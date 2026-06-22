import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    port: int = 3001
    mongodb_uri: str = "mongodb://localhost:27017/kiosk"
    jwt_secret: str
    face_threshold: float = 0.85

    model_config = {
        "env_file": ".env" if os.path.exists(".env") else None,
        "env_file_encoding": "utf-8",
    }


settings = Settings()
