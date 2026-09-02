"""Celery app and background tasks (e.g. sending email off the request path)."""

from asgiref.sync import async_to_sync
from celery import Celery

from src.mail import create_message, mail

celery_app = Celery()
celery_app.config_from_object("src.config")


@celery_app.task()
def send_email(recipients: list[str], subject: str, body: str) -> None:
    message = create_message(recipients=recipients, subject=subject, body=body)
    async_to_sync(mail.send_message)(message)
    print("email sent")
