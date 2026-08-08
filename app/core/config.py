from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    app_name: str = "Bhaktivedanta Hospital AI Assistant"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"

    database_path: str = "data/hospital.db"

    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_mode: str = "function_calling"
    max_tool_rounds: int = 4

    bolna_api_key: str = ""
    bolna_base_url: str = "https://api.bolna.ai"
    bolna_agent_id: str = ""
    bolna_webhook_allowed_ip: str = "13.203.39.153"

    emergency_helpline: str = "108"
    front_desk_phone: str = ""

    log_level: str = "INFO"

    @property
    def database_dir(self) -> Path:
        path = Path(self.database_path)
        return path.parent if path.parent != Path(".") else BASE_DIR / path.parent

    @property
    def database_file(self) -> Path:
        path = Path(self.database_path)
        if not path.is_absolute():
            path = BASE_DIR / path
        return path


settings = Settings()
