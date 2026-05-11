"""
app/config/settings.py
======================
Centralized application configuration using Pydantic Settings.
Loads values from environment variables and .env file.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
import os


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    All sensitive values MUST be set in the .env file.
    """

    # --- OpenAI Settings ---
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o", env="OPENAI_MODEL")
    embedding_model: str = Field(
        default="text-embedding-3-small", env="EMBEDDING_MODEL"
    )
    max_tokens: int = Field(default=4096, env="MAX_TOKENS")
    temperature: float = Field(default=0.0, env="TEMPERATURE")

    # --- Application Settings ---
    app_env: str = Field(default="development", env="APP_ENV")
    app_debug: bool = Field(default=True, env="APP_DEBUG")
    app_host: str = Field(default="0.0.0.0", env="APP_HOST")
    app_port: int = Field(default=8000, env="APP_PORT")
    streamlit_port: int = Field(default=8501, env="STREAMLIT_PORT")

    # --- Database ---
    database_url: str = Field(
        default="sqlite:///./app/database/audit_logs.db", env="DATABASE_URL"
    )

    # --- Security ---
    secret_key: str = Field(default="change-me-in-production", env="SECRET_KEY")
    max_file_size_mb: int = Field(default=10, env="MAX_FILE_SIZE_MB")
    allowed_extensions: str = Field(default="pdf,docx,json", env="ALLOWED_EXTENSIONS")

    # --- Paths ---
    faiss_index_path: str = Field(default="./data/faiss_index", env="FAISS_INDEX_PATH")
    output_dir: str = Field(default="./data/outputs", env="OUTPUT_DIR")

    # --- Logging ---
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_file: str = Field(default="./logs/app.log", env="LOG_FILE")

    # --- Scoring Weights (fixed rubric) ---
    weight_skills: float = 0.30
    weight_experience: float = 0.25
    weight_education: float = 0.15
    weight_projects: float = 0.20
    weight_communication: float = 0.10

    # --- Hire threshold ---
    hire_threshold: float = 65.0  # Candidates scoring >= 65 are recommended

    @property
    def allowed_extensions_list(self) -> List[str]:
        """Parse allowed extensions string into a list."""
        return [ext.strip().lower() for ext in self.allowed_extensions.split(",")]

    @property
    def max_file_size_bytes(self) -> int:
        """Convert MB to bytes."""
        return self.max_file_size_mb * 1024 * 1024

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


# --- Singleton instance ---
settings = Settings()
