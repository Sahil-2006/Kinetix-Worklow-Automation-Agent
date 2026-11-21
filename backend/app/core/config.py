from pathlib import Path
import os

from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
IS_PRODUCTION = APP_ENV in {"prod", "production"}

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("AGENT_DATA_DIR", BASE_DIR / "data"))
DB_PATH = Path(os.getenv("AGENT_DB_PATH", DATA_DIR / "agent.db"))

# --- Supabase / Postgres ---
DATABASE_URL = os.getenv("DATABASE_URL", "")

_raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173")
CORS_ORIGINS = [origin.strip() for origin in _raw_origins.split(",") if origin.strip()]

# --- OpenRouter LLM ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# --- SendGrid Email ---
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "agent@kinetix.dev")

# --- Google Calendar ---
GOOGLE_CALENDAR_CREDENTIALS = os.getenv("GOOGLE_CALENDAR_CREDENTIALS", "")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")

# --- Agent Limits ---
MAX_REACT_ITERATIONS = int(os.getenv("MAX_REACT_ITERATIONS", "10"))

# --- Auth (JWT) ---
JWT_SECRET = os.getenv("JWT_SECRET", "").strip()
if IS_PRODUCTION and len(JWT_SECRET) < 32:
    raise RuntimeError("Production requires a JWT_SECRET with at least 32 characters.")
if not JWT_SECRET:
    JWT_SECRET = "kinetix-dev-secret-change-me"
JWT_ACCESS_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_EXPIRE_MINUTES", "30"))
JWT_REFRESH_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_EXPIRE_DAYS", "7"))

# --- Google OAuth ---
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")

# --- PII Encryption ---
PII_ENCRYPTION_KEY = os.getenv("PII_ENCRYPTION_KEY", "").strip()
if IS_PRODUCTION and not PII_ENCRYPTION_KEY:
    raise RuntimeError("Production requires PII_ENCRYPTION_KEY to keep encrypted records readable.")
if PII_ENCRYPTION_KEY:
    try:
        Fernet(PII_ENCRYPTION_KEY.encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise RuntimeError("PII_ENCRYPTION_KEY must be a valid Fernet key.") from exc

# --- Redis ---
REDIS_URL = os.getenv("REDIS_URL", "")

# External actions remain simulated unless explicitly enabled.
ENABLE_LIVE_ACTIONS = os.getenv("ENABLE_LIVE_ACTIONS", "false").strip().lower() == "true"
