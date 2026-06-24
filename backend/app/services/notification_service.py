"""
Notification service.

Handles:
  - Email delivery via SendGrid (OTP, invite links, welcome emails)
  - SMS stub (extend with Twilio or Fast2SMS for production)
  - In-app notification storage (via Redis pub/sub for real-time)
"""

import logging
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ─── Email ────────────────────────────────────────────────────────────────────

async def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    plain_content: Optional[str] = None,
) -> bool:
    """
    Send a transactional email via SendGrid.

    Falls back to logging the email content in development mode (when
    SENDGRID_API_KEY is not configured).

    Args:
        to_email:      Recipient email address.
        subject:       Email subject line.
        html_content:  HTML body.
        plain_content: Optional plain-text body (auto-generated if omitted).

    Returns:
        True on success, False on failure.
    """
    if not settings.SENDGRID_API_KEY or settings.is_development:
        # Dev mode: log the email instead of sending it
        logger.info(
            "[DEV EMAIL] To: %s | Subject: %s\n%s",
            to_email,
            subject,
            plain_content or html_content,
        )
        return True

    try:
        import sendgrid
        from sendgrid.helpers.mail import Content, Email, Mail, To

        sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)

        message = Mail(
            from_email=Email(settings.FROM_EMAIL, settings.FROM_NAME),
            to_emails=To(to_email),
            subject=subject,
        )
        message.content = [
            Content("text/plain", plain_content or ""),
            Content("text/html", html_content),
        ]

        response = sg.send(message)
        if response.status_code in (200, 202):
            logger.info("Email sent to %s (status=%d).", to_email, response.status_code)
            return True
        else:
            logger.error(
                "SendGrid returned unexpected status %d for %s.",
                response.status_code,
                to_email,
            )
            return False

    except Exception as exc:
        logger.exception("Failed to send email to %s: %s", to_email, exc)
        return False


# ─── Email templates ──────────────────────────────────────────────────────────

async def send_otp_email(to_email: str, otp: str, user_name: str = "") -> bool:
    """Send an email OTP for account verification."""
    subject = "Your GenHealth AI Verification Code"
    html = f"""
    <div style="font-family:Inter,sans-serif;max-width:480px;margin:0 auto;padding:32px;">
      <div style="background:#0A2540;padding:20px;border-radius:12px;text-align:center;">
        <h1 style="color:#00C49A;font-size:24px;margin:0;">GenHealth AI</h1>
      </div>
      <div style="padding:32px 0;">
        <h2 style="color:#0F172A;">Hi {user_name or 'there'} 👋</h2>
        <p style="color:#64748B;">Your verification code is:</p>
        <div style="background:#F7F9FC;border:2px solid #00C49A;border-radius:12px;
                    padding:20px;text-align:center;margin:24px 0;">
          <span style="font-size:40px;font-weight:700;letter-spacing:12px;color:#0A2540;">
            {otp}
          </span>
        </div>
        <p style="color:#64748B;font-size:14px;">
          This code expires in {settings.OTP_EXPIRE_MINUTES} minutes.
          Do not share it with anyone.
        </p>
      </div>
      <p style="color:#94A3B8;font-size:12px;text-align:center;">
        © 2025 GenHealth AI · All data encrypted with AES-256
      </p>
    </div>
    """
    plain = f"Your GenHealth AI verification code is: {otp}. Expires in {settings.OTP_EXPIRE_MINUTES} minutes."
    return await send_email(to_email, subject, html, plain)


async def send_invite_email(
    to_email: str,
    inviter_name: str,
    relationship: str,
    invite_link: str,
) -> bool:
    """Send a family member invite email with a unique invite link."""
    subject = f"{inviter_name} invited you to join GenHealth AI"
    html = f"""
    <div style="font-family:Inter,sans-serif;max-width:480px;margin:0 auto;padding:32px;">
      <div style="background:#0A2540;padding:20px;border-radius:12px;text-align:center;">
        <h1 style="color:#00C49A;font-size:24px;margin:0;">GenHealth AI</h1>
      </div>
      <div style="padding:32px 0;">
        <h2 style="color:#0F172A;">You've been invited! 🧬</h2>
        <p style="color:#64748B;">
          <strong>{inviter_name}</strong> has added you as their
          <strong>{relationship.replace('_', ' ')}</strong> on GenHealth AI —
          a platform that uses family health history to predict and prevent disease.
        </p>
        <p style="color:#64748B;">
          By joining, you help your family better understand their hereditary health risks.
        </p>
        <div style="text-align:center;margin:32px 0;">
          <a href="{invite_link}"
             style="background:linear-gradient(135deg,#00C49A,#0097A7);color:#fff;
                    padding:14px 32px;border-radius:8px;text-decoration:none;
                    font-weight:600;font-size:16px;">
            Accept Invitation →
          </a>
        </div>
        <p style="color:#94A3B8;font-size:13px;">
          This link expires in {settings.INVITE_TOKEN_EXPIRE_HOURS} hours.
          If you did not expect this invitation, you can safely ignore this email.
        </p>
      </div>
    </div>
    """
    plain = (
        f"{inviter_name} invited you to GenHealth AI as their {relationship}. "
        f"Accept here: {invite_link} (expires in {settings.INVITE_TOKEN_EXPIRE_HOURS}h)"
    )
    return await send_email(to_email, subject, html, plain)


async def send_password_reset_email(
    to_email: str, reset_link: str, user_name: str = ""
) -> bool:
    """Send a password reset link email."""
    subject = "Reset your GenHealth AI password"
    html = f"""
    <div style="font-family:Inter,sans-serif;max-width:480px;margin:0 auto;padding:32px;">
      <div style="background:#0A2540;padding:20px;border-radius:12px;text-align:center;">
        <h1 style="color:#00C49A;font-size:24px;margin:0;">GenHealth AI</h1>
      </div>
      <div style="padding:32px 0;">
        <h2 style="color:#0F172A;">Password Reset Request</h2>
        <p style="color:#64748B;">
          Hi {user_name or 'there'}, we received a request to reset your password.
        </p>
        <div style="text-align:center;margin:32px 0;">
          <a href="{reset_link}"
             style="background:#EF4444;color:#fff;padding:14px 32px;
                    border-radius:8px;text-decoration:none;font-weight:600;">
            Reset Password
          </a>
        </div>
        <p style="color:#94A3B8;font-size:13px;">
          This link expires in 30 minutes. If you did not request this, ignore this email.
        </p>
      </div>
    </div>
    """
    plain = f"Reset your GenHealth AI password: {reset_link} (expires in 30 minutes)"
    return await send_email(to_email, subject, html, plain)


async def send_welcome_email(to_email: str, user_name: str) -> bool:
    """Send a welcome email to a newly registered user."""
    subject = "Welcome to GenHealth AI 🧬"
    html = f"""
    <div style="font-family:Inter,sans-serif;max-width:480px;margin:0 auto;padding:32px;">
      <div style="background:linear-gradient(135deg,#0A2540,#1a4a7a);
                  padding:32px 20px;border-radius:12px;text-align:center;">
        <h1 style="color:#00C49A;font-size:28px;margin:0 0 8px;">GenHealth AI</h1>
        <p style="color:rgba(255,255,255,0.7);margin:0;font-size:14px;">
          Generational Health Intelligence
        </p>
      </div>
      <div style="padding:32px 0;">
        <h2 style="color:#0F172A;">Welcome, {user_name.split()[0]}! 👋</h2>
        <p style="color:#64748B;line-height:1.6;">
          Your account is ready. Start by uploading your first prescription or
          adding your family members to begin building your generational health profile.
        </p>
        <div style="background:#F7F9FC;border-radius:10px;padding:20px;margin:20px 0;">
          <p style="color:#0F172A;font-weight:600;margin:0 0 12px;">Quick Start</p>
          <ul style="color:#64748B;padding-left:20px;line-height:1.8;">
            <li>📤 Upload a prescription</li>
            <li>👨‍👩‍👧 Add family members</li>
            <li>⚡ View your risk profile</li>
            <li>✅ Follow your recommendations</li>
          </ul>
        </div>
        <div style="text-align:center;">
          <a href="{settings.FRONTEND_URL}"
             style="background:linear-gradient(135deg,#00C49A,#0097A7);color:#fff;
                    padding:14px 32px;border-radius:8px;text-decoration:none;
                    font-weight:600;">
            Open GenHealth AI →
          </a>
        </div>
      </div>
    </div>
    """
    plain = f"Welcome to GenHealth AI, {user_name}! Open the app: {settings.FRONTEND_URL}"
    return await send_email(to_email, subject, html, plain)


# ─── SMS (stub) ───────────────────────────────────────────────────────────────

async def send_sms(to_phone: str, message: str) -> bool:
    """
    Send an SMS message.

    Currently a stub that logs in dev mode. Integrate with Twilio or
    Fast2SMS for production by adding the respective SDK calls here.
    """
    logger.info("[SMS STUB] To: %s | Message: %s", to_phone, message)
    return True


async def send_otp_sms(to_phone: str, otp: str) -> bool:
    """Send an OTP via SMS."""
    message = (
        f"Your GenHealth AI verification code is: {otp}. "
        f"Expires in {settings.OTP_EXPIRE_MINUTES} minutes. Do not share."
    )
    return await send_sms(to_phone, message)
