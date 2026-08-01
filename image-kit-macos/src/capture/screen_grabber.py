import io
import mss
from PyQt6.QtGui import QGuiApplication, QCursor, QImage, QPixmap
from PyQt6.QtCore import QBuffer, QIODevice

class ScreenGrabber:
    @staticmethod
    def capture_active_screen():
        """
        Captures the screen where the mouse cursor is currently located.
        Returns the QPixmap of the screen and the QScreen object itself.
        """
        cursor_pos = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor_pos)
        
        if not screen:
            screen = QGuiApplication.primaryScreen()
            
        with mss.mss() as sct:
            # Find the monitor that contains the cursor
            monitor = None
            for m in sct.monitors[1:]:
                if m["left"] <= cursor_pos.x() < m["left"] + m["width"] and \
                   m["top"] <= cursor_pos.y() < m["top"] + m["height"]:
                    monitor = m
                    break
            
            if not monitor:
                monitor = sct.monitors[1]
                
            # Grab the raw bytes of the screen
            sct_img = sct.grab(monitor)
            
            # sct_img.bgra contains the B G R A bytes. 
            # In PyQt, QImage.Format.Format_RGB32 treats data as 32-bit ARGB (but little endian is BGRA)
            qim = QImage(sct_img.bgra, sct_img.width, sct_img.height, sct_img.width * 4, QImage.Format.Format_RGB32)
            pixmap = QPixmap.fromImage(qim)
            
            # Very important for macOS Retina displays:
            pixmap.setDevicePixelRatio(screen.devicePixelRatio())
            
        return pixmap, screen

    @staticmethod
    def pixmap_to_base64(pixmap, format="PNG"):
        """
        Converts a QPixmap to a base64 encoded string.
        """
        byte_array = QBuffer()
        byte_array.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap.save(byte_array, format)
        return byte_array.data().toBase64().data().decode("utf-8")
