import sqlite3
import os
import uuid
import base64
from datetime import datetime

class HistoryManager:
    def __init__(self, db_path="~/.imagekit/history.db"):
        self.db_path = os.path.expanduser(db_path)
        self.img_dir = os.path.join(os.path.dirname(self.db_path), "images")
        
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.img_dir, exist_ok=True)
        
        self._init_db()
        
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT,
                    created_at DATETIME,
                    updated_at DATETIME
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    role TEXT,
                    text_content TEXT,
                    image_path TEXT,
                    timestamp DATETIME,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                )
            ''')
            conn.commit()
            
    def create_session(self, title="New Chat"):
        session_id = str(uuid.uuid4())
        now = datetime.now()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO sessions (session_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (session_id, title, now, now)
            )
            conn.commit()
        return session_id
        
    def add_message(self, session_id, role, text_content, base64_image=None):
        image_path = None
        if base64_image:
            image_filename = f"{uuid.uuid4()}.png"
            image_path = os.path.join(self.img_dir, image_filename)
            try:
                img_data = base64.b64decode(base64_image)
                with open(image_path, "wb") as f:
                    f.write(img_data)
            except Exception as e:
                print(f"Error saving image: {e}")
                image_path = None
                
        now = datetime.now()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO messages (session_id, role, text_content, image_path, timestamp) VALUES (?, ?, ?, ?, ?)",
                (session_id, role, text_content, image_path, now)
            )
            cursor.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (now, session_id)
            )
            conn.commit()
            
    def get_all_sessions(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.*, 
                       (SELECT image_path FROM messages m WHERE m.session_id = s.session_id AND image_path IS NOT NULL ORDER BY timestamp ASC LIMIT 1) as preview_image
                FROM sessions s 
                ORDER BY updated_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
            
    def get_session_messages(self, session_id):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp ASC", (session_id,))
            return [dict(row) for row in cursor.fetchall()]
            
    def delete_session(self, session_id):
        messages = self.get_session_messages(session_id)
        for msg in messages:
            if msg.get('image_path') and os.path.exists(msg['image_path']):
                try:
                    os.remove(msg['image_path'])
                except:
                    pass
                    
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.commit()
