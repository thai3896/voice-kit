import requests
import logging
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class AIClient:
    def __init__(self, chat_api_url, vision_api_url, vision_model, chat_model):
        self.chat_api_url = chat_api_url
        self.vision_api_url = vision_api_url
        self.vision_model = vision_model
        self.chat_model = chat_model
        self.messages = []

    def send_initial_request(self, prompt, base64_image):
        """
        Step 1: Extract text using Ollama Vision.
        Step 2: Send extracted text + prompt to Ollama Chat.
        """
        # 1. Ask Ollama Vision to extract the text
        vision_payload = {
            "model": self.vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract all text from this image."},
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
            return f"Failed to extract text from image.\n{extracted_text}"
            
        # 2. Build context for Ollama Chat
        chat_prompt = f"Here is the text extracted from an image by an OCR model:\n\n{extracted_text}\n\nUser Question: {prompt}"
        
        self.messages = [
            {"role": "user", "content": chat_prompt}
        ]
        
        chat_payload = {
            "model": self.chat_model,
            "messages": self.messages,
            "temperature": 0.2
        }
        
        # 3. Get answer from Ollama Chat
        answer = self._make_request(self.chat_api_url, chat_payload)
        
        # Save to history for follow-ups
        self.messages.append({"role": "assistant", "content": answer})
        
        return answer

    def send_followup_request(self, text_prompt, base64_image=None):
        """
        Sends a follow-up text request to the chat model with history.
        If a new base64_image is provided, it extracts the text via the vision model first.
        """
        if base64_image:
            # 1. Ask Vision model to extract text from the new attached image
            vision_payload = {
                "model": self.vision_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Extract all text from this image."},
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
                
            # 2. Build context for the chat model
            chat_prompt = f"Here is additional text extracted from a new image provided by the user:\n\n{extracted_text}\n\nUser Question: {text_prompt}"
            self.messages.append({"role": "user", "content": chat_prompt})
        else:
            self.messages.append({"role": "user", "content": text_prompt})
        
        payload = {
            "model": self.chat_model,
            "messages": self.messages,
            "temperature": 0.2
        }
        
        answer = self._make_request(self.chat_api_url, payload)
        self.messages.append({"role": "assistant", "content": answer})
        return answer

    def _make_request(self, url, payload):
        headers = {"Content-Type": "application/json"}
        try:
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
