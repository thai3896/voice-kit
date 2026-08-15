import json
import urllib.request
import ssl
import uuid
from typing import Optional

ssl._create_default_https_context = ssl._create_unverified_context

class OpenClawClient:
    def __init__(self, url: str, token: str, model: str = "openclaw/voice-kit"):
        self.url = url
        self.token = token
        self.model = model
        self.session_id = str(uuid.uuid4())

    def clear_history(self):
        # OpenClaw maintains history natively based on the session ID. 
        # Generating a new UUID creates a fresh session.
        self.session_id = str(uuid.uuid4())

    def ask(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
            
        # We only send the latest prompt. OpenClaw manages the rolling history internally 
        # based on the `user` parameter / session key.
        messages.append({"role": "user", "content": prompt})

        data = json.dumps({
            "model": self.model,
            "messages": messages,
            "max_tokens": 1024,
            "user": f"conv:{self.session_id}",
            "chat_id": self.session_id,      # For Open WebUI compat
            "session_id": self.session_id    # For LibreChat compat
        }).encode("utf-8")

        req = urllib.request.Request(self.url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {self.token}")

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
                answer = result["choices"][0]["message"]["content"]
                return answer
        except Exception as e:
            print(f"OpenClaw Error: {e}")
            if hasattr(e, 'read'):
                print(e.read().decode("utf-8"))
            return f"Error connecting to OpenClaw: {str(e)}"
