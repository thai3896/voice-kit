import json
import os
import shutil
import threading
from datetime import datetime
from typing import List, Dict, Any


class HistoryManager:
    def __init__(self, file_path: str = "~/.voicekit/history.json", config_manager = None):
        self.file_path = os.path.expanduser(file_path)
        self.config_manager = config_manager
        self._lock = threading.RLock()
        self._migrate_old()
        self._ensure_dir()

    def get_max_limit(self) -> int:
        if self.config_manager:
            try:
                return int(self.config_manager.get("history.max_recordings", 100))
            except Exception:
                pass
        return 100

    def _migrate_old(self):
        try:
            old_path = os.path.expanduser("~/.gemini/antigravity/voicekit_history.json")
            if os.path.exists(old_path) and not os.path.exists(self.file_path):
                os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
                shutil.copy2(old_path, self.file_path)
        except Exception:
            pass

    def _ensure_dir(self):
        try:
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            if not os.path.exists(self.file_path):
                with open(self.file_path, "w", encoding="utf-8") as f:
                    json.dump([], f)
        except Exception as e:
            print(f"HistoryManager init error: {e}")

    def add_session(self, text: str, provider: str = "voice_editor", audio_path: str = None) -> None:
        if not text or not text.strip():
            return
        text = text.strip()
        with self._lock:
            max_limit = self.get_max_limit()
            sessions = self._get_recent_unlocked(limit=max_limit + 10)
            now = datetime.now()
            entry = {
                "id": now.strftime("%Y%m%d%H%M%S") + f"_{len(sessions)}",
                "timestamp": now.strftime("%H:%M"),
                "date": now.strftime("%b %d"),
                "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
                "text": text,
                "provider": provider,
                "preview": (text[:50] + "...") if len(text) > 50 else text,
                "audio_path": audio_path
            }
            sessions.insert(0, entry)
            if len(sessions) > max_limit:
                pruned = sessions[max_limit:]
                sessions = sessions[:max_limit]
                for p in pruned:
                    ap = p.get("audio_path")
                    if ap and os.path.exists(ap):
                        try:
                            os.remove(ap)
                        except Exception:
                            pass
            try:
                with open(self.file_path, "w", encoding="utf-8") as f:
                    json.dump(sessions, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"Error saving history session: {e}")

    def get_recent(self, limit: int = 30) -> List[Dict[str, Any]]:
        with self._lock:
            return self._get_recent_unlocked(limit)

    def search(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            sessions = self._get_recent_unlocked(limit=None)
            if not query or not query.strip():
                return sessions[:limit]
            q = query.strip().lower()
            results = []
            for s in sessions:
                text = s.get("text", "").lower()
                date = s.get("date", "").lower()
                provider = s.get("provider", "").lower()
                if q in text or q in date or q in provider:
                    results.append(s)
            return results[:limit]

    def delete_session(self, session_id: str) -> bool:
        with self._lock:
            sessions = self._get_recent_unlocked(limit=None)
            deleted = [s for s in sessions if str(s.get("id")) == str(session_id)]
            new_sessions = [s for s in sessions if str(s.get("id")) != str(session_id)]
            if len(new_sessions) == len(sessions):
                return False
            for d in deleted:
                ap = d.get("audio_path")
                if ap and os.path.exists(ap):
                    try:
                        os.remove(ap)
                    except Exception as e:
                        print(f"Error removing audio file {ap}: {e}")
            try:
                with open(self.file_path, "w", encoding="utf-8") as f:
                    json.dump(new_sessions, f, ensure_ascii=False, indent=2)
                return True
            except Exception as e:
                print(f"Error deleting session: {e}")
                return False

    def update_session_text(self, session_id: str, new_text: str) -> bool:
        if not new_text or not new_text.strip():
            return False
        with self._lock:
            sessions = self._get_recent_unlocked(limit=None)
            updated = False
            for s in sessions:
                if str(s.get("id")) == str(session_id):
                    s["text"] = new_text.strip()
                    s["preview"] = (new_text.strip()[:50] + "...") if len(new_text.strip()) > 50 else new_text.strip()
                    updated = True
                    break
            if not updated:
                return False
            try:
                with open(self.file_path, "w", encoding="utf-8") as f:
                    json.dump(sessions, f, ensure_ascii=False, indent=2)
                return True
            except Exception as e:
                print(f"Error updating session text: {e}")
                return False

    def _get_recent_unlocked(self, limit: int = None) -> List[Dict[str, Any]]:
        try:
            if not os.path.exists(self.file_path):
                return []
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    max_lim = self.get_max_limit()
                    if limit is None or limit <= 0:
                        return data[:max_lim]
                    return data[:limit]
        except Exception as e:
            print(f"Error reading history file: {e}")
        return []

    def clear_history(self) -> None:
        with self._lock:
            try:
                with open(self.file_path, "w", encoding="utf-8") as f:
                    json.dump([], f)
            except Exception:
                pass
