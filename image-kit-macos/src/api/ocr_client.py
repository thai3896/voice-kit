import requests
import json
import logging
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class OCRClient:
    def __init__(self, api_url, model):
        self.api_url = api_url
        self.model = model

    def extract_text(self, base64_image):
        """
        Sends the base64 encoded image to the VLLM OpenAI-compatible endpoint.
        Uses the OvisOCR2 model.
        """
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract all text from this image. Output ONLY the raw text exactly as it appears in the image. Do not include any introductory words, explanations, or comments."},
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
        
        headers = {
            "Content-Type": "application/json"
        }

        try:
            # We explicitly ignore SSL verification if using a local domain that might have self-signed certs
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=120, verify=False)
            response.raise_for_status()
            result = response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                message = result["choices"][0].get("message", {})
                return message.get("content", "").strip()
            return "Error: Unexpected API response format."
        except Exception as e:
            logging.error(f"OCR API Error: {e}")
            return f"Error: {e}"
