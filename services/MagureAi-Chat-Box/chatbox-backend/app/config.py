import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from urllib.parse import quote_plus  

class Settings(BaseSettings):
    # Database settings
    PGHOST: str
    PGDATABASE: str
    PGPORT: int = 5432  # Default PostgreSQL port
    PGUSER: str
    PGPASSWORD: str
    PGSSLMODE: str = "disable"
    PGCHANNELBINDING: str = "require"
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    # API KEY
    OPENAI_API_KEY: str 
    ANTHROPIC_API_KEY:str
    # Application settings
    ENVIRONMENT: str = "production"
        
    @property
    def DATABASE_URL(self) -> str:
        password = quote_plus(self.PGPASSWORD)
        url = f"postgresql://{self.PGUSER}:{password}@{self.PGHOST}/{self.PGDATABASE}"
        if self.PGSSLMODE and self.PGSSLMODE != "disable":
            url += f"?sslmode={self.PGSSLMODE}"
        return url

    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
