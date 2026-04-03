import resend
from app.core.config import settings

# Configure the Resend SDK with client's API Key
resend.api_key = settings.RESEND_API_KEY

async def send_otp_email(email_to: str, otp: str, subject: str):
    """
    Sends an HTML formatted email containing the 6-digit OTP using Resend.com
    """
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 10px; text-align: center;">
        <h2 style="color: #1e3a8a;">QandelShield Verification</h2>
        <p style="color: #475569; font-size: 16px;">Please use the following 6-digit code to verify your email address. This code is valid for 10 minutes.</p>
        <div style="margin: 30px 0;">
            <span style="font-size: 36px; font-weight: bold; letter-spacing: 8px; color: #1d4ed8; background-color: #f1f5f9; padding: 15px 30px; border-radius: 8px;">
                {otp}
            </span>
        </div>
        <p style="color: #94a3b8; font-size: 14px;">If you didn't request this, you can safely ignore this email.</p>
    </div>
    """

    # Format the payload for Resend
    params = {
        "from": settings.MAIL_FROM,
        "to": [email_to],
        "subject": subject,
        "html": html_content,
    }

    try:
        # Send the email via Resend API
        response = resend.Emails.send(params)
        print(f"Successfully sent OTP {otp} to {email_to} via Resend. ID: {response.get('id')}")
        return response
    except Exception as e:
        print(f"Failed to send email to {email_to} via Resend. Error: {str(e)}")