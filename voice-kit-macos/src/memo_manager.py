import os
import json
import shutil
import wave
from datetime import datetime
from pathlib import Path


class MemoManager:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.folder_path = ""
        self._ensure_dir()

    def _ensure_dir(self):
        folder_setting = self.config_manager.get("voice_memo_folder", "~/.voicekit/memos")
        self.folder_path = os.path.expanduser(folder_setting)
        os.makedirs(self.folder_path, exist_ok=True)

    def list_memos(self):
        self._ensure_dir()
        memos = []
        for file in os.listdir(self.folder_path):
            if file.endswith(".wav"):
                full_path = os.path.join(self.folder_path, file)
                base_name = os.path.splitext(file)[0]
                
                # Get modified time
                mtime = os.path.getmtime(full_path)
                created_at = datetime.fromtimestamp(mtime)
                
                # Get duration
                duration = 0.0
                try:
                    with wave.open(full_path, "r") as wf:
                        frames = wf.getnframes()
                        rate = wf.getframerate()
                        duration = frames / float(rate)
                except Exception:
                    pass
                
                # Check for transcripts
                txt_path = os.path.join(self.folder_path, f"{base_name}.txt")
                json_path = os.path.join(self.folder_path, f"{base_name}.json")
                
                has_refined = os.path.exists(txt_path)
                has_timestamped = os.path.exists(json_path)
                
                memos.append({
                    "id": base_name,
                    "title": base_name,
                    "file_path": full_path,
                    "created_at": created_at,
                    "duration": duration,
                    "has_refined": has_refined,
                    "has_timestamped": has_timestamped,
                    "txt_path": txt_path if has_refined else None,
                    "json_path": json_path if has_timestamped else None
                })
                
        # Sort newest first
        memos.sort(key=lambda x: x["created_at"], reverse=True)
        return memos

    def rename_memo(self, old_id, new_title):
        self._ensure_dir()
        if old_id == new_title:
            return True
            
        old_wav = os.path.join(self.folder_path, f"{old_id}.wav")
        new_wav = os.path.join(self.folder_path, f"{new_title}.wav")
        
        # Avoid overwriting existing files
        if os.path.exists(new_wav):
            return False
            
        if os.path.exists(old_wav):
            os.rename(old_wav, new_wav)
            
            # Rename associated text if exists
            old_txt = os.path.join(self.folder_path, f"{old_id}.txt")
            if os.path.exists(old_txt):
                os.rename(old_txt, os.path.join(self.folder_path, f"{new_title}.txt"))
                
            # Rename associated json if exists
            old_json = os.path.join(self.folder_path, f"{old_id}.json")
            if os.path.exists(old_json):
                os.rename(old_json, os.path.join(self.folder_path, f"{new_title}.json"))
            return True
        return False

    def delete_memo(self, memo_id):
        self._ensure_dir()
        wav = os.path.join(self.folder_path, f"{memo_id}.wav")
        txt = os.path.join(self.folder_path, f"{memo_id}.txt")
        jsn = os.path.join(self.folder_path, f"{memo_id}.json")
        
        deleted = False
        if os.path.exists(wav):
            os.remove(wav)
            deleted = True
        if os.path.exists(txt):
            os.remove(txt)
        if os.path.exists(jsn):
            os.remove(jsn)
            
        return deleted

    def save_new_memo(self, temp_wav_path, desired_title=None):
        self._ensure_dir()
        if not desired_title:
            desired_title = f"New Recording {datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
        target_path = os.path.join(self.folder_path, f"{desired_title}.wav")
        shutil.copy2(temp_wav_path, target_path)
        return desired_title

    def update_memo_audio(self, memo_id, temp_wav_path):
        self._ensure_dir()
        target_path = os.path.join(self.folder_path, f"{memo_id}.wav")
        shutil.copy2(temp_wav_path, target_path)
        
        # Invalidate old transcripts
        txt = os.path.join(self.folder_path, f"{memo_id}.txt")
        jsn = os.path.join(self.folder_path, f"{memo_id}.json")
        if os.path.exists(txt):
            os.remove(txt)
        if os.path.exists(jsn):
            os.remove(jsn)
        return memo_id
