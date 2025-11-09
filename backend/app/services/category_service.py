from __future__ import annotations

from typing import Iterable, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.financial import CategoryType, FinanceCategory


class FinanceCategoryService:
    """负责维护财务分类树结构。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_or_create(self, *, names: Iterable[str], category_type: CategoryType) -> Optional[FinanceCategory]:
        chain: List[str] = [name.strip() for name in names if name and name.strip()]
        if not chain:
            return None

        parent: Optional[FinanceCategory] = None
        path: List[str] = []

        for name in chain:
            path.append(name)
            full_path = "/".join(path)

            stmt = select(FinanceCategory).where(
                FinanceCategory.category_type == category_type,
                FinanceCategory.full_path == full_path,
            )
            category = self._session.execute(stmt).scalar_one_or_none()
            if category is None:
                category = FinanceCategory(
                    name=name,
                    category_type=category_type,
                    parent=parent,
                    level=len(path),
                    full_path=full_path,
                )
                self._session.add(category)
                self._session.flush()
            parent = category

        return parent
