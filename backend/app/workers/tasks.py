from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from ..core.config import SENDGRID_API_KEY, SENDGRID_FROM_EMAIL, GOOGLE_CALENDAR_ID
from ..storage.db import TraceStore
from ..tools.calendar import _build_service

logger = logging.getLogger(__name__)


def send_email_task(
    run_id: str,
    recipients: List[str],
    subject: str,
    body: str,
) -> Dict[str, Any]:
    store = TraceStore()
    status = "queued"
    sendgrid_status_code = None

    if SENDGRID_API_KEY:
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
            status = "sent"
            sendgrid_status_code = response.status_code
        except Exception as exc:
            logger.warning("SendGrid send failed in worker: %s", exc)
            status = "failed"

    email_id = store.create_email(
        run_id,
        recipients=recipients,
        subject=subject,
        body=body,
        status=status,
    )

    result: Dict[str, Any] = {
        "email_id": email_id,
        "status": status,
        "mode": "rq",
    }
    if sendgrid_status_code is not None:
        result["sendgrid_status_code"] = sendgrid_status_code
    return result


def schedule_calendar_task(
    run_id: str,
    title: str,
    start_time: str,
    duration_minutes: int,
    attendees: List[str],
    description: str = "",
    location: str = "",
) -> Dict[str, Any]:
    store = TraceStore()
    service = _build_service()
    status = "scheduled"
    mode = "mock"
    link = ""

    if service is not None:
        try:
            start_dt = datetime.fromisoformat(start_time)
            end_dt = start_dt + timedelta(minutes=duration_minutes)

            event_body = {
                "summary": title,
                "description": description,
                "start": {"dateTime": start_dt.isoformat(), "timeZone": "UTC"},
                "end": {"dateTime": end_dt.isoformat(), "timeZone": "UTC"},
                "attendees": [{"email": e} for e in attendees],
            }

            event = (
                service.events()
                .insert(calendarId=GOOGLE_CALENDAR_ID, body=event_body)
                .execute()
            )
            link = event.get("htmlLink", "")
            mode = "live"
        except Exception as exc:
            logger.warning("Calendar scheduling failed in worker: %s", exc)
            status = "failed"

    event_id = store.create_calendar_event(
        run_id,
        title=title,
        start_time=start_time,
        duration_minutes=duration_minutes,
        attendees=attendees,
        location=location,
    )

    return {
        "event_id": event_id,
        "title": title,
        "start_time": start_time,
        "duration_minutes": duration_minutes,
        "attendees": attendees,
        "status": status,
        "mode": "rq" if mode == "mock" else "live",
        "link": link,
    }
