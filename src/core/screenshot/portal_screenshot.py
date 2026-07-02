import asyncio
import os
import secrets
import threading
import traceback
from typing import Any

from PIL import Image
from PySide6.QtCore import QRect

from src.config import FULL_SCREEN_TEMP_PATH
from src.core.exceptions import PortalCanceledError
from src.core.screenshot.base_screenshot import BaseScreenshot

try:
    from dbus_next import BusType, Variant
    from dbus_next.aio import MessageBus
    from dbus_next.message import Message
except ImportError as exc:
    BusType = None
    Variant = None
    MessageBus = None
    Message = None
    _DBUS_IMPORT_ERROR = exc
else:
    _DBUS_IMPORT_ERROR = None

try:
    import gi

    gi.require_version("Gst", "1.0")
    from gi.repository import Gst
    gi.require_version("GstVideo", "1.0")
    from gi.repository import GstVideo
except ImportError as exc:
    Gst = None
    GstVideo = None
    _GST_IMPORT_ERROR = exc
else:
    _GST_IMPORT_ERROR = None


BUS_NAME = "org.freedesktop.portal.Desktop"
OBJECT_PATH = "/org/freedesktop/portal/desktop"
SCREENCAST_INTERFACE = "org.freedesktop.portal.ScreenCast"
REQUEST_INTERFACE = "org.freedesktop.portal.Request"
SESSION_INTERFACE = "org.freedesktop.portal.Session"
DBUS_NAME = "org.freedesktop.DBus"
DBUS_PATH = "/org/freedesktop/DBus"
DBUS_INTERFACE = "org.freedesktop.DBus"
CAPTURE_TIMEOUT_SECONDS = 1.0


class PortalScreenshot(BaseScreenshot):
    """Long-lived screenshot engine based on Wayland/XDG Desktop Portal."""

    def __init__(self):
        self._lock = threading.RLock()
        self._loop = asyncio.new_event_loop()
        self._bus = None
        self._session_handle = None
        self._node_id = None
        self._pipewire_fd = None
        self._pipeline = None
        self._appsink = None
        self._started = False
        self._last_error = None
        self._gst_initialized = False

    @staticmethod
    def is_available() -> bool:
        return _DBUS_IMPORT_ERROR is None and _GST_IMPORT_ERROR is None and Gst is not None

    @property
    def last_error(self):
        return self._last_error

    def capture(self, rect: QRect, output_path: str, dpi_scale: float = 1.0) -> bool:
        """
        Opens the portal share permission and PipeWire/GStreamer stream on the first call.
        On subsequent calls, saves the selected region from the latest frame in the open stream.
        """
        with self._lock:
            try:
                self._ensure_dependencies()
                if not self._started:
                    self._loop.run_until_complete(self._start_portal_session())
                    self._start_gstreamer_pipeline()
                    self._started = True

                return self._capture_current_frame(rect, output_path, dpi_scale)
            except PortalCanceledError:
                print("Portal selection was canceled by user.")
                self.close()
                raise
            except Exception as exc:
                self._last_error = exc
                print(f"Portal Capture Error ({type(exc).__name__}): {exc!r}")
                traceback.print_exc()
                self._print_gstreamer_bus_errors()
                self.close()
                return False

    def close(self):
        """Closes the active GStreamer pipeline and portal session."""
        with self._lock:
            if self._pipeline is not None and Gst is not None:
                self._pipeline.set_state(Gst.State.NULL)
                self._pipeline = None
                self._appsink = None

            if self._pipewire_fd is not None:
                try:
                    if isinstance(self._pipewire_fd, int):
                        os.close(self._pipewire_fd)
                except OSError:
                    pass
                self._pipewire_fd = None

            if self._session_handle and self._bus is not None:
                try:
                    self._loop.run_until_complete(self._close_portal_session())
                except Exception as exc:
                    print(f"Portal Close Error: {exc}")

            if self._bus is not None:
                try:
                    self._bus.disconnect()
                except Exception:
                    pass

            self._bus = None
            self._session_handle = None
            self._node_id = None
            self._started = False

    def _ensure_dependencies(self):
        if _DBUS_IMPORT_ERROR is not None:
            raise RuntimeError("dbus-next module was not found. Install it with `pip install dbus-next`.") from _DBUS_IMPORT_ERROR
        if _GST_IMPORT_ERROR is not None or Gst is None:
            raise RuntimeError(
                "PyGObject/GStreamer Python module was not found. Install PyGObject, GStreamer, "
                "gst-plugins-base, and PipeWire plugins as system packages."
            ) from _GST_IMPORT_ERROR

    async def _add_signal_match(self, sender, path, interface, member):
        parts = [
            "type='signal'",
            f"interface='{interface}'",
            f"member='{member}'",
        ]

        if sender is not None:
            parts.append(f"sender='{sender}'")

        if path is not None:
            parts.append(f"path='{path}'")

        await self._bus.call(Message(
            destination=DBUS_NAME,
            path=DBUS_PATH,
            interface=DBUS_INTERFACE,
            member="AddMatch",
            signature="s",
            body=[",".join(parts)],
        ))

    def _token_to_request_path(self, handle_token):
        sender = self._bus.unique_name.removeprefix(":").replace(".", "_")
        return f"/org/freedesktop/portal/desktop/request/{sender}/{handle_token}"

    async def _call_portal_request(self, member, signature, body, handle_token):
        response_future = self._loop.create_future()
        expected_request_path = self._token_to_request_path(handle_token)

        def response_handler(message):
            if (
                message.path == expected_request_path
                and message.interface == REQUEST_INTERFACE
                and message.member == "Response"
            ):
                if not response_future.done():
                    response_future.set_result(message.body)
                return True
            return None

        self._bus.add_message_handler(response_handler)
        await self._add_signal_match(None, expected_request_path, REQUEST_INTERFACE, "Response")

        try:
            reply = await self._bus.call(Message(
                destination=BUS_NAME,
                path=OBJECT_PATH,
                interface=SCREENCAST_INTERFACE,
                member=member,
                signature=signature,
                body=body,
            ))

            returned_request_path = reply.body[0]
            if returned_request_path != expected_request_path:
                raise RuntimeError(
                    f"Unexpected request path: {returned_request_path}, expected: {expected_request_path}"
                )

            response_code, results = await response_future
        finally:
            self._bus.remove_message_handler(response_handler)

        if response_code != 0:
            if response_code == 1:
                raise PortalCanceledError(f"Portal request was canceled or rejected: {member}, response={response_code}")
            raise RuntimeError(f"Portal request was canceled or rejected: {member}, response={response_code}")

        return results

    async def _start_portal_session(self):
        self._bus = await MessageBus(bus_type=BusType.SESSION, negotiate_unix_fd=True).connect()

        token = secrets.token_hex(8)
        create_token = f"create_{token}"
        create_results = await self._call_portal_request("CreateSession", "a{sv}", [{
            "session_handle_token": Variant("s", f"session_{token}"),
            "handle_token": Variant("s", create_token),
        }], create_token)
        self._session_handle = create_results["session_handle"].value

        select_token = f"select_{token}"
        await self._call_portal_request("SelectSources", "oa{sv}", [self._session_handle, {
            "handle_token": Variant("s", select_token),
            "types": Variant("u", 3),
            "multiple": Variant("b", False),
            "cursor_mode": Variant("u", 2),
        }], select_token)

        start_token = f"start_{token}"
        start_results = await self._call_portal_request("Start", "osa{sv}", [self._session_handle, "", {
            "handle_token": Variant("s", start_token),
        }], start_token)

        streams = start_results.get("streams")
        if streams is None or not streams.value:
            raise RuntimeError("Portal stream started but did not return a `streams` result.")

        self._node_id, stream_properties = streams.value[0]
        print(f"Portal PipeWire node_id={self._node_id}")
        for key, value in stream_properties.items():
            print(f"  {key}={value.value!r}")

        self._pipewire_fd = await self._open_pipewire_remote()

    async def _open_pipewire_remote(self):
        reply = await self._bus.call(Message(
            destination=BUS_NAME,
            path=OBJECT_PATH,
            interface=SCREENCAST_INTERFACE,
            member="OpenPipeWireRemote",
            signature="oa{sv}",
            body=[self._session_handle, {}],
        ))

        fd_index = reply.body[0]
        try:
            fd = reply.unix_fds[fd_index]
        except IndexError as exc:
            raise RuntimeError("Portal did not return a PipeWire file descriptor.") from exc

        if hasattr(fd, "take"):
            return fd.take()
        return fd

    async def _close_portal_session(self):
        await self._bus.call(Message(
            destination=BUS_NAME,
            path=self._session_handle,
            interface=SESSION_INTERFACE,
            member="Close",
        ))

    def _start_gstreamer_pipeline(self):
        if not self._gst_initialized:
            Gst.init(None)
            self._gst_initialized = True

        pipeline_descriptions = [
            (
                f"pipewiresrc fd={self._pipewire_fd} path={self._node_id} do-timestamp=true ! "
                "videoconvert ! video/x-raw,format=RGB ! "
                "appsink name=sink emit-signals=false sync=false max-buffers=1 drop=true"
            ),
            (
                f"pipewiresrc path={self._node_id} do-timestamp=true ! "
                "videoconvert ! video/x-raw,format=RGB ! "
                "appsink name=sink emit-signals=false sync=false max-buffers=1 drop=true"
            ),
        ]

        last_error = None
        for pipeline_description in pipeline_descriptions:
            try:
                self._pipeline = Gst.parse_launch(pipeline_description)
                self._appsink = self._pipeline.get_by_name("sink")
                state_result = self._pipeline.set_state(Gst.State.PLAYING)
                if state_result == Gst.StateChangeReturn.FAILURE:
                    raise RuntimeError(f"GStreamer pipeline could not switch to PLAYING state: {pipeline_description}")

                self._wait_for_pipeline_ready()
                print(f"Portal GStreamer pipeline is ready: {pipeline_description}")
                return
            except Exception as exc:
                last_error = exc
                print(f"Portal GStreamer pipeline attempt failed ({type(exc).__name__}): {exc!r}")
                self._print_gstreamer_bus_errors()
                if self._pipeline is not None:
                    self._pipeline.set_state(Gst.State.NULL)
                    self._pipeline = None
                    self._appsink = None

        raise RuntimeError("Portal GStreamer pipeline could not be started.") from last_error

    def _wait_for_pipeline_ready(self):
        bus = self._pipeline.get_bus()
        if bus is None:
            return

        deadline = Gst.SECOND * 3
        message = bus.timed_pop_filtered(
            deadline,
            Gst.MessageType.ASYNC_DONE | Gst.MessageType.ERROR | Gst.MessageType.STATE_CHANGED,
        )
        if message is not None and message.type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            raise RuntimeError(f"GStreamer reported an error: {err}; debug={debug}")

    def _print_gstreamer_bus_errors(self):
        if self._pipeline is None or Gst is None:
            return

        bus = self._pipeline.get_bus()
        if bus is None:
            return

        while True:
            message = bus.pop_filtered(Gst.MessageType.ERROR | Gst.MessageType.WARNING)
            if message is None:
                break
            if message.type == Gst.MessageType.ERROR:
                err, debug = message.parse_error()
                print(f"Portal GStreamer ERROR: {err}; debug={debug}")
            elif message.type == Gst.MessageType.WARNING:
                err, debug = message.parse_warning()
                print(f"Portal GStreamer WARNING: {err}; debug={debug}")

    def _build_frame_image(self, sample: Any) -> Image.Image:
        buffer = sample.get_buffer()
        caps = sample.get_caps()
        structure = caps.get_structure(0)
        width = structure.get_value("width")
        height = structure.get_value("height")
        video_format = structure.get_value("format")
        video_info = GstVideo.VideoInfo.new_from_caps(caps) if GstVideo is not None else None
        stride = abs(video_info.stride[0]) if video_info is not None else width * 3
        orientation = 1 if video_info is not None and video_info.stride[0] < 0 else -1

        success, map_info = buffer.map(Gst.MapFlags.READ)
        if not success:
            raise RuntimeError("GStreamer buffer could not be read.")

        try:
            if video_format == "RGB":
                return Image.frombytes("RGB", (width, height), map_info.data, "raw", "RGB", stride, orientation)

            if video_format == "BGR":
                return Image.frombytes("RGB", (width, height), map_info.data, "raw", "BGR", stride, orientation)

            raise RuntimeError(f"Unsupported GStreamer video format: {video_format}")
        finally:
            buffer.unmap(map_info)

    def _save_sample_region(self, sample: Any, rect: QRect, output_path: str, dpi_scale: float) -> bool:
        image = self._build_frame_image(sample)
        self._save_image_atomically(image, FULL_SCREEN_TEMP_PATH)
        width, height = image.size

        x1 = max(0, int(rect.x() * dpi_scale))
        y1 = max(0, int(rect.y() * dpi_scale))
        x2 = min(width, int((rect.x() + rect.width()) * dpi_scale))
        y2 = min(height, int((rect.y() + rect.height()) * dpi_scale))

        if x2 <= x1 or y2 <= y1:
            return False

        crop = image.crop((x1, y1, x2, y2))
        self._save_image_atomically(crop, output_path)
        return True

    def _save_image_atomically(self, image: Image.Image, output_path: str) -> None:
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        output_ext = os.path.splitext(output_path)[1]
        temp_path = f"{output_path}.tmp{output_ext}"
        image.save(temp_path)
        os.replace(temp_path, output_path)

    def _capture_current_frame(self, rect: QRect, output_path: str, dpi_scale: float) -> bool:
        sample = self._appsink.emit("try-pull-sample", int(CAPTURE_TIMEOUT_SECONDS * Gst.SECOND))
        if sample is None:
            print("Waiting for Portal GStreamer sample...")
            return False

        return self._save_sample_region(sample, rect, output_path, dpi_scale)

    def __del__(self):
        try:
            self.close()
            if not self._loop.is_closed():
                self._loop.close()
        except Exception:
            pass
