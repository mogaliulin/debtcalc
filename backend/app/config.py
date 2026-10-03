from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str = "postgresql+asyncpg://debts:debts@localhost:5432/debts"

    # Публичный адрес сайта (без слэша в конце). Из него строится redirect_uri для Яндекс ID:
    # {public_url}/api/auth/yandex/callback — этот адрес нужно указать в настройках приложения Яндекс OAuth.
    public_url: str = "http://localhost:5173"
    yandex_client_id: str = ""
    yandex_client_secret: str = ""
    # Секрет для подписи временной cookie с state/PKCE на время входа
    secret_key: str = "change-me"

    session_cookie_name: str = "session"
    session_ttl_days: int = 30

    # Разрешает запросы без входа (фиксированный тестовый пользователь). Только для разработки!
    dev_auth_bypass: bool = False

    @property
    def yandex_redirect_uri(self) -> str:
        return f"{self.public_url.rstrip('/')}/api/auth/yandex/callback"

    @property
    def cookie_secure(self) -> bool:
        return self.public_url.startswith("https://")


@lru_cache
def get_settings() -> Settings:
    return Settings()
