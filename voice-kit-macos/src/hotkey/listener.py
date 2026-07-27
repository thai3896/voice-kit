import threading
import logging
import contextlib
from typing import Callable, Optional, List, Set, Any
from pynput import keyboard

# macOS 15 Sequoia (ARM64) Fix: TISGetInputSourceProperty & TISCopyCurrentKeyboardInputSource
# trigger dispatch_assert_queue(dispatch_get_main_queue()) if called from background threads.
# We warm up and cache the keycode context on the main thread at module import time,
# then replace pynput._util.darwin.keycode_context so background listener threads use the cache.
try:
    import sys
    if sys.platform == "darwin":
        import pynput._util.darwin as _darwin_util
        if hasattr(_darwin_util, 'keycode_context'):
            _orig_keycode_ctx = _darwin_util.keycode_context
            _cached_ctx = None
            try:
                with _orig_keycode_ctx() as _ctx:
                    _cached_ctx = _ctx
            except Exception as _ex:
                logging.warning(f"Main thread keycode_context warmup failed: {_ex}")
            
            @contextlib.contextmanager
            def _safe_keycode_ctx():
                yield _cached_ctx
            
            _darwin_util.keycode_context = _safe_keycode_ctx
except Exception as _e:
    logging.warning(f"Failed to apply macOS 15 keycode_context patch: {_e}")



class HotkeyListener:
    def __init__(self, combination: str = "right_fn", mode: str = "toggle"):
        self.combination = combination
        self.mode = mode.lower()
        self._listener: Optional[keyboard.Listener] = None
        self._recording_state = False
        self._combo_held = False
        self._lock = threading.RLock()
        self.on_start_callback: Optional[Callable[[], None]] = None
        self.on_stop_callback: Optional[Callable[[], None]] = None
        self.on_record_key_callback: Optional[Callable[[str], None]] = None
        self._pressed_keys: Set[Any] = set()
        self._tokens: List[str] = self._parse_tokens()

    def _parse_tokens(self) -> List[str]:
        # Parse strings like "<alt>+<space>", "right_fn", "<cmd_r>", "fn"
        raw = self.combination.replace('><', '>+<').replace(' + ', '+')
        parts = [p.strip('<> ').lower() for p in raw.split('+') if p.strip('<> ')]
        return parts or [self.combination.strip('<> ').lower()]

    def update_config(self, combination: str, mode: str) -> None:
        with self._lock:
            self.combination = combination
            self.mode = mode.lower()
            self._tokens = self._parse_tokens()

    def _is_key_match(self, key, token: str) -> bool:
        t = token.lower().strip('<> +')
        if not t:
            return False

        vk = getattr(key, 'vk', None)
        name = getattr(key, 'name', '').lower()
        key_str = str(key).lower().replace('key.', '')
        char = getattr(key, 'char', '')
        if char:
            char = char.lower()

        # Exact token match against string representation, name, char, or vk
        if t == key_str or t == name or t == char or t == str(vk) or t == f"<{vk}>":
            return True

        # Handle "right_fn", "fn", "globe", or right-side function/modifier mappings on Apple & external mechanical keyboards
        if t in ('right_fn', 'fn', 'r_fn', 'globe'):
            # On macOS Apple keyboards, Fn/Globe key is virtual keycode 63 (0x3f) or 179 (0xb3).
            # On external keyboards, Right Fn is often vk 179, 168, 255, 63, or mapped as alt_r / ctrl_r
            if vk in (63, 179, 168, 255, 9, 0x3f, 0xb3, 0x9):
                return True
            if name in ('fn', 'right_fn', 'globe'):
                return True
            if key_str in ('fn', 'right_fn', 'globe', '<63>', '<179>', '<168>', '<255>', '<9>', '◊'):
                return True
            if char in ('◊', 'fn', 'globe'):
                return True
            return False

        if t in ('alt_r', 'right_alt', 'right_option', 'ropt'):
            return name == 'alt_r' or key_str == 'alt_r' or vk == 61
        if t in ('cmd_r', 'right_cmd', 'right_command', 'rcmd'):
            return name == 'cmd_r' or key_str == 'cmd_r' or vk == 54
        if t in ('ctrl_r', 'right_ctrl', 'right_control', 'rctrl'):
            return name == 'ctrl_r' or key_str == 'ctrl_r'
        if t in ('shift_r', 'right_shift', 'rshift'):
            return name == 'shift_r' or key_str == 'shift_r'
        if t in ('alt', 'option'):
            return name in ('alt', 'alt_l', 'alt_r', 'alt_gr') or 'alt' in key_str
        if t in ('cmd', 'command'):
            return name in ('cmd', 'cmd_l', 'cmd_r') or 'cmd' in key_str
        if t in ('ctrl', 'control'):
            return name in ('ctrl', 'ctrl_l', 'ctrl_r') or 'ctrl' in key_str
        if t in ('shift'):
            return name in ('shift', 'shift_l', 'shift_r') or 'shift' in key_str

        return False

    def start(self, on_start: Callable[[], None], on_stop: Callable[[], None]) -> None:
        self.on_start_callback = on_start
        self.on_stop_callback = on_stop
        self._tokens = self._parse_tokens()
        logging.info(f"[Hotkey Listener] Started listening for '{self.combination}' (mode='{self.mode}')")
        
        # If listener is already active, do not stop/restart to prevent macOS GCD queue assertion crashes!
        if self._listener is not None and self._listener.is_alive():
            return
            
        self.stop()

        try:
            self._listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release
            )
            self._listener.start()
        except Exception as e:
            print(f"Error starting hotkey listener for '{self.combination}': {e}")

    def _is_combo_active(self) -> bool:
        for token in self._tokens:
            if not any(self._is_key_match(k, token) for k in self._pressed_keys):
                return False
        return True

    def _on_press(self, key):
        vk = getattr(key, 'vk', None)
        name = getattr(key, 'name', None)
        with self._lock:
            if self.on_record_key_callback:
                cb = self.on_record_key_callback
                self.on_record_key_callback = None
                key_str = str(key).replace('key.', '').replace('Key.', '').lower()
                if name:
                    res = name
                elif vk is not None:
                    res = f"<{vk}>"
                else:
                    res = key_str.strip("'")
                
                threading.Thread(target=cb, args=(res,), daemon=True).start()
                return

            self._pressed_keys.add(key)
            active = self._is_combo_active()
            
            if active:
                if self.mode == "toggle":
                    # Avoid OS key auto-repeat from rapidly toggling while key is held down
                    if not self._combo_held:
                        self._combo_held = True
                        current_state = not self._recording_state
                        if current_state:
                            res = None
                            if self.on_start_callback:
                                res = self.on_start_callback()
                            if res is False:
                                logging.debug("Combo triggered start, but callback returned False (ignored).")
                            else:
                                self._recording_state = True
                                logging.info("Hotkey combo triggered: recording started.")
                        else:
                            res = None
                            if self.on_stop_callback:
                                res = self.on_stop_callback()
                            if res is False:
                                logging.debug("Combo triggered stop, but callback returned False (ignored).")
                            else:
                                self._recording_state = False
                                logging.info("Hotkey combo triggered: recording stopped.")
                else:
                    # Hold / push-to-talk mode
                    if not self._recording_state:
                        res = None
                        if self.on_start_callback:
                            res = self.on_start_callback()
                        if res is False:
                            logging.debug("Hold mode triggered start, but callback returned False (ignored).")
                        else:
                            self._recording_state = True

    def _on_release(self, key):
        with self._lock:
            if key in self._pressed_keys:
                self._pressed_keys.remove(key)
            
            if not self._is_combo_active():
                self._combo_held = False
                if self.mode == "hold" and self._recording_state:
                    self._recording_state = False
                    if self.on_stop_callback:
                        self.on_stop_callback()

    def _on_toggle(self) -> None:
        with self._lock:
            current_state = not self._recording_state
            if current_state:
                res = None
                if self.on_start_callback:
                    res = self.on_start_callback()
                if res is False:
                    return
                self._recording_state = True
            else:
                res = None
                if self.on_stop_callback:
                    res = self.on_stop_callback()
                if res is False:
                    return
                self._recording_state = False

    def set_recording_state(self, is_recording: bool) -> None:
        with self._lock:
            self._recording_state = bool(is_recording)
            self._combo_held = False

    def stop(self) -> None:
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            finally:
                self._listener = None
