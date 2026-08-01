import threading
import contextlib
import logging

try:
    import sys
    if sys.platform == "darwin":
        import pynput._util.darwin as _darwin_util
        if hasattr(_darwin_util, 'keycode_context'):
            # Instead of exiting the context manager, we keep the generator alive
            # so the CFRelease is never called, keeping the pointer valid for the app's lifetime.
            _orig_keycode_ctx = _darwin_util.keycode_context
            _ctx_generator = _orig_keycode_ctx()
            _cached_ctx = _ctx_generator.__enter__()

            @contextlib.contextmanager
            def _safe_keycode_ctx():
                yield _cached_ctx
            
            _darwin_util.keycode_context = _safe_keycode_ctx
            
            # Also patch the keyboard specific darwin module in case it was already imported
            try:
                import pynput.keyboard._darwin as _kbd_darwin
                _kbd_darwin.keycode_context = _safe_keycode_ctx
            except ImportError:
                pass
except Exception as _e:
    logging.warning(f"Failed to apply macOS 15 keycode_context patch: {_e}")

from pynput import keyboard

class HotkeyListener:
    def __init__(self, combination="cmd+shift+2", on_trigger=None):
        self.combination = combination
        self.on_trigger = on_trigger
        self._listener = None
        
    def _parse_combination(self):
        parts = self.combination.lower().split('+')
        keys = set()
        for p in parts:
            p = p.strip()
            if p == 'cmd' or p == 'command':
                keys.add(keyboard.Key.cmd)
            elif p == 'shift':
                keys.add(keyboard.Key.shift)
            elif p == 'ctrl' or p == 'control':
                keys.add(keyboard.Key.ctrl)
            elif p == 'alt' or p == 'option':
                keys.add(keyboard.Key.alt)
            elif p == 'right_ctrl':
                keys.add(keyboard.Key.ctrl_r)
            elif p == 'right_fn':
                # Not easily detectable in pynput without carbon APIs, but we handle typical ones
                keys.add(keyboard.Key.cmd_r)
            else:
                # normal char
                if len(p) == 1:
                    keys.add(keyboard.KeyCode.from_char(p))
                elif hasattr(keyboard.Key, p):
                    keys.add(getattr(keyboard.Key, p))
                else:
                    try:
                        # try to parse as vk
                        if p.startswith('vk'):
                            keys.add(keyboard.KeyCode.from_vk(int(p[2:])))
                    except:
                        pass
        return keys

    def start(self):
        target_keys = self._parse_combination()
        if not target_keys:
            logging.error(f"Failed to parse hotkey combination: {self.combination}")
            return
            
        current_keys = set()

        def on_press(key):
            if getattr(self, 'on_record_key_callback', None):
                name = getattr(key, 'name', None)
                vk = getattr(key, 'vk', None)
                key_str = str(key).replace('key.', '').replace('Key.', '').lower()
                if name:
                    res = name
                elif vk is not None:
                    res = f"<{vk}>"
                else:
                    res = key_str.strip("'")
                
                cb = self.on_record_key_callback
                self.on_record_key_callback = None
                cb(res)
                return

            if key in target_keys:
                current_keys.add(key)
                if all(k in current_keys for k in target_keys):
                    if self.on_trigger:
                        self.on_trigger()
                        
        def on_release(key):
            try:
                current_keys.remove(key)
            except KeyError:
                pass

        self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self._listener.start()

    def stop(self):
        if self._listener:
            self._listener.stop()
            self._listener = None

    def update_hotkey(self, new_combination):
        self.stop()
        self.combination = new_combination
        self.start()
