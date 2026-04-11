import httpx
import json
from fastapi import HTTPException
from app.core.config import settings

class AIAnalyzerClient:
    def __init__(self):
        # We strip quotes just in case they were accidentally loaded from the .env file
        self.ai_service_url = settings.AI_SERVICE_URL.strip('"').strip("'")
        self.ai_service_url_image = settings.AI_SERVICE_URL_IMAGE.strip('"').strip("'")

    def _extract_error_detail(self, response: httpx.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            body = None

        if isinstance(body, dict):
            detail_value = body.get("detail")
            if isinstance(detail_value, dict):
                return detail_value.get("detail") or json.dumps(detail_value)
            if isinstance(detail_value, str):
                try:
                    nested = json.loads(detail_value)
                    if isinstance(nested, dict) and nested.get("detail"):
                        return nested.get("detail")
                except (ValueError, TypeError):
                    pass
                return detail_value
            return json.dumps(body)

        if isinstance(response.text, str):
            try:
                nested = json.loads(response.text)
                if isinstance(nested, dict) and nested.get("detail"):
                    return nested.get("detail")
            except ValueError:
                pass

        return response.text

    async def analyze_barcode_image(self, image_bytes: bytes) -> dict:
        """Sends the real image file to the AI developer's service."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                files = {'file': ('barcode.jpg', image_bytes, 'image/jpeg')}
                
                # Make the REAL request to the exact Ngrok URL
                response = await client.post(self.ai_service_url_image, files=files)
                
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=self._extract_error_detail(response)
                    )
                
                return response.json()
            
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Could not connect to AI service: {e}")

    async def analyze_manual_isbn(self, isbn: str) -> dict:
        """Sends a real manually typed ISBN to the AI developer's service."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                
                # Make the REAL request to the exact Ngrok URL using JSON
                response = await client.post(self.ai_service_url, json={"isbn": isbn})

                if response.status_code != 200:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=self._extract_error_detail(response)
                    )
                
                return response.json()

        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Could not connect to AI service: {e}")

ai_client = AIAnalyzerClient()