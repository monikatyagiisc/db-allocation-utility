from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "postgres"
    db_password: str = "postgres"
    db_name: str = "db_allocation"

    api_port: int = 8080
    frontend_port: int = 3000

    secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    log_level: str = "INFO"
    log_file: str | None = ".local/logs/api.log"
    log_request_body: bool = True

    # Email: smtp (legacy) or graph (recommended for Microsoft 365 — SMTP basic auth often disabled)
    email_enabled: bool = False
    email_provider: str = "smtp"  # smtp | graph

    smtp_host: str = "smtp.office365.com"
    smtp_port: int = 587
    smtp_use_tls: bool = True
    smtp_user: str = ""
    smtp_password: str = ""
    mail_from: str = ""

    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""
    graph_send_as: str = ""  # mailbox UPN to send from (defaults to mail_from)

    @computed_field
    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()
