from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（app/config.py 往上两级）
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    # .env 用绝对路径定位，从任意工作目录启动都能读到
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env")

    # 数据库配置 —— 真实值写在 .env，这里的默认值只是占位
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "change_me"
    DB_NAME: str = "wms_db"

    # JWT 配置 —— 真实密钥写在 .env，这里的默认值只是占位
    SECRET_KEY: str = "change_me_in_env"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # token 有效期24小时

    # CORS 白名单：只放行这些前端地址，可用 .env 覆盖（JSON 数组格式）
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

settings = Settings()
