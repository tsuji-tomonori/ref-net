"""Add integration fields to paper model

Revision ID: 5924fa68ae8b
Revises: 705ebf9a047d
Create Date: 2025-07-12 07:28:21.918404+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5924fa68ae8b'
down_revision: Union[str, Sequence[str], None] = '705ebf9a047d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Paperテーブルに新しいフィールドを追加
    op.add_column('papers', sa.Column('is_crawled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('papers', sa.Column('is_summarized', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('papers', sa.Column('is_generated', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('papers', sa.Column('crawl_depth', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('papers', sa.Column('markdown_path', sa.String(length=2048), nullable=True))
    op.add_column('papers', sa.Column('error_message', sa.Text(), nullable=True))
    op.add_column('papers', sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('papers', sa.Column('url', sa.String(length=2048), nullable=True))
    op.add_column('papers', sa.Column('full_text', sa.Text(), nullable=True))

    # 新しいインデックスを追加
    op.create_index('idx_papers_is_crawled', 'papers', ['is_crawled'])
    op.create_index('idx_papers_is_summarized', 'papers', ['is_summarized'])
    op.create_index('idx_papers_is_generated', 'papers', ['is_generated'])
    op.create_index('idx_papers_crawl_depth', 'papers', ['crawl_depth'])
    op.create_index('idx_papers_markdown_path', 'papers', ['markdown_path'])
    op.create_index('idx_papers_retry_count', 'papers', ['retry_count'])

    # 制約を追加
    op.create_check_constraint('check_crawl_depth_positive', 'papers', 'crawl_depth >= 0')
    op.create_check_constraint('check_retry_count_positive', 'papers', 'retry_count >= 0')

    # 古いカラムとインデックスを削除
    op.drop_index('idx_papers_crawl_status', 'papers')
    op.drop_index('idx_papers_pdf_status', 'papers')
    op.drop_index('idx_papers_summary_status', 'papers')
    op.drop_column('papers', 'crawl_status')
    op.drop_column('papers', 'pdf_status')
    op.drop_column('papers', 'summary_status')

    # Citationsテーブルを作成
    op.create_table('citations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('citing_paper_id', sa.String(length=255), nullable=False),
        sa.Column('cited_paper_id', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['cited_paper_id'], ['papers.paper_id']),
        sa.ForeignKeyConstraint(['citing_paper_id'], ['papers.paper_id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_citations_citing_paper_id', 'citations', ['citing_paper_id'])
    op.create_index('idx_citations_cited_paper_id', 'citations', ['cited_paper_id'])


def downgrade() -> None:
    """Downgrade schema."""
    # Citationsテーブルを削除
    op.drop_index('idx_citations_cited_paper_id', 'citations')
    op.drop_index('idx_citations_citing_paper_id', 'citations')
    op.drop_table('citations')

    # 古いカラムを復元
    op.add_column('papers', sa.Column('summary_status', sa.String(length=50), nullable=False, server_default='pending'))
    op.add_column('papers', sa.Column('pdf_status', sa.String(length=50), nullable=False, server_default='pending'))
    op.add_column('papers', sa.Column('crawl_status', sa.String(length=50), nullable=False, server_default='pending'))
    op.create_index('idx_papers_summary_status', 'papers', ['summary_status'])
    op.create_index('idx_papers_pdf_status', 'papers', ['pdf_status'])
    op.create_index('idx_papers_crawl_status', 'papers', ['crawl_status'])

    # 制約を削除
    op.drop_constraint('check_retry_count_positive', 'papers')
    op.drop_constraint('check_crawl_depth_positive', 'papers')

    # 新しいインデックスを削除
    op.drop_index('idx_papers_retry_count', 'papers')
    op.drop_index('idx_papers_markdown_path', 'papers')
    op.drop_index('idx_papers_crawl_depth', 'papers')
    op.drop_index('idx_papers_is_generated', 'papers')
    op.drop_index('idx_papers_is_summarized', 'papers')
    op.drop_index('idx_papers_is_crawled', 'papers')

    # 新しいカラムを削除
    op.drop_column('papers', 'full_text')
    op.drop_column('papers', 'url')
    op.drop_column('papers', 'retry_count')
    op.drop_column('papers', 'error_message')
    op.drop_column('papers', 'markdown_path')
    op.drop_column('papers', 'crawl_depth')
    op.drop_column('papers', 'is_generated')
    op.drop_column('papers', 'is_summarized')
    op.drop_column('papers', 'is_crawled')
