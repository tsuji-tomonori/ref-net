"""論文モデル定義（統合モデル）."""

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .database import Base, Paper


class Citation(Base):
    """引用関係モデル."""

    __tablename__ = "citations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    citing_paper_id = Column(String(255), ForeignKey("papers.paper_id"), nullable=False)
    cited_paper_id = Column(String(255), ForeignKey("papers.paper_id"), nullable=False)

    # リレーションシップ
    citing_paper = relationship("Paper", foreign_keys=[citing_paper_id])
    cited_paper = relationship("Paper", foreign_keys=[cited_paper_id])


__all__ = ["Paper", "Citation"]
