"""SendGrid email tool with automatic mock fallback.

When SENDGRID_API_KEY is set, sends real emails via the SendGrid API.
Otherwise, falls back to storing the email in SQLite (mock mode).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from .base import Tool, ToolContext

logger = logging.getLogger(__name__)


class EmailSendTool(Tool):
    name = "email_send"
    description = (
        "Send an email to one or more recipients. Uses SendGrid when configured, "
        "otherwise stores locally in mock mode."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "to": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Recipient email addresses.",
            },
            "subject": {
                "type": "string",
                "description": "Email subject line.",
            },
            "body": {
                "type": "string",
                "description": "Email body content (plain text).",
            },
        },
        "required": ["to", "subject", "body"],
    }

    def execute(self, params: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        recipients = params.get("to") or []
        if isinstance(recipients, str):
            recipients = [recipients]
        subject = params.get("subject", "Automated message")
        body = params.get("body", "")

        from ..core.config import REDIS_URL, SENDGRID_API_KEY
        from ..queue import enqueue_job

        if REDIS_URL:
            job = enqueue_job(
                "app.workers.tasks.send_email_task",
                context.run_id,
                recipients,
                subject,
                body,
            )
            if job is not None:
                return {
                    "status": "queued",
                    "job_id": job.id,
                    "mode": "rq",
                }

        if SENDGRID_API_KEY:
            return self._send_real(recipients, subject, body, context)

        return self._send_mock(recipients, subject, body, context)

    def _send_real(
        self,
        recipients: List[str],
        subject: str,
        body: str,
        context: ToolContext,
    ) -> Dict[str, Any]:
        from ..core.config import SENDGRID_API_KEY, SENDGRID_FROM_EMAIL

        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail

            message = Mail(
                from_email=SENDGRID_FROM_EMAIL,
                to_emails=recipients,
                subject=subject,
                plain_text_content=body,
            )
            sg = SendGridAPIClient(SENDGRID_API_KEY)
            response = sg.send(message)

            # Also store in local DB for traceability
            email_id = context.store.create_email(
                context.run_id,
                recipients=recipients,
                subject=subject,
                body=body,
                status="sent",
            )

            return {
                "email_id": email_id,
                "to": recipients,
                "subject": subject,
                "status": "sent",
                "sendgrid_status_code": response.status_code,
                "mode": "live",
            }
        except Exception as exc:
            logger.error("SendGrid send failed: %s", exc)
            # Fall back to mock on failure
            return self._send_mock(recipients, subject, body, context, error=str(exc))

    @staticmethod
    def _send_mock(
        recipients: List[str],
        subject: str,
        body: str,
        context: ToolContext,
        error: str | None = None,
    ) -> Dict[str, Any]:
        status = "queued"
        email_id = context.store.create_email(
            context.run_id,
            recipients=recipients,
            subject=subject,
            body=body,
            status=status,
        )
        result: Dict[str, Any] = {
            "email_id": email_id,
            "to": recipients,
            "subject": subject,
            "status": status,
            "mode": "mock",
        }
        if error:
            result["sendgrid_error"] = error
        return result
