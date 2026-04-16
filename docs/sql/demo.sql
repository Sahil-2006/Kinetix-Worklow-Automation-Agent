-- Run against your Postgres database in Supabase or psql.

-- Latest runs
SELECT id, command, intent, status, created_at, completed_at
FROM runs
ORDER BY created_at DESC
LIMIT 10;

-- Steps for a run (replace RUN_ID)
-- SELECT tool_name, status, output_json, error
-- FROM steps
-- WHERE run_id = 'RUN_ID'
-- ORDER BY started_at ASC;

-- Calendar events (mock)
SELECT id, title, start_time, duration_minutes, created_at
FROM calendar_events
ORDER BY created_at DESC
LIMIT 5;

-- Email outbox (mock)
SELECT id, subject, status, created_at
FROM email_outbox
ORDER BY created_at DESC
LIMIT 5;
