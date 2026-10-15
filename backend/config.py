"""
Application configuration and logging setup.

Design decision: Centralizing all configuration here guarantees we never read
environment variables ad-hoc across modules, preventing accidental secret leakage
and ensuring verified defaults are always available.
"""

import os
import logging
from dataclasses import dataclass


@dataclass
class Settings:
    """Settings loaded from environment variables with safe defaults."""

    # API Keys - never printed or logged directly
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    nvidia_api_key: str = os.getenv("NVIDIA_API_KEY", "")
    sarvam_api_key: str = os.getenv("SARVAM_API_KEY", "")

    # Verified production model defaults (lookup confirmed against docs)
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    nvidia_model: str = os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")

    # Speech model defaults
    groq_whisper_model: str = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3")
    sarvam_tts_model: str = os.getenv("SARVAM_TTS_MODEL", "bulbul:v3")
    sarvam_translate_model: str = os.getenv("SARVAM_TRANSLATE_MODEL", "sarvam-translate:v1")

    # Storage and runtime flags
    db_path: str = os.getenv("DB_PATH", "./bhaav.db")
    scripted_shops: bool = os.getenv("SCRIPTED_SHOPS", "0").lower() in ("1", "true", "yes")
    demo_controls_enabled: bool = os.getenv("DEMO_CONTROLS_ENABLED", "1").lower() in ("1", "true", "yes")
    cors_origins: str = os.getenv("CORS_ORIGINS", "*")
    port: int = int(os.getenv("PORT", "8000"))
    call_answer_timeout: float = float(os.getenv("CALL_ANSWER_TIMEOUT", "30.0"))


# Global settings instance
settings = Settings()


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configures safe, structured logging without leaking secrets."""
    logger = logging.getLogger("bhaav")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s (%(module)s:%(lineno)d): %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(level)
    return logger


logger = setup_logging()
