from fastapi import Depends
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from app.database import get_db
from app.utils.jwt_utils import decode_access_token
from app.models.user import User, Role
from app.utils.exceptions import PermissionException, BusinessException

# 从请求头 Authorization 里取值
oauth2_scheme = APIKeyHeader(name="Authorization", auto_error=False)

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    # 手动判断有没有带 token
    if not token:
        raise BusinessException(code=401, message="未登录，请先登录")

    actual_token = token.replace("Bearer ", "").replace("bearer ", "")

    # 用 actual_token 去解析
    payload = decode_access_token(actual_token)
    user_id: str = payload.get("sub") # type: ignore
    if user_id is None:
        raise BusinessException(code=401, message="token数据无效")

    # sub 必须是数字，非数字一律按无效 token 处理
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        raise BusinessException(code=401, message="token数据无效")

    user = db.query(User).filter(User.id == uid).first()
    if user is None:
        raise BusinessException(code=401, message="用户不存在")

    return user

def get_current_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    if current_user.role != Role.ADMIN: # type: ignore
        raise PermissionException(message="需要管理员权限")
    return current_user
