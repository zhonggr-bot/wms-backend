from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from app.database import Base

class InboundOrder(Base):
    __tablename__ = "inbound_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)   # 入的是哪个商品
    quantity = Column(Integer, nullable=False)                                  # 入库数量
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=False)      # 谁操作的
    remark = Column(Text, default="")                                           # 备注
    created_at = Column(DateTime, server_default=func.now())
