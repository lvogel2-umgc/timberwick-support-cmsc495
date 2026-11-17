"""
Author: Jacob Wills-Brennan

Application settings, read from environment variables or a local .env file.
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEV_SECRET_KEY = "dev-only-secret-key-change-before-deploying"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    database_url: str
    secret_key: str
    token_minutes: int
    confidence_threshold: float
    knowledge_base_path: Path


def load_settings() -> Settings:
    secret_key = os.getenv("SECRET_KEY", DEV_SECRET_KEY)
    if secret_key == DEV_SECRET_KEY:
        logger.warning("SECRET_KEY is not set. Using the development key; do not deploy this.")

    return Settings(
        database_url=os.getenv("DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'support.db'}"),
        secret_key=secret_key,
        token_minutes=int(os.getenv("TOKEN_MINUTES", "30")),
        confidence_threshold=float(os.getenv("CONFIDENCE_THRESHOLD", "0.30")),
        knowledge_base_path=Path(
            os.getenv("KNOWLEDGE_BASE_PATH", str(PROJECT_ROOT / "data" / "knowledge_base.json"))
        ),
    )
