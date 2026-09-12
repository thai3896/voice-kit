import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QGuiApplication
from src.ui.floating_button import FloatingButton
from src.ui.scroll_overlay import ScrollOverlay
from src.core.scroller import Scroller
from src.core.interceptor import GlobalMouseInterceptor

class ScreenKitApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        
        self.scroller = Scroller()
        self.overlays = []
        
        # 1. Create the floating button first so we can pass it to interceptor
        self.floating_button = FloatingButton()
        self.floating_button.toggled.connect(self.set_scroll_mode)
        
        # 2. Create the global interceptor
        self.interceptor = GlobalMouseInterceptor(self.scroller, self.floating_button)
        self.interceptor.toggle_requested.connect(self.floating_button.toggle_state)
        self.interceptor.ui_update_requested.connect(self.update_overlays_ui)
        
        # 3. Create invisible overlays (one per monitor) for drawing
        self.create_overlays()
        
        self.floating_button.show()
        
    def create_overlays(self):
        # Create one overlay per monitor to handle separate screen drawing correctly
        for screen in QGuiApplication.screens():
            overlay = ScrollOverlay()
            # Position it to cover exactly this monitor
            overlay.setGeometry(screen.geometry())
            self.overlays.append(overlay)
            
    def update_overlays_ui(self, start_pos_global, current_pos_global):
        for overlay in self.overlays:
            overlay.update_ui(start_pos_global, current_pos_global)
            
    def set_scroll_mode(self, active: bool):
        print(f"[FloatingButton] Scroll mode active: {active}")
        
        # Tell the global interceptor to start/stop the pynput background listener
        self.interceptor.set_active(active)
        
        if active:
            for overlay in self.overlays:
                overlay.show()
            self.floating_button.raise_()
            self.floating_button.activateWindow()
        else:
            for overlay in self.overlays:
                overlay.hide()
            
    def run(self):
        return self.app.exec()

if __name__ == "__main__":
    print("Starting Screen Kit App...")
    app = ScreenKitApp()
    sys.exit(app.run())
