from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QPoint, QMetaObject, Qt, Q_ARG
from pynput import mouse

class GlobalMouseInterceptor(QObject):
    toggle_requested = pyqtSignal()
    ui_update_requested = pyqtSignal(object, object)
    inject_click_requested = pyqtSignal()
    inject_scroll_requested = pyqtSignal(float)
    
    def __init__(self, scroller, floating_button):
        super().__init__()
        self.scroller = scroller
        self.floating_button = floating_button
        self.active = False
        
        self.listener = None
        self.start_pos = None
        self.current_pos = None
        
        self.joystick_timer = QTimer(self)
        self.joystick_timer.timeout.connect(self._auto_scroll_tick)
        self.scroll_velocity = 0.0
        self.scroll_accumulator = 0.0
        self.joystick_sensitivity = 0.02
        
        self.inject_click_requested.connect(self._do_click)
        self.inject_scroll_requested.connect(self._do_scroll)
        
    def _do_click(self):
        self.scroller.mouse.click(mouse.Button.left)
        
    def _do_scroll(self, steps):
        self.scroller.scroll(steps)
        
    def set_active(self, active):
        self.active = active
        if active:
            self.listener = mouse.Listener(
                on_click=self.on_click,
                on_move=self.on_move,
                on_scroll=self.on_scroll,
                suppress=True
            )
            self.listener.start()
        else:
            if self.listener:
                self.listener.stop()
                self.listener = None
            self.joystick_timer.stop()
            self.scroll_velocity = 0.0
            self.ui_update_requested.emit(None, None)
            
    def _auto_scroll_tick(self):
        if self.scroll_velocity == 0:
            return
        self.scroll_accumulator += self.scroll_velocity
        if abs(self.scroll_accumulator) >= 1.0:
            steps = int(self.scroll_accumulator)
            self.scroll_accumulator -= steps
            self.scroller.scroll(steps)

    def is_in_button(self, x, y):
        rect = self.floating_button.geometry()
        return rect.contains(int(x), int(y))

    def on_click(self, x, y, button, pressed):
        if not self.active:
            return True
            
        if pressed:
            if self.is_in_button(x, y):
                self.toggle_requested.emit()
                return True
                
            self.start_pos = (x, y)
            self.current_pos = (x, y)
            self.scroll_velocity = 0.0
            self.scroll_accumulator = 0.0
            
            QMetaObject.invokeMethod(self.joystick_timer, "start", Qt.ConnectionType.QueuedConnection, Q_ARG(int, 50))
            
            self.ui_update_requested.emit(QPoint(int(x), int(y)), QPoint(int(x), int(y)))
        else:
            QMetaObject.invokeMethod(self.joystick_timer, "stop", Qt.ConnectionType.QueuedConnection)
            self.scroll_velocity = 0.0
            
            if self.start_pos:
                dist = abs(x - self.start_pos[0]) + abs(y - self.start_pos[1])
                if dist < 15:
                    # Defer click injection to main thread to prevent Event Tap deadlock
                    self.inject_click_requested.emit()
                    
            self.start_pos = None
            self.current_pos = None
            self.ui_update_requested.emit(None, None)

    def on_move(self, x, y):
        if not self.active or not self.start_pos:
            return True
            
        self.current_pos = (x, y)
        self.ui_update_requested.emit(
            QPoint(int(self.start_pos[0]), int(self.start_pos[1])), 
            QPoint(int(x), int(y))
        )
        
        dy = y - self.start_pos[1]
        if abs(dy) > 10:
            self.scroll_velocity = dy * self.joystick_sensitivity
        else:
            self.scroll_velocity = 0.0
            
    def on_scroll(self, x, y, dx, dy):
        if not self.active:
            return True
        # Defer physical scroll forwarding to main thread
        self.inject_scroll_requested.emit(float(dy))
