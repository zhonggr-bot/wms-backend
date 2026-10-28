"""项目常量集中定义，避免业务代码里散落裸字符串"""


class LogAction:
    """操作日志的 action 取值"""
    REGISTER = "register"
    LOGIN = "login"
    CREATE_INBOUND = "create_inbound"
    CREATE_OUTBOUND = "create_outbound"
    APPROVE_OUTBOUND = "approve_outbound"
    CANCEL_OUTBOUND = "cancel_outbound"
    CREATE_PRODUCT = "create_product"
    UPDATE_PRODUCT = "update_product"
    DELETE_PRODUCT = "delete_product"
    CREATE_CATEGORY = "create_category"
    UPDATE_CATEGORY = "update_category"
    DELETE_CATEGORY = "delete_category"


class LogTarget:
    """操作日志的 target 取值"""
    USER = "user"
    PRODUCT = "product"
    CATEGORY = "category"
    OUTBOUND_ORDER = "outbound_order"
