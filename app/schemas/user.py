from pydantic import BaseModel, ConfigDict, Field
from app.models.user import Role
from datetime import datetime

# ===== 请求模型 =====

class UserRegister(BaseModel):
    """注册请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=100, description="密码")

class UserLogin(BaseModel):
    """登录请求"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")

# ===== 响应模型 =====

class UserResponse(BaseModel):
    """用户信息响应"""
    model_config = ConfigDict(from_attributes=True)   # 允许直接从 SQLAlchemy 对象读取

    id: int
    username: str
    role: Role
    created_at: datetime

class TokenResponse(BaseModel):
    """登录成功返回 token"""
    access_token: str
    token_type: str = "bearer"
    user_info: UserResponse
