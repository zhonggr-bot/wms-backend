from datetime import datetime, timedelta
from jose import jwt, JWTError
from app.config import settings
from app.utils.exceptions import BusinessException

def create_access_token(data: dict) -> str:
    """
    生成 JWT token
    data: 要塞进 token 的数据（比如 {"sub": "1", "role": "admin"}）
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict:
    """
    验证并解析 token
    成功返回 token 里的数据，失败抛异常
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise BusinessException(code=401, message="token无效或已过期")
