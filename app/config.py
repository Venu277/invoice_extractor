from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "InvoiceIQ"
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Database
    DATABASE_URL: str = "sqlite:///./data/app.db"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        if isinstance(v, str):
            # Render and Heroku provide postgres:// or postgresql://
            if v.startswith("postgres://"):
                return v.replace("postgres://", "postgresql+psycopg2://", 1)
            elif v.startswith("postgresql://") and not v.startswith("postgresql+"):
                return v.replace("postgresql://", "postgresql+psycopg2://", 1)
        return v

    # Security & Auth
    SECRET_KEY: str = "default-insecure-secret-key-change-in-production-min-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720  # 12 hours

    # Storage & Paths
    UPLOAD_DIR: str = "./uploads"
    LOG_DIR: str = "./logs"
    BACKUP_DIR: str = "./backups"

    # OCR Settings
    OCR_ENABLED: bool = True
    TESSERACT_CMD: str = ""
    POPPLER_PATH: str = ""

    # SMTP Settings (Optional)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_TLS: bool = True

    # GST Filing Reminder Days
    GST_GSTR1_DUE_DAY: int = 11
    GST_GSTR3B_DUE_DAY: int = 20

    # Tally Configuration
    TALLY_LEDGER_PURCHASE: str = "Purchase"
    TALLY_LEDGER_SALES: str = "Sales"
    TALLY_LEDGER_INPUT_CGST: str = "Input CGST"
    TALLY_LEDGER_INPUT_SGST: str = "Input SGST"
    TALLY_LEDGER_INPUT_IGST: str = "Input IGST"
    TALLY_LEDGER_OUTPUT_CGST: str = "Output CGST"
    TALLY_LEDGER_OUTPUT_SGST: str = "Output SGST"
    TALLY_LEDGER_OUTPUT_IGST: str = "Output IGST"
    TALLY_LEDGER_ROUND_OFF: str = "Round Off"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def upload_path(self) -> Path:
        p = Path(self.UPLOAD_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def log_path(self) -> Path:
        p = Path(self.LOG_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def backup_path(self) -> Path:
        p = Path(self.BACKUP_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
