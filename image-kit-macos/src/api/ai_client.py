import requests
import logging
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class AIClient:
    def __init__(self, chat_api_url, vision_api_url, vision_model, chat_model, general_vision_model="qwen2.5vl:3b"):
        self.chat_api_url = chat_api_url
        self.vision_api_url = vision_api_url
        self.vision_model = vision_model
        self.chat_model = chat_model
        self.general_vision_model = general_vision_model
        self.messages = []

    def send_initial_request(self, prompt, base64_image=None, on_text_extracted=None, on_chunk=None, vision_task="ocr", vision_prompt=None):
        """
        Step 1: Extract text or description using Vision model (if image provided).
        Step 2: Send prompt (and extracted text) to Chat model.
        """
        if base64_image:
            # 1. Ask Vision model to extract the text
            model_to_use = self.general_vision_model if vision_task == "vision" else self.vision_model
            default_prompt = "Extract all text from this image." if vision_task == "ocr" else "Analyze this image in detail."
            v_prompt = vision_prompt if vision_prompt else default_prompt
            
            vision_payload = {
                "model": model_to_use,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": v_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                "temperature": 0.1
            }
            
            # We don't stream the vision text extraction since it goes to the chat model context
            extracted_text = self._make_request(self.vision_api_url, vision_payload)
            if "Error:" in extracted_text:
                return f"Failed to extract text from image.\n{extracted_text}"
                
            if on_text_extracted:
                on_text_extracted(extracted_text)
                
            # 2. Build context for Chat model
            if vision_task == "vision":
                chat_prompt = f"Here is a detailed description of an image provided by a vision model:\n\n{extracted_text}\n\nUser Question: {prompt}"
            else:
                chat_prompt = f"Here is the text extracted from an image by an OCR model:\n\n{extracted_text}\n\nUser Question: {prompt}"
        else:
            chat_prompt = prompt
            
        self.messages = [
            {"role": "user", "content": chat_prompt}
        ]
        
        chat_payload = {
            "model": self.chat_model,
            "messages": self.messages,
            "temperature": 0.2
        }
        
        if on_chunk:
            chat_payload["stream"] = True
            
        # 3. Get answer from Ollama Chat
        answer = self._make_request(self.chat_api_url, chat_payload, on_chunk=on_chunk)
        
        # Save to history for follow-ups
        self.messages.append({"role": "assistant", "content": answer})
        
        return answer

    def send_followup_request(self, text_prompt, base64_image=None, on_text_extracted=None, on_chunk=None, vision_task="ocr", vision_prompt=None):
        """
        Sends a follow-up text request to the chat model with history.
        If a new base64_image is provided, it extracts the text via the vision model first.
        """
        if base64_image:
            # 1. Ask Vision model to extract text from the new attached image
            model_to_use = self.general_vision_model if vision_task == "vision" else self.vision_model
            default_prompt = "Extract all text from this image." if vision_task == "ocr" else "Analyze this image in detail."
            v_prompt = vision_prompt if vision_prompt else default_prompt
            
            vision_payload = {
                "model": model_to_use,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": v_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                "temperature": 0.1
            }
            
            extracted_text = self._make_request(self.vision_api_url, vision_payload)
            if "Error:" in extracted_text:
                return f"Failed to extract text from the new attached image.\n{extracted_text}"
                
            if on_text_extracted:
                on_text_extracted(extracted_text)
                
            # 2. Build context for the chat model
            if vision_task == "vision":
                chat_prompt = f"Here is additional detailed description of a new image provided by a vision model:\n\n{extracted_text}\n\nUser Question: {text_prompt}"
            else:
                chat_prompt = f"Here is additional text extracted from a new image provided by the user:\n\n{extracted_text}\n\nUser Question: {text_prompt}"
            
            self.messages.append({"role": "user", "content": chat_prompt})
        else:
            self.messages.append({"role": "user", "content": text_prompt})
        
        payload = {
            "model": self.chat_model,
            "messages": self.messages,
            "temperature": 0.2
        }
        
        if on_chunk:
            payload["stream"] = True
        
        answer = self._make_request(self.chat_api_url, payload, on_chunk=on_chunk)
        self.messages.append({"role": "assistant", "content": answer})
        return answer

    def _make_request(self, url, payload, on_chunk=None):
        headers = {"Content-Type": "application/json"}
        try:
            if on_chunk and payload.get("stream"):
                response = requests.post(url, headers=headers, json=payload, timeout=180, verify=False, stream=True)
                response.raise_for_status()
                
                full_text = ""
                import json
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith("data: "):
                            data_str = decoded_line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                if "choices" in data and len(data["choices"]) > 0:
                                    delta = data["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        full_text += content
                                        on_chunk(content)
                            except json.JSONDecodeError:
                                pass
                return full_text
            else:
                response = requests.post(url, headers=headers, json=payload, timeout=180, verify=False)
                response.raise_for_status()
                result = response.json()
                
                if "choices" in result and len(result["choices"]) > 0:
                    message = result["choices"][0].get("message", {})
                    return message.get("content", "").strip()
                return "Error: Unexpected API response format."
        except Exception as e:
            logging.error(f"AI API Error: {e}")
            return f"Error: {e}"
