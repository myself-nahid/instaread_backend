import httpx
from fastapi import HTTPException

class AIAnalyzerClient:
    def __init__(self):
        # The URL where your AI Developer's API is hosted
        self.ai_service_url = "http://ai-service:8001/api/v1/analyze" 

    async def analyze_barcode_image(self, image_bytes: bytes) -> dict:
        """Sends the image file to the AI developer's service."""
        try:
            # --- ACTUAL CODE TO COMMUNICATE WITH AI DEVs API ---
            # async with httpx.AsyncClient(timeout=30.0) as client:
            #     files = {'file': ('barcode.jpg', image_bytes, 'image/jpeg')}
            #     response = await client.post(f"{self.ai_service_url}/image", files=files)
            #     if response.status_code != 200:
            #         raise HTTPException(status_code=400, detail="AI Service failed to analyze the image.")
            #     return response.json()
            
            # --- MOCK RESPONSE FOR TESTING YOUR APP NOW ---
            return self._mock_ai_response()
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error connecting to AI service: {str(e)}")

    async def analyze_manual_isbn(self, isbn: str) -> dict:
        """Sends a manually typed ISBN to the AI developer's service."""
        try:
            # --- ACTUAL CODE TO COMMUNICATE WITH AI DEVs API ---
            # async with httpx.AsyncClient(timeout=30.0) as client:
            #     response = await client.post(f"{self.ai_service_url}/isbn", json={"isbn": isbn})
            #     if response.status_code != 200:
            #         raise HTTPException(status_code=400, detail="AI Service failed to analyze ISBN.")
            #     return response.json()

            # --- MOCK RESPONSE FOR TESTING YOUR APP NOW ---
            return self._mock_ai_response(isbn=isbn)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error connecting to AI service: {str(e)}")


    def _mock_ai_response(self, isbn="9780439023481"):
        """Mock data reflecting the exact UI for 'The Hunger Games'"""
        return {
            "isbn": isbn,
            "title": "The Hunger Games",
            "author": "Suzanne Collins",
            "cover_image_url": "https://covers.openlibrary.org/b/isbn/9780439023481-L.jpg",
            "recommended_age": "10+",
            "rating": "Concern",  # Safe, Caution, Concern
            "rating_score": 39,   # The percentage shown in the red circle
            "ai_insights": {
                "violence": {
                    "level": "High", 
                    "description": "Contains multiple instances of graphic violence including death and combat scenes. Strong themes of survival and trauma throughout."
                },
                "profanity": {
                    "level": "Mild", 
                    "description": "Contains mild language."
                },
                "sexual_content": {
                    "level": "None", 
                    "description": "No sexual content detected."
                },
                "gender_identity": {
                    "level": "None", 
                    "description": "No gender identity themes detected."
                }
            }
        }

ai_client = AIAnalyzerClient()