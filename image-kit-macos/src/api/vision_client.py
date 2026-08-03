import requests
import json
import logging
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class VisionClient:
    def __init__(self, api_url, model):
        self.api_url = api_url
        self.model = model

    def extract_text(self, base64_image):
        """
        Sends the base64 encoded image to the VLLM endpoint.
        Uses the OvisOCR2 model for raw text extraction.
        """
        prompt = "Extract all text from this image. Output ONLY the raw text exactly as it appears in the image. Do not include any introductory words, explanations, or comments."
        return self._make_request(base64_image, prompt)
        
    def analyze_image(self, base64_image, prompt):
        """
        Sends the base64 encoded image to the VLLM endpoint with a custom vision prompt.
        """
        return self._make_request(base64_image, prompt)
        
    def _make_request(self, base64_image, prompt):
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
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
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=120, verify=False)
            response.raise_for_status()
            result = response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                message = result["choices"][0].get("message", {})
                return message.get("content", "").strip()
            return "Error: Unexpected API response format."
        except Exception as e:
            logging.error(f"Vision API Error: {e}")
            return f"Error: {e}"
