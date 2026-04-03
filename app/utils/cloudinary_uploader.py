import cloudinary
import cloudinary.uploader
from fastapi import UploadFile
from app.core.config import settings

cloudinary.config(
  cloud_name=settings.CLOUDINARY_CLOUD_NAME,
  api_key=settings.CLOUDINARY_API_KEY,
  api_secret=settings.CLOUDINARY_API_SECRET,
  secure=True
)

async def upload_profile_image(file: UploadFile, user_id: int) -> str:
    """
    Uploads a user's profile picture to Cloudinary, overwriting any existing one.
    Resizes the image to a 250x250 square for consistency.
    """
    try:
        # Upload the file to Cloudinary
        upload_result = cloudinary.uploader.upload(
            file.file,
            # Organize uploads into a specific folder on Cloudinary
            folder="profile_pictures",
            # Use the user's ID as the public_id to ensure each user has only one profile pic
            public_id=str(user_id),
            # Overwrite the image if it already exists for this user
            overwrite=True,
            # Automatically resize the image to a 250x250 square, focusing on the face if detected
            transformation=[
                {'width': 250, 'height': 250, 'gravity': "face", 'crop': "fill"}
            ]
        )
        # Return the secure URL of the uploaded and transformed image
        return upload_result.get("secure_url")
        
    except Exception as e:
        # Handle potential upload errors
        print(f"Cloudinary upload failed: {str(e)}")
        return None