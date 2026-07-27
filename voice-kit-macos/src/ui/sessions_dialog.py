import pyperclip
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton,
    QSplitter, QMessageBox, QWidget, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from src.history_manager import HistoryManager


class SessionsDialog(QDialog):
    signal_open_in_editor = pyqtSignal(dict)

    def __init__(self, history_mgr: HistoryManager, parent=None):
        super().__init__(parent)
        self.history_mgr = history_mgr
        self.current_session = None
        self._drag_pos = None
        self._init_ui()
        self.refresh_sessions()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def _init_ui(self):
        self.setWindowTitle("Sessions History & Search — VoiceKit")
        self.setMinimumSize(780, 520)
        self.setWindowFlags(Qt.WindowType.Window)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        self.setStyleSheet("""
            QDialog {
                background-color: #1e272e;
            }
            QLabel {
                color: #f1f2f6;
                font-family: '.AppleSystemUIFont', -apple-system, sans-serif;
                font-size: 14px;
                font-weight: 600;
            }
            QLineEdit {
                background-color: rgba(15, 15, 20, 0.6);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #70a1ff;
            }
            QListWidget {
                background-color: rgba(15, 15, 20, 0.4);
                color: #ced6e0;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                padding: 6px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 6px;
                margin-bottom: 4px;
            }
            QListWidget::item:hover {
                background-color: rgba(255, 255, 255, 0.08);
            }
            QListWidget::item:selected {
                background-color: rgba(112, 161, 255, 0.25);
                color: #ffffff;
                font-weight: 700;
            }
            QPlainTextEdit {
                background-color: rgba(15, 15, 20, 0.6);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
                line-height: 1.4;
            }
            QPushButton {
                font-family: '.AppleSystemUIFont', -apple-system, sans-serif;
                font-size: 13px;
                font-weight: 600;
                padding: 8px 14px;
                border-radius: 8px;
                border: none;
            }
            QPushButton#btnOpen {
                background-color: #3742fa;
                color: #ffffff;
                font-weight: 700;
            }
            QPushButton#btnOpen:hover {
                background-color: #5352ed;
            }
            QPushButton#btnCopy {
                background-color: rgba(112, 161, 255, 0.2);
                color: #70a1ff;
                border: 1px solid rgba(112, 161, 255, 0.4);
            }
            QPushButton#btnCopy:hover {
                background-color: rgba(112, 161, 255, 0.35);
            }
            QPushButton#btnDelete {
                background-color: rgba(255, 71, 87, 0.2);
                color: #ff4757;
            }
            QPushButton#btnDelete:hover {
                background-color: rgba(255, 71, 87, 0.35);
            }
            QPushButton#btnClear {
                background-color: rgba(255, 255, 255, 0.08);
                color: #ced6e0;
            }
            QPushButton#btnClear:hover {
                background-color: rgba(255, 255, 255, 0.18);
            }
        """)

        # Search bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search sessions by keyword, date, or provider...")
        self.search_input.textChanged.connect(self._on_search_changed)
        main_layout.addWidget(self.search_input)

        # Splitter for list and preview
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background-color: rgba(255, 255, 255, 0.08); width: 1px; }")

        # Left side: List widget
        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._on_item_selected)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        splitter.addWidget(self.list_widget)

        # Right side: Preview and actions
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(18, 0, 0, 0)

        lbl_preview = QLabel("📝 Full Document Preview:")
        right_layout.addWidget(lbl_preview)

        self.preview_text = QPlainTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText("Select a session on the left to preview its full text...")
        right_layout.addWidget(self.preview_text)

        # Actions bar
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)

        self.btn_copy = QPushButton("📋 Copy Text")
        self.btn_copy.setObjectName("btnCopy")
        self.btn_copy.setEnabled(False)
        self.btn_copy.clicked.connect(self._on_copy_clicked)
        action_layout.addWidget(self.btn_copy)

        self.btn_open = QPushButton("📂 Open in Editor")
        self.btn_open.setObjectName("btnOpen")
        self.btn_open.setEnabled(False)
        self.btn_open.clicked.connect(self._on_open_clicked)
        action_layout.addWidget(self.btn_open)

        self.btn_delete = QPushButton("🗑️ Delete")
        self.btn_delete.setObjectName("btnDelete")
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        action_layout.addWidget(self.btn_delete)

        right_layout.addLayout(action_layout)
        splitter.addWidget(right_panel)

        # Set splitter ratio (40% left list, 60% right preview)
        splitter.setSizes([300, 480])
        main_layout.addWidget(splitter)

        # Bottom bar
        bottom_layout = QHBoxLayout()
        self.lbl_count = QLabel("Total Sessions: 0")
        self.lbl_count.setStyleSheet("color: #a4b0be; font-weight: normal; font-size: 12px;")
        bottom_layout.addWidget(self.lbl_count)
        bottom_layout.addStretch()

        self.btn_clear_all = QPushButton("🧹 Clear All History")
        self.btn_clear_all.setObjectName("btnClear")
        self.btn_clear_all.clicked.connect(self._on_clear_all_clicked)
        bottom_layout.addWidget(self.btn_clear_all)

        main_layout.addLayout(bottom_layout)

    def refresh_sessions(self, query: str = ""):
        self.list_widget.clear()
        self.preview_text.clear()
        self.current_session = None
        self.btn_copy.setEnabled(False)
        self.btn_open.setEnabled(False)
        self.btn_delete.setEnabled(False)
        self.btn_copy.setText("📋 Copy Text")

        sessions = self.history_mgr.search(query, limit=100)
        self.lbl_count.setText(f"Total Sessions: {len(sessions)}")

        for s in sessions:
            date_str = f"{s.get('date', '')} {s.get('timestamp', '')}"
            preview = s.get("preview", "")
            item = QListWidgetItem(f"[{date_str}] {preview}")
            item.setData(Qt.ItemDataRole.UserRole, s)
            self.list_widget.addItem(item)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _on_search_changed(self, text: str):
        self.refresh_sessions(text)

    def _on_item_selected(self, current: QListWidgetItem, previous: QListWidgetItem):
        if not current:
            return
        data = current.data(Qt.ItemDataRole.UserRole)
        if data and isinstance(data, dict):
            self.current_session = data
            self.preview_text.setPlainText(data.get("text", ""))
            self.btn_copy.setEnabled(True)
            self.btn_open.setEnabled(True)
            self.btn_delete.setEnabled(True)
            self.btn_copy.setText("📋 Copy Text")

    def _on_item_double_clicked(self, item: QListWidgetItem):
        self._on_open_clicked()

    def _on_copy_clicked(self):
        if self.current_session:
            text = self.current_session.get("text", "")
            if text:
                pyperclip.copy(text)
                self.btn_copy.setText("✓ Copied!")

    def _on_open_clicked(self):
        if self.current_session:
            self.signal_open_in_editor.emit(self.current_session)
            self.accept()

    def _on_delete_clicked(self):
        if not self.current_session:
            return
        session_id = self.current_session.get("id")
        if session_id:
            self.history_mgr.delete_session(session_id)
            self.refresh_sessions(self.search_input.text())

    def _on_clear_all_clicked(self):
        reply = QMessageBox.question(
            self, "Clear All History",
            "Are you sure you want to delete all saved sessions? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.history_mgr.clear_history()
            self.refresh_sessions(self.search_input.text())
