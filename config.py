# config.py
from pydantic import BaseModel, ValidationError, ValidationInfo, field_validator
import os
from dotenv import load_dotenv
import logging

class Config(BaseModel):
    BOT_TOKEN: str
    API_ID: int
    API_HASH: str
    MAX_FORWARD_BATCH: int = 100
    FORWARD_DELAY_MIN: int = 60
    FORWARD_DELAY_MAX: int = 120
    MONGODB_URI: str
    DB_NAME: str

    @field_validator('API_ID', 'MAX_FORWARD_BATCH', 'FORWARD_DELAY_MIN', 'FORWARD_DELAY_MAX')
    def must_be_int(cls, v):
        if not isinstance(v, int):
            raise ValueError('must be an integer')
        return v

def load_config():
    load_dotenv()

    try:
        config = Config(
            BOT_TOKEN=os.getenv('BOT_TOKEN'),
            API_ID=int(os.getenv('API_ID')),
            API_HASH=os.getenv('API_HASH'),
            MAX_FORWARD_BATCH=int(os.getenv('MAX_FORWARD_BATCH', 100)),
            FORWARD_DELAY_MIN=int(os.getenv('FORWARD_DELAY_MIN', 60)),
            FORWARD_DELAY_MAX=int(os.getenv('FORWARD_DELAY_MAX', 120)),
            MONGODB_URI=os.getenv('MONGODB_URI'),
            DB_NAME=os.getenv('DB_NAME')
        )
    except ValueError as e:
        raise ValueError(f"Configuration error: {e}")

    return config