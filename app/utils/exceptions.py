class BusinessException(Exception):
    """业务异常 —— 自己定义的，比如库存不足、没权限"""
    def __init__(self, code: int = 1, message: str = "业务异常"):
        self.code = code
        self.message = message
        super().__init__(message)

# 几个常用的预设异常
class NotFoundException(BusinessException):
    def __init__(self, message: str = "资源不存在"):
        super().__init__(code=404, message=message)

class PermissionException(BusinessException):
    def __init__(self, message: str = "无权限操作"):
        super().__init__(code=403, message=message)

class ValidationException(BusinessException):
    def __init__(self, message: str = "参数校验失败"):
        super().__init__(code=400, message=message)
