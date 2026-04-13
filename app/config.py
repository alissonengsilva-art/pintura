from pathlib import Path

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_prefix="PINTURA_",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Painel de Controle PINTURA"
    environment: str = "development"
    secret_key: str = "dev-secret-key"

    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str = "pintura"
    db_user: str = "root"
    db_password: str = "senha"

    @computed_field
    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    @property
    def templates_dir(self) -> Path:
        return BASE_DIR / "app" / "templates"

    @property
    def static_dir(self) -> Path:
        return BASE_DIR / "app" / "static"


settings = Settings()
