# config.py
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseSettings):
    BOT_TOKEN: str = Field(..., env="BOT_TOKEN")
    API_ID: int = Field(..., env="API_ID")
    API_HASH: str = Field(..., env="API_HASH")
    MONGODB_URI: str = Field(..., env="MONGODB_URI")
    DB_NAME: str = Field(..., env="DB_NAME")
    SQLITE_DB_PATH: str = Field(..., env="DB_PATH")
    MAX_FORWARD_BATCH: int = Field(100, env="MAX_FORWARD_BATCH")
    FORWARD_DELAY_MIN: int = Field(60, env="FORWARD_DELAY_MIN")
    FORWARD_DELAY_MAX: int = Field(120, env="FORWARD_DELAY_MAX")

    class Config:
        env_file = ".env"