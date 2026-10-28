"""列表接口统一分页"""

from typing import Any

from sqlalchemy.orm import Query


def paginate(query: Query, page: int, page_size: int) -> tuple[int, list[Any]]:
    """
    对已经 order_by 过的查询做分页
    返回 (总条数, 当前页数据)
    """
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return total, items
