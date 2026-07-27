import ssl
import threading
import queue
import json
import time
from datetime import datetime
from typing import Callable, Optional, Dict
from websockets.sync.client import connect, ClientConnection
from .base import BaseTranscriptionProvider


class VoiceEditorProvider(BaseTranscriptionProvider):
    def __init__(self, url: str = "wss://voice-editor.minipc.na/ws/transcribe", do_cleanup: bool = True, language: str = "auto", headers: Optional[Dict[str, str]] = None):
        self.url = self._normalize_url(url)
        self.do_cleanup = do_cleanup
        self.language = language
        self.headers = headers or {}
        self._ws: Optional[ClientConnection] = None
        self._stream_thread: Optional[threading.Thread] = None
        self._stream_queue = queue.Queue()
        self._streaming_active = False
        self._stream_text_chunks = []
        self._on_partial_callback: Optional[Callable[[str], None]] = None

    def _normalize_url(self, url: str) -> str:
        url = url.strip()
        if url.startswith("http://"):
            url = "ws://" + url[7:]
        elif url.startswith("https://"):
            url = "wss://" + url[8:]
        
        url = url.rstrip('/')
        if '/ws/' not in url:
            url += '/ws/transcribe'
        return url

    def _get_ssl_kwargs(self, query_url: str) -> dict:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        kwargs = {}
        if query_url.startswith("wss://"):
            kwargs["ssl"] = ssl_context
        if self.headers:
            kwargs["additional_headers"] = self.headers
        return kwargs

    def start_stream(self, on_partial: Optional[Callable[[str], None]] = None) -> None:
        self._on_partial_callback = on_partial
        self._stream_text_chunks = []
        self._streaming_active = True
        self._stream_queue = queue.Queue()

        live_base_url = self.url.replace("/ws/transcribe", "/ws/live")
        if "/ws/live" not in live_base_url:
            live_base_url = live_base_url.rstrip("/") + "/ws/live"
        query_url = f"{live_base_url}?do_cleanup=false&language={self.language}"
        kwargs = self._get_ssl_kwargs(query_url)

        def _stream_worker():
            def _log(msg: str):
                ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                print(f"[{ts}] [Live Stream Debug] {msg}")

            _log(f"Starting stream worker for {query_url}...")
            # Text accumulated from previous socket sessions — shown as prefix in live box
            committed_text = ""

            while self._streaming_active:
                # Shared variable: receiver writes the latest partial; main thread reads on reconnect
                last_partial = [""]

                try:
                    _log(f"Connecting to {query_url}...")
                    with connect(query_url, **kwargs) as ws:
                        _log("Connected to /ws/live successfully!")
                        self._ws = ws

                        def _receiver(curr_ws, committed, last_partial_ref):
                            _log("Receiver thread started listening for messages...")
                            try:
                                for message in curr_ws:
                                    if isinstance(message, str):
                                        try:
                                            data = json.loads(message)
                                            if isinstance(data, dict) and data.get("type") in ("partial", "final"):
                                                text = data.get("text", "")
                                                _log(f"Received partial ({data.get('type')}): '{text}'")
                                                if text:
                                                    last_partial_ref[0] = text
                                                    # Prepend committed text from previous sockets
                                                    full_display = (committed + " " + text).strip() if committed else text
                                                    if self._on_partial_callback:
                                                        self._on_partial_callback(full_display)
                                            else:
                                                _log(f"Received unhandled JSON: {data}")
                                        except Exception as e:
                                            _log(f"Failed to parse JSON message: {e} -> {message[:100]}")
                                    elif isinstance(message, bytes):
                                        _log(f"Received binary frame ({len(message)} bytes)")
                            except Exception as e:
                                _log(f"Receiver loop ended ({e})")
                            finally:
                                _log("Receiver thread stopped.")

                        rx_thread = threading.Thread(target=_receiver, args=(ws, committed_text, last_partial), daemon=True)
                        rx_thread.start()

                        audio_buffer = bytearray()
                        frame_count = 0
                        while self._streaming_active:
                            try:
                                chunk = self._stream_queue.get(timeout=0.05)
                                if chunk == "STOP_STREAM":
                                    _log("Received STOP_STREAM command.")
                                    if audio_buffer:
                                        try:
                                            ws.send(bytes(audio_buffer))
                                        except Exception:
                                            pass
                                        audio_buffer.clear()
                                    last_partial[0] = ""
                                    break
                                elif chunk == "RESET_STREAM":
                                    _log("Received RESET_STREAM command. Clearing committed text and reconnecting...")
                                    committed_text = ""
                                    last_partial[0] = ""
                                    audio_buffer.clear()
                                    if self._on_partial_callback:
                                        self._on_partial_callback("")
                                    try:
                                        ws.close()
                                    except Exception:
                                        pass
                                    break
                                elif isinstance(chunk, bytes):
                                    audio_buffer.extend(chunk)
                                    # Buffer ~3200 bytes (200ms of audio at 16kHz int16) before sending
                                    if len(audio_buffer) >= 3200:
                                        ws.send(bytes(audio_buffer))
                                        frame_count += 1
                                        audio_buffer.clear()
                                        if frame_count % 10 == 0:
                                            _log(f"Sent {frame_count} buffered audio frames (~3200 bytes each = 200ms audio) to /ws/live...")
                            except queue.Empty:
                                if audio_buffer:
                                    try:
                                        ws.send(bytes(audio_buffer))
                                        frame_count += 1
                                        audio_buffer.clear()
                                    except Exception:
                                        break
                                continue
                            except Exception as send_err:
                                _log(f"Send error ({send_err}). Reconnecting...")
                                break

                    # Socket closed — save the last partial as committed text for next connection
                    if last_partial[0]:
                        committed_text = (committed_text + " " + last_partial[0]).strip() if committed_text else last_partial[0]
                        _log(f"Socket closed. Committed text so far: '{committed_text[:60]}...'")
                        last_partial[0] = ""

                except Exception as e:
                    if self._streaming_active:
                        _log(f"Live streaming WebSocket closed/error ({e}). Reconnecting in 0.5s...")
                        time.sleep(0.5)
            _log("_stream_worker terminated and socket closed.")
            self._ws = None

        self._stream_thread = threading.Thread(target=_stream_worker, daemon=True)
        self._stream_thread.start()

    def send_chunk(self, audio_chunk: bytes) -> None:
        if self._streaming_active and audio_chunk:
            self._stream_queue.put(audio_chunk)

    def reset_live_stream(self) -> None:
        if self._streaming_active:
            self._stream_queue.put("RESET_STREAM")

    def finish_stream(self, fallback_audio_bytes: bytes = b"") -> str:
        self._streaming_active = False
        self._stream_queue.put("STOP_STREAM")

        if self._stream_thread and self._stream_thread.is_alive():
            self._stream_thread.join(timeout=2.0)

        # For final AI copy-edited transcription, send complete WAV file to /ws/transcribe
        return self.transcribe_bytes(fallback_audio_bytes, self._on_partial_callback)

    def transcribe(self, audio_file_path: str, on_partial: Optional[Callable[[str], None]] = None) -> str:
        with open(audio_file_path, "rb") as f:
            audio_bytes = f.read()
        return self.transcribe_bytes(audio_bytes, on_partial)

    def transcribe_bytes(self, audio_bytes: bytes, on_partial: Optional[Callable[[str], None]] = None) -> str:
        query_url = f"{self.url}?do_cleanup={str(self.do_cleanup).lower()}&language={self.language}"
        kwargs = self._get_ssl_kwargs(query_url)

        full_text_chunks = []
        try:
            with connect(query_url, **kwargs) as ws:
                # 1. Send binary audio buffer
                ws.send(audio_bytes)
                # 2. Send STOP signal as text
                ws.send("STOP")

                # 3. Read incoming streamed text chunks
                for message in ws:
                    if isinstance(message, str):
                        if message == "[DONE]":
                            break
                        elif message.startswith(" [Error:"):
                            print(f"VoiceEditor API error: {message}")
                            break
                        else:
                            full_text_chunks.append(message)
                            if on_partial:
                                on_partial("".join(full_text_chunks))

            return "".join(full_text_chunks).strip()
        except Exception as e:
            print(f"Error connecting to VoiceEditor server ({query_url}): {e}")
            return f"[Transcription error: {e}]"

