from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import get_db
from app.utils.response import success
from app.utils.exceptions import BusinessException
from app.utils.jwt_utils import create_access_token
from app.utils.password_utils import hash_password, verify_password
from app.models.user import User, Role
from app.models.operation_log import OperationLog
from app.schemas.user import UserRegister, UserLogin, UserResponse, TokenResponse
from app.dependencies import get_current_user
from app.constants import LogAction, LogTarget

router = APIRouter(prefix="/api/auth", tags=["用户认证"])

@router.post("/register")
def register(data: UserRegister, db: Session = Depends(get_db)):
    """用户注册"""
    # 1. 检查用户名是否已存在
    existing = db.query(User).filter(User.username == data.username).first()
    if existing:
        raise BusinessException(code=400, message="用户名已存在")

    # 2. 加密密码 + 创建用户
    hashed = hash_password(data.password)
    user = User(username=data.username, password=hashed, role=Role.USER)
    db.add(user)
    db.flush()   # 先拿到自增 id（事务内执行，尚未提交）

    # 3. 自动记录一条操作日志
    log = OperationLog(
        user_id=user.id,
        action=LogAction.REGISTER,
        target=LogTarget.USER,
        target_id=user.id
    )
    db.add(log)

    # 4. 用户和日志在同一个事务里一次提交
    try:
        db.commit()
    except IntegrityError:
        # 并发注册撞唯一索引：回滚并返回业务错误
        db.rollback()
        raise BusinessException(code=400, message="用户名已存在")
    db.refresh(user)

    return success(data=UserResponse.model_validate(user), message="注册成功")

@router.post("/login")
def login(data: UserLogin, db: Session = Depends(get_db)):
    """用户登录"""
    # 1. 查用户
    user = db.query(User).filter(User.username == data.username).first()
    if not user:
        raise BusinessException(code=401, message="用户名或密码错误")

    # 2. 验密码
    if not verify_password(data.password, user.password): # type: ignore
        raise BusinessException(code=401, message="用户名或密码错误")

    # 3. 生成 JWT token
    token = create_access_token(data={"sub": str(user.id), "role": user.role.value})

    # 4. 记录登录日志
    log = OperationLog(
        user_id=user.id,
        action=LogAction.LOGIN,
        target=LogTarget.USER,
        target_id=user.id
    )
    db.add(log)
    db.commit()

    # 5. 用响应模型组装返回（字段结构由 TokenResponse 保证）
    result = TokenResponse(
        access_token=token,
        user_info=UserResponse.model_validate(user)
    )
    return success(data=result, message="登录成功")

@router.get("/me")
def get_my_info(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息（测试 token 用）"""
    return success(data=UserResponse.model_validate(current_user))
