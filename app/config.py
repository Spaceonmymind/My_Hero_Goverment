from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Мой Герой — MVP"
    secret_key: str = "dev-secret-change-me"
    base_url: str = "http://127.0.0.1:8000"
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "lax"
    auth_url_token_enabled: bool = False
    max_bot_token: str = ""
    max_bot_api_base: str = "https://platform-api2.max.ru"
    max_verify_ssl: bool = True
    max_webhook_secret: str = ""
    max_mini_app_url: str = ""
    max_mini_app_button_text: str = "Старт"
    max_welcome_text: str = (
        "Приветствуем Вас в чат-боте Комитета по молодежной политике "
        "Курганской области.\n\n"
        "Бот в игровой форме помогает выполнять задания, развивать навыки "
        "и прокачивать своего виртуального героя через реальные проекты.\n\n"
        "Нажмите на кнопку «Старт», зарегистрируйтесь и узнайте больше."
    )


settings = Settings()
