from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from app.database import Base

class OperationLog(Base):
    __tablename__ = "operation_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))   # 谁操作的（用户被删时日志保留）
    action = Column(String(50), nullable=False)                # 操作类型：login / create_product / approve_outbound ...
    target = Column(String(50), default="")                     # 操作对象：product / inbound_order / ...
    target_id = Column(Integer)                                 # 操作对象的 id（比如商品id=3）
    detail = Column(Text, default="")                           # 详细信息（JSON格式，存附加数据）
    created_at = Column(DateTime, server_default=func.now())
