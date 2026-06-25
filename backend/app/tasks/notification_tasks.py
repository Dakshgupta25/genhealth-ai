"""
Notification background tasks for GenHealth AI.
Bridges the synchronous Celery worker environment with the asynchronous NotificationService.
"""

import asyncio
import logging
from typing import Optional

from app.celery_app import celery_app
from app.services import notification_service

logger = logging.getLogger(__name__)


def run_async(coro):
    """Helper to run async coroutines in the Celery worker thread's event loop."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@celery_app.task(name="app.tasks.notification_tasks.send_welcome_email")
def send_welcome_email(to_email: str, user_name: str) -> bool:
    """Send a welcome email asynchronously."""
    logger.info("Queued welcome email task for: %s", to_email)
    return run_async(notification_service.send_welcome_email(to_email, user_name))


@celery_app.task(name="app.tasks.notification_tasks.send_otp_email")
def send_otp_email(to_email: str, otp: str, user_name: str = "") -> bool:
    """Send an OTP email asynchronously."""
    logger.info("Queued OTP email task for: %s", to_email)
    return run_async(notification_service.send_otp_email(to_email, otp, user_name))


@celery_app.task(name="app.tasks.notification_tasks.send_invite_email")
def send_invite_email(
    to_email: str,
    inviter_name: str,
    relationship: str,
    invite_link: str,
) -> bool:
    """Send a family member invitation email asynchronously."""
    logger.info("Queued invite email task for: %s", to_email)
    return run_async(
        notification_service.send_invite_email(
            to_email=to_email,
            inviter_name=inviter_name,
            relationship=relationship,
            invite_link=invite_link,
        )
    )


@celery_app.task(name="app.tasks.notification_tasks.send_password_reset_email")
def send_password_reset_email(to_email: str, reset_link: str, user_name: str = "") -> bool:
    """Send a password reset email asynchronously."""
    logger.info("Queued password reset email task for: %s", to_email)
    return run_async(notification_service.send_password_reset_email(to_email, reset_link, user_name))


@celery_app.task(name="app.tasks.notification_tasks.send_otp_sms")
def send_otp_sms(to_phone: str, otp: str) -> bool:
    """Send an OTP SMS asynchronously."""
    logger.info("Queued OTP SMS task for: %s", to_phone)
    return run_async(notification_service.send_otp_sms(to_phone, otp))
