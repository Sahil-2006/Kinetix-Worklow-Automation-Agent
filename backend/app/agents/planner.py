from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List
import re


@dataclass
class PlanStep:
    tool_name: str
    params: Dict[str, Any]


@dataclass
class Plan:
    intent: str
    steps: List[PlanStep]
    missing: List[str]
    message: str = ""


def classify_intent(command: str) -> str:
    lower = command.lower()
    if "csv" in lower and ("analyze" in lower or "trend" in lower):
        return "analyze_csv"
    if "schedule" in lower and "meeting" in lower:
        return "schedule_meeting"
    if "summarize" in lower and "report" in lower:
        return "summarize_reports"
    if "search" in lower or "find" in lower or "lookup" in lower:
        return "web_search"
    return "unknown"


def _extract_path_by_ext(command: str, exts: List[str]) -> str | None:
    for ext in exts:
        matches = re.findall(r"([\\w\\-./\\\\]+%s)" % re.escape(ext), command)
        if matches:
            return matches[0]
    return None


def _extract_emails(command: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}", command)


def _extract_time(command: str) -> str | None:
    match = re.search(r"(\\d{1,2}:\\d{2})", command)
    return match.group(1) if match else None


def _extract_relative_date(command: str) -> str | None:
    lower = command.lower()
    today = date.today()
    if "tomorrow" in lower:
        return (today + timedelta(days=1)).isoformat()
    if "today" in lower:
        return today.isoformat()
    return None


def _extract_query(command: str) -> str | None:
    lower = command.lower()
    for keyword in ("search", "find", "lookup"):
        if keyword in lower:
            tail = command.lower().split(keyword, 1)[1].strip(" :")
            return tail or None
    return None


def build_plan(command: str, context: Dict[str, Any]) -> Plan:
    intent = classify_intent(command)
    steps: List[PlanStep] = []
    missing: List[str] = []

    if intent == "analyze_csv":
        csv_path = context.get("csv_path") or _extract_path_by_ext(command, [".csv"])
        if not csv_path:
            missing.append("csv_path")
        else:
            steps.append(
                PlanStep(
                    "csv_analyzer",
                    {
                        "path": csv_path,
                        "top_n": context.get("top_n", 3),
                        "max_rows": context.get("max_rows", 5000),
                    },
                )
            )

    elif intent == "schedule_meeting":
        date_value = context.get("date") or _extract_relative_date(command)
        if not date_value:
            missing.append("date")
        time_value = context.get("time") or _extract_time(command) or "09:00"
        attendees = context.get("attendees") or _extract_emails(command)
        steps.append(
            PlanStep(
                "calendar_schedule",
                {
                    "title": context.get("title", "Meeting"),
                    "date": date_value,
                    "time": time_value,
                    "duration_minutes": context.get("duration_minutes", 30),
                    "attendees": attendees,
                    "location": context.get("location", ""),
                },
            )
        )

    elif intent == "summarize_reports":
        report_path = context.get("report_path") or _extract_path_by_ext(
            command, [".txt", ".md", ".log"]
        )
        if not report_path:
            missing.append("report_path")
        steps.extend(
            [
                PlanStep(
                    "file_read",
                    {
                        "path": report_path,
                        "max_chars": context.get("max_chars", 8000),
                    },
                ),
                PlanStep(
                    "report_summarizer",
                    {"text": "$ref:steps.0.content"},
                ),
            ]
        )
        email_to = context.get("email_to") or _extract_emails(command)
        if "send" in command.lower() or email_to:
            if not email_to:
                missing.append("email_to")
            else:
                steps.append(
                    PlanStep(
                        "email_send",
                        {
                            "to": email_to,
                            "subject": context.get("subject", "Daily report summary"),
                            "body": "$ref:steps.1.summary",
                        },
                    )
                )

    elif intent == "web_search":
        query = context.get("query") or _extract_query(command)
        if not query:
            missing.append("query")
        else:
            steps.append(
                PlanStep(
                    "web_search",
                    {
                        "query": query,
                        "top_k": context.get("top_k", 3),
                    },
                )
            )

    else:
        return Plan(
            intent="unknown", steps=[], missing=[], message="Intent not recognized."
        )

    message = "Missing required inputs." if missing else "Plan ready."
    return Plan(intent=intent, steps=steps, missing=missing, message=message)
