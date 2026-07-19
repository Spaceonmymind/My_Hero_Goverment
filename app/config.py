from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Мой Герой — MVP"
    secret_key: str = "dev-secret-change-me"
    base_url: str = "http://127.0.0.1:8000"
    max_bot_token: str = ""
    max_bot_api_base: str = "https://platform-api2.max.ru"
    max_webhook_secret: str = ""
    max_mini_app_url: str = ""
    max_mini_app_button_text: str = "Открыть мини-приложение"
    max_welcome_text: str = (
        "Привет! Это мини-приложение «Мой герой».\n\n"
        "Здесь можно выполнять задания, отправлять работы на проверку "
        "и следить за своими баллами.\n\n"
        "Нажми кнопку ниже, чтобы открыть мини-приложение."
    )


settings = Settings()
