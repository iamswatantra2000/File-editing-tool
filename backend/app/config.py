from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    agent_mode: str = "auto"  # auto | real | mock
    storage_dir: str = "./storage"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def resolved_agent_mode(self) -> str:
        if self.agent_mode == "auto":
            return "real" if self.anthropic_api_key else "mock"
        return self.agent_mode


settings = Settings()
