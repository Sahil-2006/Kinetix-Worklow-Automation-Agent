from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row

from ..core.config import DATABASE_URL
from ..security.pii import encrypt_json, encrypt_text, redact_payload, redact_text


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dump(payload: Optional[Any]) -> Optional[str]:
    if payload is None:
        return None
    return json.dumps(payload, ensure_ascii=True, default=str)


def _json_load(payload: Optional[str]) -> Optional[Dict[str, Any]]:
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


def _to_iso(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


class DbPool:
    _pool: ConnectionPool | None = None
    _conninfo: str | None = None

    @classmethod
    def get_pool(cls, conninfo: str) -> ConnectionPool:
        if not conninfo:
            raise RuntimeError("DATABASE_URL is not configured.")
        if cls._pool is None or cls._conninfo != conninfo:
            cls._conninfo = conninfo
            cls._pool = ConnectionPool(
                conninfo=conninfo,
                min_size=1,
                max_size=10,
                open=True,
                kwargs={"autocommit": True},
            )
        return cls._pool


class TraceStore:
    def __init__(self, database_url: str | None = None) -> None:
        conninfo = database_url or DATABASE_URL
        if not conninfo:
            raise RuntimeError("DATABASE_URL is not configured.")
        self.pool = DbPool.get_pool(conninfo)
        self._init_db()

    def _execute(self, query: str, params: Tuple[Any, ...] = ()) -> None:
        with self.pool.connection() as conn:
            conn.execute(query, params)

    def _fetchone(
        self, query: str, params: Tuple[Any, ...] = ()
    ) -> Optional[Dict[str, Any]]:
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, params)
                row = cur.fetchone()
                return dict(row) if row else None

    def _fetchall(
        self, query: str, params: Tuple[Any, ...] = ()
    ) -> List[Dict[str, Any]]:
        with self.pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
                return [dict(row) for row in rows]

    def _init_db(self) -> None:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT NOT NULL,
                password_hash TEXT,
                role TEXT NOT NULL DEFAULT 'user',
                google_id TEXT,
                avatar_url TEXT,
                created_at TIMESTAMPTZ NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                command TEXT NOT NULL,
                intent TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL,
                completed_at TIMESTAMPTZ,
                error TEXT
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS steps (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                status TEXT NOT NULL,
                input_json TEXT,
                output_json TEXT,
                started_at TIMESTAMPTZ NOT NULL,
                ended_at TIMESTAMPTZ,
                error TEXT
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS calendar_events (
                id TEXT PRIMARY KEY,
                run_id TEXT,
                title TEXT NOT NULL,
                start_time TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                attendees_json TEXT,
                location TEXT,
                created_at TIMESTAMPTZ NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS email_outbox (
                id TEXT PRIMARY KEY,
                run_id TEXT,
                to_json TEXT,
                subject TEXT,
                body TEXT,
                status TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS llm_calls (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                iteration INTEGER NOT NULL DEFAULT 0,
                messages_json TEXT,
                response_content TEXT,
                tool_calls_count INTEGER DEFAULT 0,
                model TEXT,
                usage_json TEXT,
                started_at TIMESTAMPTZ NOT NULL,
                ended_at TIMESTAMPTZ,
                error TEXT
            );
            """,
        ]
        for statement in statements:
            self._execute(statement)

    # ── Runs ───────────────────────────────────────────────────────

    def create_run(
        self, command: str, intent: str, user_id: str | None = None
    ) -> Tuple[str, str]:
        run_id = str(uuid.uuid4())
        created_at = utc_now()
        command_safe = redact_text(command) or ""
        self._execute(
            "INSERT INTO runs (id, user_id, command, intent, status, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
            (run_id, user_id, command_safe, intent, "running", created_at),
        )
        return run_id, created_at

    def finish_run(self, run_id: str, status: str, error: Optional[str] = None) -> None:
        completed_at = utc_now()
        self._execute(
            "UPDATE runs SET status = %s, completed_at = %s, error = %s WHERE id = %s",
            (status, completed_at, error, run_id),
        )

    def list_runs(self, limit: int = 20) -> List[Dict[str, Any]]:
        rows = self._fetchall(
            """
            SELECT id, command, intent, status, created_at, completed_at
            FROM runs
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        for row in rows:
            row["created_at"] = _to_iso(row.get("created_at"))
            row["completed_at"] = _to_iso(row.get("completed_at"))
        return rows

    def list_runs_for_user(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        rows = self._fetchall(
            """
            SELECT id, command, intent, status, created_at, completed_at
            FROM runs
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (user_id, limit),
        )
        for row in rows:
            row["created_at"] = _to_iso(row.get("created_at"))
            row["completed_at"] = _to_iso(row.get("completed_at"))
        return rows

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        run = self._fetchone(
            """
            SELECT id, command, intent, status, created_at, completed_at, error
            FROM runs
            WHERE id = %s
            """,
            (run_id,),
        )
        if not run:
            return None
        run["created_at"] = _to_iso(run.get("created_at"))
        run["completed_at"] = _to_iso(run.get("completed_at"))
        return run

    # ── Steps ──────────────────────────────────────────────────────

    def create_step(
        self, run_id: str, tool_name: str, input_payload: Dict[str, Any]
    ) -> Tuple[str, str]:
        step_id = str(uuid.uuid4())
        started_at = utc_now()
        input_safe = redact_payload(input_payload, mask_payload=True)
        self._execute(
            """
            INSERT INTO steps (id, run_id, tool_name, status, input_json, started_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (step_id, run_id, tool_name, "running", _json_dump(input_safe), started_at),
        )
        return step_id, started_at

    def finish_step(
        self,
        step_id: str,
        status: str,
        output_payload: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        ended_at = utc_now()
        output_safe = (
            redact_payload(output_payload, mask_payload=True)
            if output_payload
            else None
        )
        self._execute(
            """
            UPDATE steps
            SET status = %s, output_json = %s, ended_at = %s, error = %s
            WHERE id = %s
            """,
            (status, _json_dump(output_safe), ended_at, error, step_id),
        )

    def get_steps(self, run_id: str) -> List[Dict[str, Any]]:
        rows = self._fetchall(
            """
            SELECT tool_name, status, output_json, error
            FROM steps
            WHERE run_id = %s
            ORDER BY started_at ASC
            """,
            (run_id,),
        )
        results = []
        for row in rows:
            results.append(
                {
                    "tool_name": row["tool_name"],
                    "status": row["status"],
                    "output": _json_load(row["output_json"]),
                    "error": row["error"],
                }
            )
        return results

    # ── LLM Calls ──────────────────────────────────────────────────

    def create_llm_call(
        self,
        run_id: str,
        messages: List[Dict[str, Any]],
        iteration: int,
    ) -> str:
        call_id = str(uuid.uuid4())
        started_at = utc_now()
        messages_safe = redact_payload(messages, mask_payload=True)
        self._execute(
            """
            INSERT INTO llm_calls (id, run_id, iteration, messages_json, started_at)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (call_id, run_id, iteration, _json_dump(messages_safe), started_at),
        )
        return call_id

    def finish_llm_call(
        self,
        call_id: str,
        response_content: Optional[str] = None,
        tool_calls_count: int = 0,
        model: str = "",
        usage: Optional[Dict[str, int]] = None,
        error: Optional[str] = None,
    ) -> None:
        ended_at = utc_now()
        response_safe = redact_text(response_content) if response_content else None
        self._execute(
            """
            UPDATE llm_calls
            SET response_content = %s, tool_calls_count = %s,
                model = %s, usage_json = %s, ended_at = %s, error = %s
            WHERE id = %s
            """,
            (
                response_safe,
                tool_calls_count,
                model,
                _json_dump(usage),
                ended_at,
                error,
                call_id,
            ),
        )

    # ── Calendar events (encrypted) ───────────────────────────────

    def create_calendar_event(
        self,
        run_id: str,
        title: str,
        start_time: str,
        duration_minutes: int,
        attendees: List[str],
        location: str,
    ) -> str:
        event_id = str(uuid.uuid4())
        created_at = utc_now()
        attendees_enc = encrypt_json(attendees)
        self._execute(
            """
            INSERT INTO calendar_events
            (id, run_id, title, start_time, duration_minutes, attendees_json, location, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                event_id,
                run_id,
                title,
                start_time,
                duration_minutes,
                attendees_enc,
                location,
                created_at,
            ),
        )
        return event_id

    # ── Email outbox (encrypted) ───────────────────────────────────

    def create_email(
        self,
        run_id: str,
        recipients: List[str],
        subject: str,
        body: str,
        status: str,
    ) -> str:
        email_id = str(uuid.uuid4())
        created_at = utc_now()
        to_enc = encrypt_json(recipients)
        subject_enc = encrypt_text(subject)
        body_enc = encrypt_text(body)
        self._execute(
            """
            INSERT INTO email_outbox
            (id, run_id, to_json, subject, body, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                email_id,
                run_id,
                to_enc,
                subject_enc,
                body_enc,
                status,
                created_at,
            ),
        )
        return email_id

    # ── Users ──────────────────────────────────────────────────────

    def create_user(
        self,
        user_id: str,
        username: str,
        email: str,
        password_hash: Optional[str] = None,
        role: str = "user",
        google_id: Optional[str] = None,
        avatar_url: Optional[str] = None,
    ) -> None:
        created_at = utc_now()
        safe_password = password_hash or ""
        self._execute(
            """
            INSERT INTO users (id, username, email, password_hash, role, google_id, avatar_url, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                username,
                email,
                safe_password,
                role,
                google_id,
                avatar_url,
                created_at,
            ),
        )

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            """
            SELECT id, username, email, password_hash, role, google_id, avatar_url, created_at
            FROM users WHERE username = %s
            """,
            (username,),
        )

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            """
            SELECT id, username, email, password_hash, role, google_id, avatar_url, created_at
            FROM users WHERE id = %s
            """,
            (user_id,),
        )

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            """
            SELECT id, username, email, password_hash, role, google_id, avatar_url, created_at
            FROM users WHERE email = %s
            """,
            (email,),
        )

    def get_user_by_google_id(self, google_id: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            """
            SELECT id, username, email, password_hash, role, google_id, avatar_url, created_at
            FROM users WHERE google_id = %s
            """,
            (google_id,),
        )

    def update_user_google_id(
        self, user_id: str, google_id: str, avatar_url: Optional[str] = None
    ) -> None:
        self._execute(
            "UPDATE users SET google_id = %s, avatar_url = %s WHERE id = %s",
            (google_id, avatar_url, user_id),
        )
