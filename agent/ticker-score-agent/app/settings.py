# app/workflow/settings.py
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]  # ticker-score-agent/

class Settings(BaseSettings):
    clovastudio_api_key: str = ""
    clovastudio_api_secret: str = ""
    clovastudio_api_gateway: str = "https://clovastudio.apigw.ntruss.com"

    mcp_config_path: str = str(BASE_DIR / "ticker-score-agent/mcp_config.json")

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),  # 절대경로 지정
        extra="ignore"
    )

settings = Settings()
