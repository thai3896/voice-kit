import os
import sys
import ctypes
import ctypes.util
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFrame, QApplication, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor


def check_accessibility(prompt_system: bool = False) -> bool:
    """
    Checks if the current process is trusted for macOS Accessibility (input event monitoring).
    Uses clean AXIsProcessTrusted() without pointer dictionary options to guarantee zero crash risk on ARM64.
    """
    if sys.platform != "darwin":
        return True
    try:
        app_services_path = ctypes.util.find_library('ApplicationServices')
        if not app_services_path:
            return True
        app_services = ctypes.cdll.LoadLibrary(app_services_path)
        app_services.AXIsProcessTrusted.argtypes = []
        app_services.AXIsProcessTrusted.restype = ctypes.c_bool
        return app_services.AXIsProcessTrusted()
    except Exception as e:
        print(f"Error checking accessibility: {e}")
        return False


class PermissionsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔐 Accessibility Permission Required")
        self.setFixedSize(520, 420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e24;
                color: #ffffff;
            }
            QLabel {
                color: #e0e0e0;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            }
            QPushButton {
                background-color: #2d2d3a;
                border: 1px solid #3d3d4e;
                border-radius: 6px;
                color: #ffffff;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3a3a4c;
                border-color: #505068;
            }
            QPushButton#primary_btn {
                background-color: #0066cc;
                border-color: #0077ee;
            }
            QPushButton#primary_btn:hover {
                background-color: #0077ee;
                border-color: #2288ff;
            }
            QPushButton#secondary_btn {
                background-color: transparent;
                border: 1px solid transparent;
                color: #aaaaaa;
            }
            QPushButton#secondary_btn:hover {
                color: #ffffff;
                text-decoration: underline;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        header_label = QLabel("🔐 Accessibility Permission Needed")
        header_font = QFont()
        header_font.setPointSize(18)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet("color: #ffffff;")
        layout.addWidget(header_label)

        # Explanation
        desc_label = QLabel(
            "VoiceKit needs macOS Accessibility permission to listen for your global shortcut key "
            "(like <b>Right Fn</b> or <b>Right Ctrl</b>) across different applications."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("font-size: 14px; line-height: 1.4;")
        layout.addWidget(desc_label)

        # Why is it not asking / already blue?
        box_frame = QFrame()
        box_frame.setStyleSheet("""
            QFrame {
                background-color: #282834;
                border: 1px solid #3d3d4e;
                border-radius: 8px;
            }
        """)
        box_layout = QVBoxLayout(box_frame)
        box_layout.setContentsMargins(16, 16, 16, 16)
        box_layout.setSpacing(8)

        steps_label = QLabel(
            "<b>Why didn't macOS prompt me, or why is VoiceKit already enabled in System Settings?</b><br><br>"
            "When an app bundle is re-built or updated, macOS invalidates the binary security signature. "
            "macOS silently blocks hotkeys in the background even if the switch still looks checked (blue).<br><br>"
            "<b>How to grant permission:</b><br>"
            "1. Click <b>Open System Settings</b> below.<br>"
            "2. In Accessibility, select <b>VoiceKit</b> (or iTerm/Terminal) and click <b><code>&nbsp;-&nbsp;</code> (minus)</b> to remove it.<br>"
            "3. Click <b><code>&nbsp;+&nbsp;</code> (plus)</b> and select your newly built <b>VoiceKit.app</b>.<br>"
            "4. Click <b>Check Permission Again</b> below."
        )
        steps_label.setWordWrap(True)
        steps_label.setStyleSheet("font-size: 13px; color: #cccccc; border: none;")
        box_layout.addWidget(steps_label)
        layout.addWidget(box_frame)

        layout.addStretch()

        # Status indicator
        self.status_label = QLabel("⚠️ Permission currently revoked or missing.")
        self.status_label.setStyleSheet("color: #ffaa00; font-weight: bold; font-size: 13px;")
        layout.addWidget(self.status_label)

        # Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_open_settings = QPushButton("⚙️ Open System Settings")
        self.btn_open_settings.setObjectName("primary_btn")
        self.btn_open_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_settings.clicked.connect(self.open_system_settings)
        btn_layout.addWidget(self.btn_open_settings)

        self.btn_check_again = QPushButton("🔄 Check Permission Again")
        self.btn_check_again.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_check_again.clicked.connect(self.on_check_again)
        btn_layout.addWidget(self.btn_check_again)

        layout.addLayout(btn_layout)

        # Continue without hotkey
        self.btn_continue = QPushButton("Continue Without Hotkey →")
        self.btn_continue.setObjectName("secondary_btn")
        self.btn_continue.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_continue.clicked.connect(self.accept)
        layout.addWidget(self.btn_continue, alignment=Qt.AlignmentFlag.AlignCenter)

        # Timer to auto-detect permission while dialog is open
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.auto_check)
        self.timer.start(1500)

    def open_system_settings(self):
        os.system('open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"')

    def auto_check(self):
        if check_accessibility():
            self.status_label.setText("✅ Permission Granted! You can close this dialog.")
            self.status_label.setStyleSheet("color: #00ff66; font-weight: bold; font-size: 13px;")

    def on_check_again(self):
        if check_accessibility():
            QMessageBox.information(self, "Permission Granted", "macOS Accessibility permission is active! Your hotkeys will work now.")
            self.accept()
        else:
            QMessageBox.warning(
                self, "Still Revoked", 
                "macOS still reports this process as untrusted.\n\n"
                "Remember: If VoiceKit is already checked in System Settings, you MUST select it, click '-' to remove it, and click '+' to re-add the new VoiceKit.app bundle."
            )
