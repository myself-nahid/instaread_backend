import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_DAYS: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_DAYS", 7))
    AI_SERVICE_URL: str = os.getenv("AI_SERVICE_URL", "http://127.0.0.1:8002/scan-book")
    AI_SERVICE_URL_IMAGE: str = os.getenv("AI_SERVICE_URL_IMAGE", "http://127.0.0.1:8002/scan-book-image")
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET")
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY")
    MAIL_FROM: str = os.getenv("MAIL_FROM", "onboarding@resend.dev")
    CLOUDINARY_CLOUD_NAME: str = os.getenv("CLOUDINARY_CLOUD_NAME")
    CLOUDINARY_API_KEY: str = os.getenv("CLOUDINARY_API_KEY")
    CLOUDINARY_API_SECRET: str = os.getenv("CLOUDINARY_API_SECRET")
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID")
    APPLE_APP_ID: str = os.getenv("APPLE_APP_ID")
    APP_WEBHOOK_SECRET: str = os.getenv("APP_WEBHOOK_SECRET", "default_secret")


    class Config:
        case_sensitive = True

settings = Settings()