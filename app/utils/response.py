from typing import Any

def success(data: Any = None, message: str = "ok") -> dict:
    """成功响应"""
    return {"code": 0, "message": message, "data": data}

def fail(code: int = 1, message: str = "error", data: Any = None) -> dict:
    """失败响应"""
    return {"code": code, "message": message, "data": data}
