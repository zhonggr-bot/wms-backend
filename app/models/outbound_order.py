import enum

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum
from sqlalchemy.sql import func

from app.database import Base

class OutboundStatus(str, enum.Enum):
    PENDING = "pending"      # 待审批
    APPROVED = "approved"    # 审批通过 → 出库成功
    REJECTED = "rejected"    # 审批驳回
    CANCELLED = "cancelled"  # 用户自己撤回

class OutboundOrder(Base):
    __tablename__ = "outbound_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)                                   # 申请出库数量
    applicant_id = Column(Integer, ForeignKey("users.id"), nullable=False)       # 申请人
    approver_id = Column(Integer, ForeignKey("users.id"))                        # 审批人（管理员）
    status = Column(Enum(OutboundStatus), default=OutboundStatus.PENDING)
    reject_reason = Column(String(500), default="")                              # 驳回原因
    remark = Column(Text, default="")
    approved_at = Column(DateTime)                                               # 审批时间
    created_at = Column(DateTime, server_default=func.now())
