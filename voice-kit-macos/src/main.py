import sys
import threading
import os
from typing import Optional
from src.logger import setup_logging
setup_logging()

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal

from src.config_manager import ConfigManager
from src.audio.recorder import AudioRecorder
from src.clipboard.paster import ClipboardPaster
from src.hotkey.listener import HotkeyListener
from src.ui.hud_window import HudWindow
from src.ui.tray_icon import TrayIcon
from src.ui.settings_dialog import SettingsDialog
from src.ui.editor_window import EditorWindow
from src.ui.sessions_dialog import SessionsDialog
from src.ui.recordings_window import RecordingsWindow
from src.history_manager import HistoryManager

from src.transcription.base import BaseTranscriptionProvider
from src.transcription.voice_editor_provider import VoiceEditorProvider
from src.transcription.openai_provider import OpenAIProvider
from src.transcription.local_provider import LocalProvider


class AppCoordinator(QObject):
    signal_status_error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.config = ConfigManager("config.yaml")
        
        # Initialize UI components
        self.history_mgr = HistoryManager(config_manager=self.config)
        self.hud = HudWindow()
        self.editor = EditorWindow(
            on_done_callback=self._on_editor_done,
            on_cut_callback=self.cut_and_process_speech,
            on_stop_callback=self.stop_recording,
            on_continue_callback=self.continue_recording,
            on_new_callback=self.new_session_recording,
            on_settings_callback=self.open_settings,
            on_start_recording_callback=self.start_recording,
            on_sessions_callback=self.show_sessions,
            on_recordings_callback=self.show_recordings,
        )
        self.editor.history_mgr = self.history_mgr
        self.tray = TrayIcon()
        self.tray.show()

        # Initialize engines
        self.recorder = AudioRecorder(
            sample_rate=self.config.get("audio.sample_rate", 16000),
            channels=self.config.get("audio.channels", 1)
        )
        self.paster = ClipboardPaster(
            auto_paste=self.config.get("clipboard.auto_paste", True),
            restore_clipboard=self.config.get("clipboard.restore_clipboard", False),
            use_clipboard=not self.config.get("clipboard.direct_typing", False)
        )
        self.provider = self._create_provider()
        
        self.hotkey = HotkeyListener(
            combination=self.config.get("hotkey.combination", "right_fn"),
            mode=self.config.get("hotkey.mode", "toggle")
        )

        self._connect_signals()
        self._start_hotkey()

    def _create_provider(self) -> BaseTranscriptionProvider:
        provider_name = self.config.get("transcription.provider", "voice_editor")
        if provider_name == "voice_editor":
            return VoiceEditorProvider(
                url=self.config.get("transcription.voice_editor.url", "wss://voice-editor.minipc.na/ws/transcribe"),
                do_cleanup=self.config.get("transcription.voice_editor.do_cleanup", True),
                language=self.config.get("transcription.voice_editor.language", "auto"),
                headers=self.config.get("transcription.voice_editor.headers", {})
            )
        elif provider_name == "openai":
            return OpenAIProvider(
                api_key=self.config.get("transcription.openai.api_key", ""),
                model=self.config.get("transcription.openai.model", "whisper-1")
            )
        elif provider_name == "groq":
            # Groq uses OpenAI client structure with different base URL
            os.environ["OPENAI_BASE_URL"] = "https://api.groq.com/openai/v1"
            return OpenAIProvider(
                api_key=self.config.get("transcription.groq.api_key", ""),
                model=self.config.get("transcription.groq.model", "whisper-large-v3")
            )
        elif provider_name == "local":
            return LocalProvider(
                model_size=self.config.get("transcription.local.model_size", "base"),
                device=self.config.get("transcription.local.device", "auto")
            )
        return VoiceEditorProvider()

    def _connect_signals(self):
        self.tray.signal_open_app.connect(self._open_app)
        self.tray.signal_open_sessions.connect(self.show_sessions)
        self.tray.signal_open_recordings.connect(self.show_recordings)
        self.tray.signal_open_settings.connect(self.open_settings)  # kept for compat
        self.tray.signal_quit.connect(self.quit_app)

    def _open_app(self):
        """Bring the editor window to the front (idle state), or show it if hidden."""
        self.editor.signal_show_idle.emit()
        self.editor.show()
        self.editor.raise_()
        self.editor.activateWindow()

    def _start_hotkey(self):
        from src.ui.permissions_dialog import check_accessibility, PermissionsDialog
        if not check_accessibility():
            print("macOS Accessibility permission is missing or revoked. Showing permissions dialog...")
            dlg = PermissionsDialog(parent=None)
            dlg.exec()

        if check_accessibility():
            self.hotkey.start(
                on_start=self.start_recording_hotkey,
                on_stop=self.stop_recording_hotkey
            )
            print(f"VoiceKit macOS ready! Listening for global hotkey: {self.hotkey.combination}")
        else:
            print("macOS Accessibility permission not granted. Running without global hotkey.")

    def start_recording_hotkey(self) -> bool:
        if self.recorder.is_recording:
            return False
        self._recording_from_hotkey = True
        self.start_recording(clear_main=True, from_hotkey=True)
        return True

    def stop_recording_hotkey(self) -> bool:
        if not self.recorder.is_recording:
            return False
        self.stop_recording()
        return True

    def toggle_recording(self):
        if self.recorder.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def _on_audio_chunk(self, chunk: bytes):
        if hasattr(self, 'provider') and hasattr(self.provider, 'send_chunk'):
            self.provider.send_chunk(chunk)

    def continue_recording(self):
        print("Continuing recording in the same session...")
        self.start_recording(clear_main=False)

    def new_session_recording(self):
        print("Starting a new fresh recording session...")
        self.start_recording(clear_main=True)

    def _should_show_editor(self) -> bool:
        return False

    def start_recording(self, clear_main: bool | None = None, from_hotkey: bool = False):
        if self.recorder.is_recording:
            return
        if not from_hotkey:
            self._recording_from_hotkey = False
        if clear_main is None:
            # If editor is already visible and has text, default to continuing session
            if self.editor.isVisible() and bool(self.editor.text_edit.toPlainText().strip()):
                clear_main = False
            else:
                clear_main = True
        print(f"Starting recording (clear_main={clear_main})...")
        try:
            show_editor = self._should_show_editor()

            def on_partial(text: str):
                if show_editor:
                    self.editor.signal_update_partial.emit(text)
                else:
                    self.hud.signal_show_transcribing.emit(text)

            # Only use live stream when the editor window is open (live preview box).
            # In HUD-only mode (no editor), skip live stream — just post-process and insert.
            if show_editor and hasattr(self.provider, 'start_stream'):
                self.provider.start_stream(on_partial=on_partial)

            self.recorder.start(on_level=self.hud.signal_update_level.emit, on_chunk=self._on_audio_chunk)
            if show_editor:
                self.editor.signal_show_recording.emit(clear_main)
            else:
                self.hud.signal_show_recording.emit()
            self.tray.set_recording_state(True)
            self.hotkey.set_recording_state(True)
        except Exception as e:
            print(f"Failed to start recording: {e}")

    def cut_and_process_speech(self):
        if not self.recorder.is_recording:
            return
        print("Cutting speech segment and processing in background...")
        audio_bytes = self.recorder.get_wav_bytes()
        self.recorder.clear_buffer()
        if hasattr(self.provider, "reset_live_stream"):
            self.provider.reset_live_stream()
        if not audio_bytes:
            return

        import datetime, os
        rec_dir = os.path.expanduser("~/.voicekit/recordings")
        os.makedirs(rec_dir, exist_ok=True)
        ts_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        cut_path = os.path.join(rec_dir, f"rec_cut_{ts_str}.wav")
        try:
            with open(cut_path, "wb") as f:
                f.write(audio_bytes)
        except Exception:
            cut_path = None

        def _cut_worker():
            try:
                result = self.provider.transcribe_bytes(audio_bytes, on_partial=None)
                if result and not result.startswith("[Error") and not result.startswith("[Transcrib"):
                    try:
                        self.editor.history_mgr.add_session(result, provider=f"{self.config.get('transcription.provider', 'voice_editor')} (cut)", audio_path=cut_path)
                    except Exception as e:
                        print(f"Failed to save cut session: {e}")
                    self.editor.signal_append_text.emit(result)
                else:
                    print(f"Speech cut transcription failed: {result}")
            except Exception as e:
                print(f"Cut speech worker failed: {e}")

        threading.Thread(target=_cut_worker, daemon=True).start()

    def stop_recording(self):
        if not self.recorder.is_recording:
            return
        print("Stopping recording...")
        self.tray.set_recording_state(False)
        self.hotkey.set_recording_state(False)
        show_editor = self._should_show_editor()
        if show_editor:
            self.editor.signal_show_transcribing.emit(self.config.get("transcription.provider", "voice_editor"))
        else:
            self.hud.signal_show_transcribing.emit("")

        # Save audio and process in background thread
        audio_file_path = self.recorder.stop()
        audio_bytes = self.recorder.get_wav_bytes()

        if not audio_bytes and not audio_file_path:
            print("No audio captured.")
            self._recording_from_hotkey = False
            if show_editor:
                self.editor.signal_close.emit()
            else:
                self.hud.signal_hide.emit()
            return

        if not audio_bytes and audio_file_path:
            try:
                with open(audio_file_path, "rb") as f:
                    audio_bytes = f.read()
            except Exception:
                pass

        threading.Thread(
            target=self._transcribe_thread,
            args=(audio_bytes, audio_file_path),
            daemon=True
        ).start()

    def _transcribe_thread(self, audio_bytes: bytes, audio_file_path: str = None):
        try:
            print(f"Transcribing {len(audio_bytes)} bytes with {self.config.get('transcription.provider')}...")
            if hasattr(self.provider, 'finish_stream') and getattr(self.provider, '_streaming_active', False):
                text = self.provider.finish_stream(fallback_audio_bytes=audio_bytes)
            else:
                text = self.provider.transcribe_bytes(audio_bytes, on_partial=None)
            print(f"Transcription result: {text}")

            show_editor = self._should_show_editor()
            if text and not text.startswith("[Error") and not text.startswith("[Transcrib"):
                try:
                    provider_label = f"{self.config.get('transcription.provider', 'voice_editor')}" + ("" if show_editor else " (direct)")
                    self.editor.history_mgr.add_session(text, provider=provider_label, audio_path=audio_file_path)
                except Exception as e:
                    print(f"Failed to save session to history: {e}")
                if show_editor:
                    # In editor mode: show text in editor. Session already saved to history with audio_path.
                    self.editor.signal_show_finished.emit(text)
                else:
                    # In HUD mode (no editor): auto-paste text directly into focused app.
                    self.paster.paste(text)
                    self.hud.signal_show_done.emit()
            else:
                if show_editor:
                    self.editor.signal_show_finished.emit(f"Error: {text or 'Transcription failed'}")
                else:
                    self.hud.signal_show_transcribing.emit(text or "Failed")
                    threading.Timer(2.5, self.hud.signal_hide.emit).start()
        finally:
            self._recording_from_hotkey = False

    def _on_editor_done(self, text: str):
        # Editor Done button now just closes the window (session saved to history inside editor).
        # No clipboard paste needed — user can use the Copy button if they want.
        pass

    def open_settings(self):
        dialog = SettingsDialog(self.config, hotkey_listener=self.hotkey)
        dialog.signal_config_changed.connect(self._on_config_changed)
        dialog.exec()

    def show_sessions(self):
        dialog = SessionsDialog(self.editor.history_mgr)
        dialog.signal_open_in_editor.connect(self._on_open_session_from_dialog)
        dialog.exec()

    def _on_open_session_from_dialog(self, session_data: dict):
        text = session_data.get("text", "")
        self.editor.signal_show_idle.emit()
        self.editor.show()
        self.editor.raise_()
        self.editor.activateWindow()
        self.editor.text_edit.setPlainText(text)
        self.editor.lbl_status.setText(f"📂 Loaded session from {session_data.get('date', '')} {session_data.get('timestamp', '')}")

    def show_recordings(self):
        if not hasattr(self, 'recordings_window') or self.recordings_window is None:
            self.recordings_window = RecordingsWindow(self.history_mgr, regenerate_handler=self.regenerate_recording)
        self.recordings_window.refresh_recordings()
        self.recordings_window.show()
        self.recordings_window.raise_()
        self.recordings_window.activateWindow()

    def regenerate_recording(self, session_id: str, audio_path: str, on_complete_callback):
        def _regen_worker():
            try:
                with open(audio_path, "rb") as f:
                    audio_bytes = f.read()
                print(f"Regenerating session {session_id} from {audio_path} ({len(audio_bytes)} bytes)...")
                if hasattr(self.provider, 'finish_stream') and getattr(self.provider, '_streaming_active', False):
                    text = self.provider.finish_stream(fallback_audio_bytes=audio_bytes)
                else:
                    text = self.provider.transcribe_bytes(audio_bytes, on_partial=None)
                print(f"Regenerate result: {text}")
                on_complete_callback(text)
            except Exception as e:
                print(f"Regenerate failed: {e}")
                on_complete_callback("[Error: Regeneration failed]")
        threading.Thread(target=_regen_worker, daemon=True).start()

    def _on_config_changed(self):
        print("Reloading config...")
        self.provider = self._create_provider()
        self.paster = ClipboardPaster(
            auto_paste=self.config.get("clipboard.auto_paste", True),
            restore_clipboard=self.config.get("clipboard.restore_clipboard", False),
            use_clipboard=not self.config.get("clipboard.direct_typing", False)
        )
        self.hotkey.update_config(
            self.config.get("hotkey.combination", "right_fn"),
            self.config.get("hotkey.mode", "toggle")
        )

    def quit_app(self):
        print("Quitting VoiceKit macOS...")
        self.hotkey.stop()
        if self.recorder.is_recording:
            self.recorder.stop()
        QApplication.quit()


def set_macos_accessory_policy():
    """Set macOS activation policy to Accessory (1) via pure ctypes to prevent focus stealing without PyObjC."""
    import sys
    if sys.platform != "darwin":
        return
    try:
        import ctypes
        import ctypes.util
        ctypes.cdll.LoadLibrary("/System/Library/Frameworks/AppKit.framework/AppKit")
        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))

        get_class = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_char_p)(("objc_getClass", objc))
        register_sel = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_char_p)(("sel_registerName", objc))

        cls_NSApp = get_class(b"NSApplication")
        sel_sharedApp = register_sel(b"sharedApplication")
        sel_setPolicy = register_sel(b"setActivationPolicy:")

        get_app = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(("objc_msgSend", objc))
        set_policy = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long)(("objc_msgSend", objc))

        app = get_app(cls_NSApp, sel_sharedApp)
        if app:
            set_policy(app, sel_setPolicy, 1)  # 1 = NSApplicationActivationPolicyAccessory
            print("[macOS] Activation policy set to Accessory (no focus stealing).")
    except Exception as e:
        print(f"[macOS] Could not set activation policy via ctypes: {e}")


def main():
    set_macos_accessory_policy()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("VoiceKit")
    coordinator = AppCoordinator()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
