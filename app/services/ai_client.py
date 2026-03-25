import httpx
from fastapi import HTTPException
from app.core.config import settings

class AIAnalyzerClient:
    def __init__(self):
        # We strip quotes just in case they were accidentally loaded from the .env file
        self.ai_service_url = settings.AI_SERVICE_URL.strip('"').strip("'")

    async def analyze_barcode_image(self, image_bytes: bytes) -> dict:
        """Sends the real image file to the AI developer's service."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                files = {'file': ('barcode.jpg', image_bytes, 'image/jpeg')}
                
                # Make the REAL request to the exact Ngrok URL
                response = await client.post(self.ai_service_url, files=files)
                
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=response.status_code, 
                        detail=f"AI Service failed to analyze the image: {response.text}"
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
                        detail=f"AI Service failed to analyze ISBN: {response.text}"
                    )
                
                return response.json()

        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Could not connect to AI service: {e}")

ai_client = AIAnalyzerClient()