#!/usr/bin/env bash
# UmayOCR installer for Arch/Arch-based, Ubuntu, Debian, and Fedora.
# Installs system dependencies, detects desktop environment and GPU vendor,
# creates a Python virtual environment, and installs Python OCR backends.

set -Eeuo pipefail
IFS=$'\n\t'

APP_NAME="UmayOCR"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"
LOG_FILE="${PROJECT_ROOT}/install.log"
YES=0
DRY_RUN=0
INSTALL_GPU=1
INSTALL_DESKTOP_FILE=1

DISTRO_ID=""
DISTRO_LIKE=""
DISTRO_NAME=""
DISTRO_FAMILY=""
PKG_MANAGER=""
SUDO=""
DETECTED_DE="unknown"
PORTAL_BACKEND=""
GPU_VENDOR="unknown"
GPU_DETAILS=""
PYTHON_BIN=""

BASE_PACKAGES=()
PORTAL_PACKAGES=()
GPU_PACKAGES=()
OPTIONAL_PACKAGES=()
TESSERACT_LANG_PACKAGES=()
WARNINGS=()

usage() {
  cat <<'EOF'
UmayOCR installer

Usage:
  ./install.sh [options]

Options:
  -y, --yes              Do not ask confirmation questions.
      --dry-run          Print commands without executing them.
      --no-gpu           Skip GPU acceleration package installation.
      --no-desktop-file  Do not create a desktop launcher.
  -h, --help             Show this help message.
EOF
}

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "${LOG_FILE}"
}

warn() {
  WARNINGS+=("$*")
  log "WARNING: $*"
}

fail() {
  log "ERROR: $*"
  exit 1
}

run_cmd() {
  log "+ $*"
  if [[ "${DRY_RUN}" -eq 0 ]]; then
    "$@"
  fi
}

run_shell() {
  log "+ $*"
  if [[ "${DRY_RUN}" -eq 0 ]]; then
    bash -lc "$*"
  fi
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

confirm() {
  local prompt="$1"
  if [[ "${YES}" -eq 1 ]]; then
    return 0
  fi
  read -r -p "${prompt} [y/N] " answer
  [[ "${answer}" =~ ^[Yy]$|^[Yy][Ee][Ss]$ ]]
}

append_unique() {
  local -n target="$1"
  shift
  local item existing
  for item in "$@"; do
    [[ -n "${item}" ]] || continue
    existing=0
    local current
    for current in "${target[@]}"; do
      if [[ "${current}" == "${item}" ]]; then
        existing=1
        break
      fi
    done
    [[ "${existing}" -eq 1 ]] || target+=("${item}")
  done
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -y|--yes) YES=1 ;;
      --dry-run) DRY_RUN=1 ;;
      --no-gpu) INSTALL_GPU=0 ;;
      --no-desktop-file) INSTALL_DESKTOP_FILE=0 ;;
      -h|--help) usage; exit 0 ;;
      *) fail "Unknown option: $1" ;;
    esac
    shift
  done
}

setup_sudo() {
  if [[ "${EUID}" -eq 0 ]]; then
    SUDO=""
  elif have_cmd sudo; then
    SUDO="sudo"
    if [[ "${DRY_RUN}" -eq 0 ]]; then
      log "Requesting sudo privileges for system package installation."
      sudo -v
    fi
  else
    fail "sudo is required when the installer is not run as root."
  fi
}

detect_distro() {
  if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    source /etc/os-release
    DISTRO_ID="${ID:-unknown}"
    DISTRO_LIKE="${ID_LIKE:-}"
    DISTRO_NAME="${PRETTY_NAME:-${NAME:-${DISTRO_ID}}}"
  else
    DISTRO_ID="unknown"
    DISTRO_LIKE=""
    DISTRO_NAME="Unknown Linux distribution"
    warn "/etc/os-release not found; continuing with package-manager detection."
  fi

  if have_cmd pacman; then
    DISTRO_FAMILY="arch"
    PKG_MANAGER="pacman"
  elif have_cmd apt; then
    DISTRO_FAMILY="debian"
    PKG_MANAGER="apt"
  elif have_cmd dnf; then
    DISTRO_FAMILY="fedora"
    PKG_MANAGER="dnf"
  else
    fail "Unsupported system: none of pacman, apt, or dnf was found."
  fi

  log "Detected distribution: ${DISTRO_NAME}"
  log "Detected package manager: ${PKG_MANAGER} (${DISTRO_FAMILY} package set)"
}

detect_desktop_environment() {
  local desktop="${XDG_CURRENT_DESKTOP:-${XDG_SESSION_DESKTOP:-${DESKTOP_SESSION:-}}}"
  desktop="$(printf '%s' "${desktop}" | tr '[:upper:]' '[:lower:]')"

  case "${desktop}" in
    *kde*|*plasma*) DETECTED_DE="kde" ;;
    *gnome*) DETECTED_DE="gnome" ;;
    *xfce*) DETECTED_DE="xfce" ;;
    *cinnamon*) DETECTED_DE="cinnamon" ;;
    *mate*) DETECTED_DE="mate" ;;
    *sway*|*hyprland*|*river*|*wayfire*|*wlroots*) DETECTED_DE="wlroots" ;;
    *)
      if pgrep -x plasmashell >/dev/null 2>&1 || pgrep -x kwin_wayland >/dev/null 2>&1; then
        DETECTED_DE="kde"
      elif pgrep -x gnome-shell >/dev/null 2>&1; then
        DETECTED_DE="gnome"
      elif pgrep -x sway >/dev/null 2>&1 || pgrep -x Hyprland >/dev/null 2>&1; then
        DETECTED_DE="wlroots"
      else
        DETECTED_DE="unknown"
      fi
      ;;
  esac

  case "${DETECTED_DE}" in
    kde) PORTAL_BACKEND="kde" ;;
    gnome|cinnamon) PORTAL_BACKEND="gnome" ;;
    wlroots) PORTAL_BACKEND="wlr" ;;
    *) PORTAL_BACKEND="generic" ;;
  esac

  log "Detected desktop environment: ${DETECTED_DE}; portal backend: ${PORTAL_BACKEND}"
}

minimal_package_probe() {
  case "${DISTRO_FAMILY}" in
    arch)
      run_cmd ${SUDO:+$SUDO} pacman -Sy --needed --noconfirm pciutils || true
      ;;
    debian)
      run_cmd ${SUDO:+$SUDO} apt update
      run_cmd ${SUDO:+$SUDO} apt install -y pciutils || true
      ;;
    fedora)
      run_cmd ${SUDO:+$SUDO} dnf install -y pciutils || true
      ;;
  esac
}

detect_gpu() {
  if ! have_cmd lspci; then
    warn "lspci is not available yet; installing pciutils before GPU detection."
    minimal_package_probe
  fi

  if have_cmd lspci; then
    GPU_DETAILS="$(lspci -nnk | grep -Ei 'vga|3d|display|nvidia|amd|radeon|intel' || true)"
    local lower
    lower="$(printf '%s' "${GPU_DETAILS}" | tr '[:upper:]' '[:lower:]')"
    if [[ "${lower}" == *"nvidia"* || "${lower}" == *"10de"* ]]; then
      GPU_VENDOR="nvidia"
    elif [[ "${lower}" == *"amd"* || "${lower}" == *"advanced micro devices"* || "${lower}" == *"radeon"* || "${lower}" == *"1002"* ]]; then
      GPU_VENDOR="amd"
    elif [[ "${lower}" == *"intel"* || "${lower}" == *"8086"* ]]; then
      GPU_VENDOR="intel"
    else
      GPU_VENDOR="unknown"
    fi
  else
    GPU_VENDOR="unknown"
    GPU_DETAILS="lspci unavailable"
  fi

  log "Detected GPU vendor: ${GPU_VENDOR}"
  if [[ -n "${GPU_DETAILS}" ]]; then
    log "GPU details:"
    printf '%s\n' "${GPU_DETAILS}" | tee -a "${LOG_FILE}"
  fi
}

package_exists_arch() {
  pacman -Si "$1" >/dev/null 2>&1
}

package_exists_debian() {
  apt-cache show "$1" >/dev/null 2>&1
}

package_exists_fedora() {
  dnf -q info "$1" >/dev/null 2>&1
}

filter_existing_packages() {
  local -n input="$1"
  local filtered=()
  local pkg
  for pkg in "${input[@]}"; do
    case "${DISTRO_FAMILY}" in
      arch)
        if [[ "${DRY_RUN}" -eq 1 ]] || package_exists_arch "${pkg}"; then
          filtered+=("${pkg}")
        else
          warn "Skipping unavailable Arch package: ${pkg}"
        fi
        ;;
      debian)
        if [[ "${DRY_RUN}" -eq 1 ]] || package_exists_debian "${pkg}"; then
          filtered+=("${pkg}")
        else
          warn "Skipping unavailable Debian/Ubuntu package: ${pkg}"
        fi
        ;;
      fedora)
        if [[ "${DRY_RUN}" -eq 1 ]] || package_exists_fedora "${pkg}"; then
          filtered+=("${pkg}")
        else
          warn "Skipping unavailable Fedora package: ${pkg}"
        fi
        ;;
    esac
  done
  input=("${filtered[@]}")
}

build_package_lists() {
  case "${DISTRO_FAMILY}" in
    arch)
      append_unique BASE_PACKAGES \
        base-devel git python python-pip python-virtualenv python-gobject cairo gobject-introspection \
        gst-plugin-pipewire gst-plugins-base gst-plugins-good pipewire xdg-desktop-portal \
        tesseract pciutils mesa-utils vulkan-tools libglvnd
      append_unique TESSERACT_LANG_PACKAGES \
        tesseract-data-eng tesseract-data-rus tesseract-data-ara tesseract-data-heb \
        tesseract-data-tur tesseract-data-vie tesseract-data-tha tesseract-data-spa \
        tesseract-data-jpn tesseract-data-chi_sim tesseract-data-chi_tra
      case "${PORTAL_BACKEND}" in
        kde) append_unique PORTAL_PACKAGES xdg-desktop-portal-kde spectacle ;;
        gnome) append_unique PORTAL_PACKAGES xdg-desktop-portal-gnome ;;
        wlr) append_unique PORTAL_PACKAGES xdg-desktop-portal-wlr slurp grim ;;
        *) append_unique PORTAL_PACKAGES xdg-desktop-portal-gtk ;;
      esac
      case "${GPU_VENDOR}" in
        nvidia) append_unique GPU_PACKAGES nvidia-utils cuda cudnn python-pytorch-cuda ;;
        amd) append_unique GPU_PACKAGES rocm-hip-sdk rocm-opencl-runtime rocminfo vulkan-radeon opencl-mesa ;;
        intel) append_unique GPU_PACKAGES intel-compute-runtime intel-media-driver vulkan-intel intel-gmmlib ;;
      esac
      ;;
    debian)
      append_unique BASE_PACKAGES \
        build-essential git python3 python3-pip python3-venv python3-dev python3-gi python3-gi-cairo \
        gir1.2-gstreamer-1.0 gir1.2-gst-plugins-base-1.0 gstreamer1.0-pipewire \
        gstreamer1.0-plugins-base gstreamer1.0-plugins-good pipewire xdg-desktop-portal \
        tesseract-ocr pciutils mesa-utils vulkan-tools
      append_unique TESSERACT_LANG_PACKAGES \
        tesseract-ocr-eng tesseract-ocr-rus tesseract-ocr-ara tesseract-ocr-heb \
        tesseract-ocr-tur tesseract-ocr-vie tesseract-ocr-tha tesseract-ocr-spa \
        tesseract-ocr-jpn tesseract-ocr-chi-sim tesseract-ocr-chi-tra
      case "${PORTAL_BACKEND}" in
        kde) append_unique PORTAL_PACKAGES xdg-desktop-portal-kde kde-spectacle ;;
        gnome) append_unique PORTAL_PACKAGES xdg-desktop-portal-gnome ;;
        wlr) append_unique PORTAL_PACKAGES xdg-desktop-portal-wlr slurp grim ;;
        *) append_unique PORTAL_PACKAGES xdg-desktop-portal-gtk ;;
      esac
      case "${GPU_VENDOR}" in
        nvidia) append_unique GPU_PACKAGES nvidia-driver nvidia-cuda-toolkit nvidia-cudnn ;;
        amd) append_unique GPU_PACKAGES rocm-opencl-runtime rocm-dev rocminfo mesa-vulkan-drivers mesa-opencl-icd ;;
        intel) append_unique GPU_PACKAGES intel-opencl-icd intel-media-va-driver-non-free intel-gpu-tools mesa-vulkan-drivers ;;
      esac
      ;;
    fedora)
      append_unique BASE_PACKAGES \
        gcc gcc-c++ make git python3 python3-pip python3-devel python3-gobject cairo-gobject-devel \
        gstreamer1-plugin-pipewire gstreamer1-plugins-base gstreamer1-plugins-good pipewire \
        xdg-desktop-portal tesseract pciutils mesa-demos vulkan-tools
      append_unique TESSERACT_LANG_PACKAGES \
        tesseract-langpack-eng tesseract-langpack-rus tesseract-langpack-ara tesseract-langpack-heb \
        tesseract-langpack-tur tesseract-langpack-vie tesseract-langpack-tha tesseract-langpack-spa \
        tesseract-langpack-jpn tesseract-langpack-chi_sim tesseract-langpack-chi_tra
      case "${PORTAL_BACKEND}" in
        kde) append_unique PORTAL_PACKAGES xdg-desktop-portal-kde spectacle ;;
        gnome) append_unique PORTAL_PACKAGES xdg-desktop-portal-gnome ;;
        wlr) append_unique PORTAL_PACKAGES xdg-desktop-portal-wlr slurp grim ;;
        *) append_unique PORTAL_PACKAGES xdg-desktop-portal-gtk ;;
      esac
      case "${GPU_VENDOR}" in
        nvidia) append_unique GPU_PACKAGES xorg-x11-drv-nvidia-cuda cuda-toolkit ;;
        amd) append_unique GPU_PACKAGES rocm-opencl rocm-hip rocm-smi mesa-vulkan-drivers mesa-libOpenCL ;;
        intel) append_unique GPU_PACKAGES intel-compute-runtime intel-media-driver intel-gpu-tools mesa-vulkan-drivers ;;
      esac
      ;;
  esac

  filter_existing_packages BASE_PACKAGES
  filter_existing_packages PORTAL_PACKAGES
  filter_existing_packages TESSERACT_LANG_PACKAGES
  if [[ "${INSTALL_GPU}" -eq 1 ]]; then
    filter_existing_packages GPU_PACKAGES
  else
    GPU_PACKAGES=()
  fi
}

install_system_packages() {
  local packages=("${BASE_PACKAGES[@]}" "${PORTAL_PACKAGES[@]}" "${TESSERACT_LANG_PACKAGES[@]}")
  if [[ "${#packages[@]}" -eq 0 ]]; then
    warn "No base system packages selected for installation."
    return 0
  fi

  case "${DISTRO_FAMILY}" in
    arch)
      run_cmd ${SUDO:+$SUDO} pacman -Sy --needed --noconfirm "${packages[@]}"
      ;;
    debian)
      run_cmd ${SUDO:+$SUDO} apt update
      run_cmd ${SUDO:+$SUDO} apt install -y "${packages[@]}"
      ;;
    fedora)
      run_cmd ${SUDO:+$SUDO} dnf install -y "${packages[@]}"
      ;;
  esac
}

install_gpu_packages() {
  [[ "${INSTALL_GPU}" -eq 1 ]] || { log "GPU package installation skipped by --no-gpu."; return 0; }
  [[ "${GPU_VENDOR}" != "unknown" ]] || { warn "No supported GPU vendor detected; skipping GPU packages."; return 0; }
  [[ "${#GPU_PACKAGES[@]}" -gt 0 ]] || { warn "No available GPU packages found for ${GPU_VENDOR} on ${DISTRO_NAME}."; return 0; }

  log "GPU package installation can be large and may alter graphics drivers."
  if ! confirm "Install best-effort ${GPU_VENDOR} GPU acceleration packages?"; then
    warn "User skipped GPU package installation."
    return 0
  fi

  case "${DISTRO_FAMILY}" in
    arch)
      run_cmd ${SUDO:+$SUDO} pacman -S --needed --noconfirm "${GPU_PACKAGES[@]}" || warn "GPU package installation failed; continuing with Python setup."
      ;;
    debian)
      run_cmd ${SUDO:+$SUDO} apt install -y "${GPU_PACKAGES[@]}" || warn "GPU package installation failed; continuing with Python setup."
      ;;
    fedora)
      run_cmd ${SUDO:+$SUDO} dnf install -y "${GPU_PACKAGES[@]}" || warn "GPU package installation failed; continuing with Python setup."
      ;;
  esac
}

select_python() {
  if have_cmd python3; then
    PYTHON_BIN="python3"
  elif have_cmd python; then
    PYTHON_BIN="python"
  else
    fail "Python was not found after package installation."
  fi
  log "Using Python: $(${PYTHON_BIN} --version 2>&1)"
}

create_virtualenv() {
  if [[ ! -d "${VENV_DIR}" ]]; then
    run_cmd "${PYTHON_BIN}" -m venv --system-site-packages "${VENV_DIR}"
  else
    log "Virtual environment already exists: ${VENV_DIR}"
    if [[ -f "${VENV_DIR}/pyvenv.cfg" ]] && ! grep -q '^include-system-site-packages = true' "${VENV_DIR}/pyvenv.cfg"; then
      log "Enabling system site packages in existing virtual environment."
      if [[ "${DRY_RUN}" -eq 0 ]]; then
        sed -i 's/^include-system-site-packages = .*/include-system-site-packages = true/' "${VENV_DIR}/pyvenv.cfg" || true
        grep -q '^include-system-site-packages = true' "${VENV_DIR}/pyvenv.cfg" || printf '\ninclude-system-site-packages = true\n' >> "${VENV_DIR}/pyvenv.cfg"
      fi
    fi
  fi

  run_cmd "${VENV_DIR}/bin/python" -m pip install --upgrade pip setuptools wheel
}

python_version_supported_by_paddle() {
  "${VENV_DIR}/bin/python" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info < (3, 13) else 1)
PY
}

install_python_packages() {
  [[ -f "${PROJECT_ROOT}/requirements.txt" ]] || fail "requirements.txt not found."
  run_cmd "${VENV_DIR}/bin/python" -m pip install -r "${PROJECT_ROOT}/requirements.txt"
  run_cmd "${VENV_DIR}/bin/python" -m pip install -e "${PROJECT_ROOT}"

  if [[ "${INSTALL_GPU}" -eq 1 && "${GPU_VENDOR}" == "nvidia" ]]; then
    log "Installing PyTorch CUDA wheels for NVIDIA via pip."
    run_cmd "${VENV_DIR}/bin/python" -m pip install --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 || {
      warn "PyTorch CUDA wheel installation failed; falling back to CPU wheels."
      run_cmd "${VENV_DIR}/bin/python" -m pip install --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu || warn "PyTorch CPU installation failed."
    }
  else
    log "Installing PyTorch CPU wheels as safe default for EasyOCR."
    run_cmd "${VENV_DIR}/bin/python" -m pip install --upgrade torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu || warn "PyTorch CPU installation failed. EasyOCR may install its own torch dependency or fail at runtime."
  fi

  if python_version_supported_by_paddle; then
    log "Installing PaddlePaddle CPU backend for PaddleOCR compatibility."
    run_cmd "${VENV_DIR}/bin/python" -m pip install --upgrade paddlepaddle || warn "paddlepaddle installation failed; PaddleOCR remains optional."
  else
    warn "Skipping paddlepaddle because current Python version is not supported by available PaddlePaddle wheels."
  fi
}

create_launchers() {
  local launcher="${VENV_DIR}/bin/umayocr-run"
  log "Creating launcher: ${launcher}"
  if [[ "${DRY_RUN}" -eq 0 ]]; then
    cat > "${launcher}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "${PROJECT_ROOT}"
exec "${VENV_DIR}/bin/python" "${PROJECT_ROOT}/run.py" "\$@"
EOF
    chmod +x "${launcher}"
  fi

  [[ "${INSTALL_DESKTOP_FILE}" -eq 1 ]] || { log "Desktop launcher skipped by --no-desktop-file."; return 0; }

  local desktop_dir="${HOME}/.local/share/applications"
  local desktop_file="${desktop_dir}/umayocr.desktop"
  log "Creating desktop launcher: ${desktop_file}"
  if [[ "${DRY_RUN}" -eq 0 ]]; then
    mkdir -p "${desktop_dir}"
    cat > "${desktop_file}" <<EOF
[Desktop Entry]
Type=Application
Name=UmayOCR
Comment=Instant OCR Translator HUD
Exec=${launcher}
Icon=${PROJECT_ROOT}/src/ui/assets/UmayOCR.png
Terminal=false
Categories=Utility;OCR;Translation;
StartupNotify=true
EOF
    chmod +x "${desktop_file}"
    if have_cmd update-desktop-database; then
      update-desktop-database "${desktop_dir}" >/dev/null 2>&1 || true
    fi
  fi
}

post_install_checks() {
  log "Running post-install checks."
  run_cmd "${VENV_DIR}/bin/python" - <<'PY'
import importlib.util
import sys
modules = ["PySide6", "pytesseract", "easyocr", "PIL", "dbus_next"]
missing = [name for name in modules if importlib.util.find_spec(name) is None]
if missing:
    print("Missing Python modules:", ", ".join(missing))
    sys.exit(1)
print("Core Python modules are importable.")
PY
}

print_summary() {
  cat <<EOF | tee -a "${LOG_FILE}"

Installation summary
--------------------
Distribution:       ${DISTRO_NAME}
Package manager:    ${PKG_MANAGER}
Desktop:            ${DETECTED_DE}
Portal backend:     ${PORTAL_BACKEND}
GPU vendor:         ${GPU_VENDOR}
Project root:       ${PROJECT_ROOT}
Virtual env:        ${VENV_DIR}
Log file:           ${LOG_FILE}

Run UmayOCR:
  ${VENV_DIR}/bin/python ${PROJECT_ROOT}/run.py
or:
  ${VENV_DIR}/bin/umayocr-run

EOF

  if [[ "${#WARNINGS[@]}" -gt 0 ]]; then
    log "Warnings:"
    local warning
    for warning in "${WARNINGS[@]}"; do
      printf '  - %s\n' "${warning}" | tee -a "${LOG_FILE}"
    done
  fi
}

main() {
  : > "${LOG_FILE}"
  parse_args "$@"
  log "Starting ${APP_NAME} installer."
  detect_distro
  setup_sudo
  detect_desktop_environment
  minimal_package_probe
  detect_gpu
  build_package_lists
  install_system_packages
  install_gpu_packages
  select_python
  create_virtualenv
  install_python_packages
  create_launchers
  post_install_checks || warn "Post-install import checks failed; review ${LOG_FILE}."
  print_summary
  log "Installer finished."
}

main "$@"
