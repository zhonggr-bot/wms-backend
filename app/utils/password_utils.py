from passlib.context import CryptContext

# 创建加密器，使用 bcrypt 算法
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(plain_password: str) -> str:
    """把明文密码加密成密文"""
    return pwd_context.hash(plain_password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码和密文是否匹配"""
    return pwd_context.verify(plain_password, hashed_password)
