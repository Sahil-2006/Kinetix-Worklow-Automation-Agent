"""Google Calendar tool with automatic mock fallback.

When GOOGLE_CALENDAR_CREDENTIALS is set, uses the real Google Calendar API.
Otherwise, falls back to an in-SQLite mock so the demo always works.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any, Dict, List

from .base import Tool, ToolContext
from ..core.config import REDIS_URL
from ..queue import enqueue_job

logger = logging.getLogger(__name__)


def _build_service():
    """Attempt to build a Google Calendar API service client."""
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
        from ..core.config import GOOGLE_CALENDAR_CREDENTIALS

        if not GOOGLE_CALENDAR_CREDENTIALS:
            return None

        creds_json = base64.b64decode(GOOGLE_CALENDAR_CREDENTIALS)
        info = json.loads(creds_json)
        creds = Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/calendar"]
        )
        return build("calendar", "v3", credentials=creds)
    except Exception as exc:
        logger.warning("Google Calendar API unavailable, using mock: %s", exc)
        return None


class CalendarScheduleTool(Tool):
    name = "calendar_schedule"
    description = (
        "Schedule a meeting on Google Calendar. Creates a real calendar event "
        "when credentials are configured, otherwise uses a local mock."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Meeting title.",
            },
            "date": {
                "type": "string",
                "description": "Date in YYYY-MM-DD format.",
            },
            "time": {
                "type": "string",
                "description": "Start time in HH:MM 24-hour format.",
                "default": "09:00",
            },
            "duration_minutes": {
                "type": "integer",
                "description": "Duration in minutes.",
                "default": 30,
            },
            "attendees": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Email addresses of attendees.",
                "default": [],
            },
            "description": {
                "type": "string",
                "description": "Optional meeting description.",
                "default": "",
            },
        },
        "required": ["title", "date"],
    }

    def execute(self, params: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        title = params.get("title", "Meeting")
        date_value = params["date"]
        time_value = params.get("time", "09:00")
        duration = int(params.get("duration_minutes", 30))
        attendees = params.get("attendees") or []
        description = params.get("description", "")
        location = params.get("location", "")

        if isinstance(attendees, str):
            attendees = [attendees]

        start_time = f"{date_value}T{time_value}:00"

        if REDIS_URL:
            job = enqueue_job(
                "app.workers.tasks.schedule_calendar_task",
                context.run_id,
                title,
                start_time,
                duration,
                attendees,
                description,
                location,
            )
            if job is not None:
                return {
                    "status": "queued",
                    "job_id": job.id,
                    "mode": "rq",
                }

        # Try real Google Calendar API
        service = _build_service()
        if service is not None:
            return self._create_real_event(
                service, title, start_time, duration, attendees, description
            )

        # Fallback to mock
        return self._create_mock_event(
            context, title, start_time, duration, attendees, location
        )

    def _create_real_event(
        self,
        service,
        title: str,
        start_time: str,
        duration: int,
        attendees: List[str],
        description: str,
    ) -> Dict[str, Any]:
        from ..core.config import GOOGLE_CALENDAR_ID
        from datetime import datetime, timedelta

        start_dt = datetime.fromisoformat(start_time)
        end_dt = start_dt + timedelta(minutes=duration)

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

        return {
            "event_id": event.get("id", ""),
            "title": title,
            "start_time": start_time,
            "duration_minutes": duration,
            "attendees": attendees,
            "link": event.get("htmlLink", ""),
            "status": "scheduled",
            "mode": "live",
        }

    @staticmethod
    def _create_mock_event(
        context: ToolContext,
        title: str,
        start_time: str,
        duration: int,
        attendees: List[str],
        location: str,
    ) -> Dict[str, Any]:
        event_id = context.store.create_calendar_event(
            context.run_id,
            title=title,
            start_time=start_time,
            duration_minutes=duration,
            attendees=attendees,
            location=location,
        )
        return {
            "event_id": event_id,
            "title": title,
            "start_time": start_time,
            "duration_minutes": duration,
            "attendees": attendees,
            "status": "scheduled",
            "mode": "mock",
        }
