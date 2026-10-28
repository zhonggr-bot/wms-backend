from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

# 拼出数据库连接字符串
SQLALCHEMY_DATABASE_URL = (
    f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}"
    f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    f"?charset=utf8mb4"
)

# 创建引擎（相当于数据库的"大门"）
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,          # 连接失效时自动重连
    echo=True                    # 控制台打印 SQL 语句（调试用，后面可以关掉）
)

# 创建会话工厂（每次操作数据库用的"工作台"）
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 所有模型类的"老祖宗"
Base = declarative_base()

# FastAPI 依赖注入用的函数 —— 每次请求来给一个会话，用完自动关掉
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
