# UmayOCR (Instant OCR Translator HUD)

UmayOCR is a high-performance, PySide6-based instant translation tool designed for Linux. It acts as a transparent HUD (Heads-Up Display) that provides **real-time subtitle translation** for games, videos, movies, and any non-selectable text on your screen.

![UmayOCR Screenshot](docs/Screenshot_20260531_215750.png)

By "sniping" a specific area of your screen, UmayOCR continuously monitors that region, extracts text using OCR (Optical Character Recognition), and overlays the translated text instantly, making it perfect for playing untranslated games or watching foreign media.

> **Note:** Current version is optimized for **KDE Plasma (Wayland)** using **xcb** mode. Future versions will expand compatibility.

## 🚀 Key Features

*   **Real-Time HUD Translation:** Specifically designed to provide live translations over video players and game windows.
*   **KDE & Wayland Support:** Currently runs in `xcb` mode, specifically tailored for KDE Plasma environments using native tools for region selection and capture.
*   **Sniper Mode Overlay:** Modular region selection system to target subtitle areas.
*   **Modular OCR Engine Subsystem:** Dynamic multi-backend support (Tesseract & EasyOCR) for accurate text extraction.
*   **Dual-Engine Translation Subsystem:** Context-aware translations via Google Translate and DeepL (Note: DeepL is currently untested).
*   **Unix Socket IPC Broadcasting:** Real-time JSON broadcast of every translation to a local Unix socket, enabling integration with other tools (e.g., custom subtitles, logging, or OBS).
*   **Global Shortcuts & IPC Integration:** Utilizes a lightweight single-instance architecture to handle background processes and external CLI-driven shortcuts.

## 📡 External Integration (IPC)

UmayOCR features a built-in Unix Domain Socket server that broadcasts every translation in real-time. This allows you to "pipe" translations into other applications, scripts, or overlays effortlessly.

This feature is designed for high extensibility, making it easy to integrate UmayOCR into your existing workflow:
*   **Live Streaming:** Send translations directly to OBS or other broadcast software as a text source.
*   **Accessibility:** Integrate with text-to-speech (TTS) engines for real-time audio translation.
*   **Data Logging:** Pipe the stream to a file to create a searchable history or transcripts of your sessions.
*   **Custom Overlays:** Build your own UI or specialized subtitles that react to UmayOCR data.

**Socket Path:** `/tmp/umayocr.sock`

### How to use:
You can listen to the stream using standard tools like `netcat` (nc):
```bash
nc -U /tmp/umayocr.sock
```

### JSON Output Format:
Every translation is sent as a single line in JSON format:
```json
{
  "original": "Hello world",
  "translated": "Merhaba dünya",
  "source": "en",
  "target": "tr",
  "engine": "Google",
  "timestamp": 1717181234.56
}
```

## 🗺️ Roadmap & Future Support

While currently focused on KDE/Linux, support for the following is planned:
- [ ] **Native Linux Packaging:** Distribution via `.deb` (Debian/Ubuntu), AUR (Arch Linux), and **Flatpak**.
- [ ] **Other Linux DEs:** Full native Wayland support without xcb.
- [ ] **Windows Support:** Integration with Windows-native capture and OCR APIs.
- [ ] **macOS Support:** Support for macOS native APIs and capture systems.

---

## 🛠️ System Requirements

Before running the application, install the system packages required for OCR, PipeWire/GStreamer portal capture, and PyGObject integration.

### CachyOS / Arch packages

For GNOME:

```bash
sudo pacman -S --needed \
  python-gobject \
  gst-plugin-pipewire \
  gst-plugins-base \
  gst-plugins-good \
  pipewire \
  xdg-desktop-portal \
  xdg-desktop-portal-gnome \
  tesseract \
  tesseract-data-rus \
  tesseract-data-ara \
  tesseract-data-heb \
  tesseract-data-tur \
  tesseract-data-vie \
  tesseract-data-tha \
  tesseract-data-spa \
  tesseract-data-jpn \
  tesseract-data-chi_sim \
  tesseract-data-chi_tra
```

For KDE Plasma:

```bash
sudo pacman -S --needed \
  python-gobject \
  gst-plugin-pipewire \
  gst-plugins-base \
  gst-plugins-good \
  pipewire \
  xdg-desktop-portal \
  xdg-desktop-portal-kde \
  tesseract \
  tesseract-data-rus \
  tesseract-data-ara \
  tesseract-data-heb \
  tesseract-data-tur \
  tesseract-data-vie \
  tesseract-data-tha \
  tesseract-data-spa \
  tesseract-data-jpn \
  tesseract-data-chi_sim \
  tesseract-data-chi_tra
```

### Fedora packages

For GNOME:

```bash
sudo dnf install -y \
  python3-gobject \
  gstreamer1-plugin-pipewire \
  gstreamer1-plugins-base \
  gstreamer1-plugins-good \
  pipewire \
  xdg-desktop-portal \
  xdg-desktop-portal-gnome \
  tesseract \
  tesseract-langpack-rus \
  tesseract-langpack-ara \
  tesseract-langpack-heb \
  tesseract-langpack-tur \
  tesseract-langpack-vie \
  tesseract-langpack-tha \
  tesseract-langpack-spa \
  tesseract-langpack-jpn \
  tesseract-langpack-chi_sim \
  tesseract-langpack-chi_tra
```

For KDE Plasma:

```bash
sudo dnf install -y \
  python3-gobject \
  gstreamer1-plugin-pipewire \
  gstreamer1-plugins-base \
  gstreamer1-plugins-good \
  pipewire \
  xdg-desktop-portal \
  xdg-desktop-portal-kde \
  tesseract \
  tesseract-langpack-rus \
  tesseract-langpack-ara \
  tesseract-langpack-heb \
  tesseract-langpack-tur \
  tesseract-langpack-vie \
  tesseract-langpack-tha \
  tesseract-langpack-spa \
  tesseract-langpack-jpn \
  tesseract-langpack-chi_sim \
  tesseract-langpack-chi_tra
```

### Ubuntu / Debian packages

For GNOME:

```bash
sudo apt update
sudo apt install -y \
  python3-gi \
  python3-gi-cairo \
  gir1.2-gstreamer-1.0 \
  gir1.2-gst-plugins-base-1.0 \
  gstreamer1.0-pipewire \
  gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-good \
  pipewire \
  xdg-desktop-portal \
  xdg-desktop-portal-gnome \
  tesseract-ocr \
  tesseract-ocr-rus \
  tesseract-ocr-ara \
  tesseract-ocr-heb \
  tesseract-ocr-tur \
  tesseract-ocr-vie \
  tesseract-ocr-tha \
  tesseract-ocr-spa \
  tesseract-ocr-jpn \
  tesseract-ocr-chi-sim \
  tesseract-ocr-chi-tra
```

For KDE Plasma:

```bash
sudo apt update
sudo apt install -y \
  python3-gi \
  python3-gi-cairo \
  gir1.2-gstreamer-1.0 \
  gir1.2-gst-plugins-base-1.0 \
  gstreamer1.0-pipewire \
  gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-good \
  pipewire \
  xdg-desktop-portal \
  xdg-desktop-portal-kde \
  tesseract-ocr \
  tesseract-ocr-rus \
  tesseract-ocr-ara \
  tesseract-ocr-heb \
  tesseract-ocr-tur \
  tesseract-ocr-vie \
  tesseract-ocr-tha \
  tesseract-ocr-spa \
  tesseract-ocr-jpn \
  tesseract-ocr-chi-sim \
  tesseract-ocr-chi-tra
```

---

## 📦 Installation & Usage

1. **Clone the repository:**
   ```bash
   git clone https://github.com/sedataym/umayocr.git
   cd umayocr
   ```

2. **Create and activate a virtual environment:**

   PyGObject is normally installed as a system package, not as a regular pip-only dependency. Create the virtual environment with system site packages enabled:

   ```bash
   python -m venv --system-site-packages .venv
   source .venv/bin/activate
   ```

   If the virtual environment already exists, enable system site packages in `.venv/pyvenv.cfg`:

   ```ini
   include-system-site-packages = true
   ```

3. **Install dependencies:**
   ```bash
   .venv/bin/pip install -r requirements.txt
   ```

4. **Run the application:**
   ```bash
   .venv/bin/python run.py
   ```

---

## 🛠️ Tech Stack
* **GUI:** PySide6
* **OCR:** pytesseract, easyocr
* **Translation:** deep-translator
* **Desktop Environments:** KDE Plasma (optimized) / GNOME
