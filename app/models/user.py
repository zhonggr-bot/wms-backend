import enum

from sqlalchemy import Column, Integer, String, DateTime, Enum
from sqlalchemy.sql import func

from app.database import Base

# 角色枚举 —— 就两种
class Role(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)   # unique 已自带索引
    password = Column(String(255), nullable=False)       # 存加密后的密码
    role = Column(Enum(Role), default=Role.USER, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
