import os
import sys
import logging
import builtins
from datetime import datetime

LOG_FILE_PATH = os.path.expanduser("~/.voicekit/voicekit.log")

def setup_logging():
    try:
        os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
        
        # Configure root logger
        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s] [%(levelname)s] [%(threadName)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            handlers=[
                logging.FileHandler(LOG_FILE_PATH, encoding="utf-8"),
                logging.StreamHandler(sys.stdout)
            ]
        )

        # Intercept builtins.print so all print() calls across all modules are logged automatically
        _original_print = builtins.print
        def _logged_print(*args, **kwargs):
            msg = " ".join(str(a) for a in args)
            logging.info(msg)
        builtins.print = _logged_print

        # Intercept uncaught exceptions
        def _excepthook(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
            logging.critical("Uncaught application exception:", exc_info=(exc_type, exc_value, exc_traceback))
            try:
                _original_print(f"CRITICAL ERROR: {exc_value}", file=sys.stderr)
            except Exception:
                pass
        sys.excepthook = _excepthook

        print(f"--- VoiceKit Logger Initialized: {LOG_FILE_PATH} ---")
    except Exception as e:
        sys.stderr.write(f"Failed to setup logging: {e}\n")
