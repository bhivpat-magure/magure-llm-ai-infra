import os
from functools import lru_cache
from pydantic_settings import BaseSettings  # ✅ Correct spelling and source

class Settings(BaseSettings):
    # Database settings
    PGHOST: str
    PGDATABASE: str
    PGUSER: str
    PGPASSWORD: str
    PGSSLMODE: str = "disable"
    PGCHANNELBINDING: str = "require"
    
    # Application settings
    ENVIRONMENT: str = "development"
    
    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.PGUSER}:{self.PGPASSWORD}@{self.PGHOST}/"
            f"{self.PGDATABASE}?sslmode={self.PGSSLMODE}"
        )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
