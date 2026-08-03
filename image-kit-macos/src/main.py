import sys
import pyperclip
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtCore import QObject, pyqtSignal, Qt, QThread

from src.config_manager import ConfigManager
from src.hotkey.listener import HotkeyListener
from src.capture.screen_grabber import ScreenGrabber
from src.ui.overlay_window import OverlayWindow
from src.ui.settings_dialog import SettingsDialog
from src.ui.editor_window import EditorWindow
from src.api.vision_client import VisionClient
from src.ui.prompt_dialog import PromptDialog
from src.ui.chat_window import ChatWindow
from src.ui.sessions_window import SessionsWindow
from src.api.ai_client import AIClient
from src.api.history_manager import HistoryManager

class VisionWorker(QThread):
    finished = pyqtSignal(str)
    
    def __init__(self, vision_client, base64_img, task_type="ocr", prompt=None):
        super().__init__()
        self.vision_client = vision_client
        self.base64_img = base64_img
        self.task_type = task_type
        self.prompt = prompt
        
    def run(self):
        if self.task_type == "ocr":
            text = self.vision_client.extract_text(self.base64_img)
        else:
            text = self.vision_client.analyze_image(self.base64_img, self.prompt)
        self.finished.emit(text)

class AppController(QObject):
    trigger_overlay = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.history_manager = HistoryManager()
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.vision_worker = None
        
        # Check permissions
        from src.ui.permissions_dialog import check_accessibility, check_screen_recording, PermissionsDialog
        if not check_accessibility(prompt_system=True) or not check_screen_recording(prompt_system=True):
            dialog = PermissionsDialog()
            dialog.exec()
            
        # We need a system tray icon
        self.tray = QSystemTrayIcon()
        # Create a simple icon for the tray
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.lightGray)
        self.tray.setIcon(QIcon(pixmap))
        print("Tray icon initialized (light gray square). Look for it near the clock!")
        
        self.menu = QMenu()
        
        self.action_screenshot = self.menu.addAction("Screenshot, OCR, or Vision")
        self.action_screenshot.triggered.connect(self.trigger_overlay.emit)
        self.menu.addSeparator()
        
        self.action_history = self.menu.addAction("Chat History")
        self.action_history.triggered.connect(self.show_history)
        
        self.action_settings = self.menu.addAction("Settings")
        self.action_settings.triggered.connect(self.show_settings)
        
        self.action_quit = self.menu.addAction("Quit")
        self.action_quit.triggered.connect(self.quit_app)
        
        self.tray.setContextMenu(self.menu)
        self.tray.show()
        
        self.hotkey_listener = HotkeyListener(
            combination=self.config.get("hotkey"),
            on_trigger=self.on_hotkey_triggered
        )
        self.hotkey_listener.start()
        
        self.overlay = None
        self.editor = None
        self.chat_window = None
        self.sessions_window = None
        self.trigger_overlay.connect(self.show_overlay)

    def on_hotkey_triggered(self):
        # We emit a signal to ensure UI stuff happens on the main thread
        self.trigger_overlay.emit()

    def show_overlay(self):
        if self.overlay:
            try:
                self.overlay.close()
            except:
                pass
            self.overlay = None
            
        print("Triggering overlay...")
        try:
            pixmap, screen = ScreenGrabber.capture_active_screen()
            if pixmap is None or pixmap.isNull():
                print("Error: Captured pixmap is null. Missing Screen Recording permissions?")
                return
                
            print(f"Captured screen {screen.name()} with geometry {screen.geometry()}")
            self.overlay = OverlayWindow(pixmap, screen.geometry(), self.config)
            self.overlay.selection_made.connect(self.process_selection)
            self.overlay.ai_selection_made.connect(lambda rect: self.process_ai_selection(rect, mode="ocr"))
            self.overlay.vision_selection_made.connect(self.process_vision_selection)
            self.overlay.ask_vision_selection_made.connect(lambda rect, p: self.process_ai_selection(rect, mode="vision", vision_prompt=p))
            self.overlay.cancelled.connect(self.close_overlay)
            self.overlay.show()
            self.overlay.activateWindow()
            self.overlay.raise_()
        except Exception as e:
            print(f"Error showing overlay: {e}")

    def close_overlay(self):
        if self.overlay:
            self.overlay.close()
            self.overlay = None

    def process_selection(self, rect):
        if not self.overlay: return
        
        # Crop the pixmap
        cropped = self.overlay.pixmap.copy(rect)
        self.close_overlay()
        
        # Convert to base64
        base64_img = ScreenGrabber.pixmap_to_base64(cropped)
        
        # Show editor immediately with a loading state
        if self.config.get("show_editor"):
            self.editor = EditorWindow("*Extracting text... please wait...*", self.config)
            self.editor.ask_ai_requested.connect(self.follow_up_with_ai)
            self.editor.show()
            
            # Disable buttons while loading
            self.editor.ask_ai_btn.setEnabled(False)
            self.editor.toggle_btn.setEnabled(False)
            self.editor.copy_btn.setEnabled(False)
        
        # Process OCR in background
        client = VisionClient(
            api_url=self.config.get("api_url"),
            model=self.config.get("model")
        )
        
        self.vision_worker = VisionWorker(client, base64_img, task_type="ocr")
        self.vision_worker.finished.connect(self.on_vision_finished)
        self.vision_worker.start()

    def process_vision_selection(self, rect, prompt):
        if not self.overlay: return
        
        cropped = self.overlay.pixmap.copy(rect)
        self.close_overlay()
        base64_img = ScreenGrabber.pixmap_to_base64(cropped)
        
        if self.config.get("show_editor"):
            self.editor = EditorWindow("*Analyzing image... please wait...*", self.config)
            self.editor.ask_ai_requested.connect(self.follow_up_with_ai)
            self.editor.show()
            
            self.editor.ask_ai_btn.setEnabled(False)
            self.editor.toggle_btn.setEnabled(False)
            self.editor.copy_btn.setEnabled(False)
        
        client = VisionClient(
            api_url=self.config.get("vision_api_url", self.config.get("api_url")),
            model=self.config.get("general_vision_model", "qwen2.5vl:3b")
        )
        
        self.vision_worker = VisionWorker(client, base64_img, task_type="vision", prompt=prompt)
        self.vision_worker.finished.connect(self.on_vision_finished)
        self.vision_worker.start()

    def on_vision_finished(self, text):
        if self.config.get("copy_to_clipboard"):
            pyperclip.copy(text)
            
        if self.config.get("show_editor") and self.editor:
            self.editor.set_text(text)
            self.editor.ask_ai_btn.setEnabled(True)
            self.editor.toggle_btn.setEnabled(True)
            self.editor.copy_btn.setEnabled(True)

    def follow_up_with_ai(self, context_text):
        # Show prompt dialog
        dialog = PromptDialog(pixmap=None)
        if dialog.exec():
            prompt = dialog.get_prompt()
            if not prompt: return
            
            # Init AI Client
            ai_client = AIClient(
                chat_api_url=self.config.get("ai_api_url"),
                vision_api_url=self.config.get("vision_api_url", self.config.get("ai_api_url")),
                vision_model=self.config.get("vision_model"),
                chat_model=self.config.get("chat_model"),
                general_vision_model=self.config.get("general_vision_model", "qwen2.5vl:3b")
            )
            
            # Show Chat Window
            self.chat_window = ChatWindow(ai_client, self.history_manager)
            self.chat_window.show()
            
            full_prompt = f"Here is context extracted from an image:\n\n{context_text}\n\nUser Question: {prompt}"
            self.chat_window.start_initial_request(full_prompt, None)

    def process_ai_selection(self, rect, mode="ocr", vision_prompt=None):
        if not self.overlay: return
        
        # Crop the pixmap
        cropped = self.overlay.pixmap.copy(rect)
        self.close_overlay()
        
        # Convert to base64
        base64_img = ScreenGrabber.pixmap_to_base64(cropped)
        
        # Show prompt dialog
        dialog = PromptDialog(pixmap=cropped)
        if dialog.exec():
            prompt = dialog.get_prompt()
            if not prompt: return
            
            # Init AI Client
            ai_client = AIClient(
                chat_api_url=self.config.get("ai_api_url"),
                vision_api_url=self.config.get("vision_api_url", self.config.get("ai_api_url")),
                vision_model=self.config.get("vision_model"),
                chat_model=self.config.get("chat_model"),
                general_vision_model=self.config.get("general_vision_model", "qwen2.5vl:3b")
            )
            
            # Show Chat Window
            self.chat_window = ChatWindow(ai_client, self.history_manager)
            self.chat_window.show()
            
            self.chat_window.worker = AIWorker(ai_client, prompt, is_initial=True, base64_image=base64_img, vision_task=mode, vision_prompt=vision_prompt)
            self.chat_window.worker.finished.connect(self.chat_window.on_response)
            self.chat_window.worker.text_extracted.connect(self.chat_window.on_text_extracted)
            self.chat_window.worker.chunk_received.connect(self.chat_window.on_chunk_received)
            
            # Setup UI state
            self.chat_window.last_user_prompt = prompt
            self.chat_window.last_base64_image = base64_img
            self.chat_window.is_streaming = False
            self.chat_window.current_stream_text = ""
            self.chat_window.current_vision_task = mode
            self.chat_window.current_vision_prompt = vision_prompt
            
            display_text = prompt
            img_html = f"<br><img src='data:image/png;base64,{base64_img}' style='max-width: 300px; max-height: 200px; border-radius: 6px; border: 1px solid #ccc; margin-top: 8px;'/>"
            display_text += img_html
            self.chat_window.append_message("You", display_text)
            self.chat_window.status_label.setText(f"Analyzing image with {'Vision' if mode == 'vision' else 'OCR'} model...")
            
            self.chat_window.input_field.setEnabled(False)
            self.chat_window.send_btn.setEnabled(False)
            self.chat_window.btn_attach.setEnabled(False)
            
            self.chat_window.worker.start()

    def show_history(self):
        self.sessions_window = SessionsWindow(self.history_manager, self.open_chat_session)
        self.sessions_window.show()
        self.sessions_window.raise_()
        self.sessions_window.activateWindow()
        
    def open_chat_session(self, session_id):
        ai_client = AIClient(
            chat_api_url=self.config.get("ai_api_url"),
            vision_api_url=self.config.get("vision_api_url", self.config.get("ai_api_url")),
            vision_model=self.config.get("vision_model"),
            chat_model=self.config.get("chat_model")
        )
        self.chat_window = ChatWindow(ai_client, self.history_manager, session_id=session_id)
        self.chat_window.show()
        self.chat_window.raise_()
        self.chat_window.activateWindow()

    def show_settings(self):
        self.settings_dialog = SettingsDialog(self.config, self.hotkey_listener)
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    def quit_app(self):
        self.hotkey_listener.stop()
        self.app.quit()

    def run(self):
        sys.exit(self.app.exec())

if __name__ == "__main__":
    controller = AppController()
    controller.run()
