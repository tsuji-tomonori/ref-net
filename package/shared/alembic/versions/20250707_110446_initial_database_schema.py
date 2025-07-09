"""Initial database schema

Revision ID: 705ebf9a047d
Revises:
Create Date: 2025-07-07 11:04:46.379819+00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '705ebf9a047d'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # venues table
    op.create_table('venues',
        sa.Column('venue_id', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=500), nullable=False),
        sa.Column('short_name', sa.String(length=100), nullable=True),
        sa.Column('type', sa.String(length=50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('homepage_url', sa.String(length=2048), nullable=True),
        sa.Column('rank', sa.String(length=10), nullable=True),
        sa.Column('h_index', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('venue_id', name=op.f('pk_venues'))
    )
    op.create_index('idx_venues_name', 'venues', ['name'], unique=False)
    op.create_index('idx_venues_rank', 'venues', ['rank'], unique=False)
    op.create_index('idx_venues_short_name', 'venues', ['short_name'], unique=False)
    op.create_index('idx_venues_type', 'venues', ['type'], unique=False)

    # journals table
    op.create_table('journals',
        sa.Column('journal_id', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=500), nullable=False),
        sa.Column('issn', sa.String(length=20), nullable=True),
        sa.Column('publisher', sa.String(length=200), nullable=True),
        sa.Column('homepage_url', sa.String(length=2048), nullable=True),
        sa.Column('impact_factor', sa.Float(), nullable=True),
        sa.Column('h_index', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('journal_id', name=op.f('pk_journals'))
    )
    op.create_index('idx_journals_impact_factor', 'journals', ['impact_factor'], unique=False)
    op.create_index('idx_journals_issn', 'journals', ['issn'], unique=False)
    op.create_index('idx_journals_name', 'journals', ['name'], unique=False)
    op.create_index('idx_journals_publisher', 'journals', ['publisher'], unique=False)

    # authors table
    op.create_table('authors',
        sa.Column('author_id', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=500), nullable=False),
        sa.Column('paper_count', sa.Integer(), nullable=False),
        sa.Column('citation_count', sa.Integer(), nullable=False),
        sa.Column('h_index', sa.Integer(), nullable=True),
        sa.Column('affiliations', sa.Text(), nullable=True),
        sa.Column('homepage_url', sa.String(length=2048), nullable=True),
        sa.Column('orcid', sa.String(length=19), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('citation_count >= 0', name='check_citation_count_positive'),
        sa.CheckConstraint('h_index >= 0', name='check_h_index_positive'),
        sa.CheckConstraint('paper_count >= 0', name='check_paper_count_positive'),
        sa.PrimaryKeyConstraint('author_id', name=op.f('pk_authors'))
    )
    op.create_index('idx_authors_citation_count', 'authors', ['citation_count'], unique=False)
    op.create_index('idx_authors_h_index', 'authors', ['h_index'], unique=False)
    op.create_index('idx_authors_name', 'authors', ['name'], unique=False)
    op.create_index('idx_authors_name_fts', 'authors', ['name'], unique=False)
    op.create_index('idx_authors_orcid', 'authors', ['orcid'], unique=False)
    op.create_index('idx_authors_paper_count', 'authors', ['paper_count'], unique=False)

    # papers table
    op.create_table('papers',
        sa.Column('paper_id', sa.String(length=255), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('abstract', sa.Text(), nullable=True),
        sa.Column('year', sa.Integer(), nullable=True),
        sa.Column('citation_count', sa.Integer(), nullable=False),
        sa.Column('reference_count', sa.Integer(), nullable=False),
        sa.Column('influence_score', sa.Float(), nullable=True),
        sa.Column('crawl_status', sa.String(length=50), nullable=False),
        sa.Column('pdf_status', sa.String(length=50), nullable=False),
        sa.Column('summary_status', sa.String(length=50), nullable=False),
        sa.Column('pdf_url', sa.String(length=2048), nullable=True),
        sa.Column('pdf_hash', sa.String(length=64), nullable=True),
        sa.Column('pdf_size', sa.Integer(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('summary_model', sa.String(length=100), nullable=True),
        sa.Column('summary_created_at', sa.DateTime(), nullable=True),
        sa.Column('venue_id', sa.String(length=255), nullable=True),
        sa.Column('journal_id', sa.String(length=255), nullable=True),
        sa.Column('language', sa.String(length=10), nullable=True),
        sa.Column('is_open_access', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('last_crawled_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint("crawl_status IN ('pending', 'running', 'completed', 'failed')", name='check_crawl_status'),
        sa.CheckConstraint('citation_count >= 0', name='check_citation_count_positive'),
        sa.CheckConstraint('pdf_size >= 0', name='check_pdf_size_positive'),
        sa.CheckConstraint("pdf_status IN ('pending', 'running', 'completed', 'failed', 'unavailable')", name='check_pdf_status'),
        sa.CheckConstraint('reference_count >= 0', name='check_reference_count_positive'),
        sa.CheckConstraint("summary_status IN ('pending', 'running', 'completed', 'failed')", name='check_summary_status'),
        sa.CheckConstraint('year >= 1900 AND year <= 2100', name='check_year_range'),
        sa.ForeignKeyConstraint(['journal_id'], ['journals.journal_id'], name=op.f('fk_papers_journal_id_journals')),
        sa.ForeignKeyConstraint(['venue_id'], ['venues.venue_id'], name=op.f('fk_papers_venue_id_venues')),
        sa.PrimaryKeyConstraint('paper_id', name=op.f('pk_papers'))
    )
    op.create_index('idx_papers_citation_count', 'papers', ['citation_count'], unique=False)
    op.create_index('idx_papers_created_at', 'papers', ['created_at'], unique=False)
    op.create_index('idx_papers_crawl_status', 'papers', ['crawl_status'], unique=False)
    op.create_index('idx_papers_journal_year', 'papers', ['journal_id', 'year'], unique=False)
    op.create_index('idx_papers_last_crawled_at', 'papers', ['last_crawled_at'], unique=False)
    op.create_index('idx_papers_pdf_status', 'papers', ['pdf_status'], unique=False)
    op.create_index('idx_papers_summary_status', 'papers', ['summary_status'], unique=False)
    op.create_index('idx_papers_title_fts', 'papers', ['title'], unique=False)
    op.create_index('idx_papers_updated_at', 'papers', ['updated_at'], unique=False)
    op.create_index('idx_papers_venue_year', 'papers', ['venue_id', 'year'], unique=False)
    op.create_index('idx_papers_year', 'papers', ['year'], unique=False)

    # paper_authors association table
    op.create_table('paper_authors',
        sa.Column('paper_id', sa.String(), nullable=False),
        sa.Column('author_id', sa.String(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['author_id'], ['authors.author_id'], ),
        sa.ForeignKeyConstraint(['paper_id'], ['papers.paper_id'], ),
        sa.PrimaryKeyConstraint('paper_id', 'author_id')
    )
    op.create_index('idx_paper_authors_author_id', 'paper_authors', ['author_id'], unique=False)
    op.create_index('idx_paper_authors_paper_id', 'paper_authors', ['paper_id'], unique=False)
    op.create_index('idx_paper_authors_position', 'paper_authors', ['paper_id', 'position'], unique=False)

    # paper_relations table
    op.create_table('paper_relations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source_paper_id', sa.String(length=255), nullable=False),
        sa.Column('target_paper_id', sa.String(length=255), nullable=False),
        sa.Column('relation_type', sa.String(length=50), nullable=False),
        sa.Column('hop_count', sa.Integer(), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('relevance_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('hop_count >= 1', name='check_hop_count_positive'),
        sa.CheckConstraint("relation_type IN ('citation', 'reference')", name='check_relation_type'),
        sa.CheckConstraint('source_paper_id != target_paper_id', name='check_no_self_reference'),
        sa.ForeignKeyConstraint(['source_paper_id'], ['papers.paper_id'], name=op.f('fk_paper_relations_source_paper_id_papers')),
        sa.ForeignKeyConstraint(['target_paper_id'], ['papers.paper_id'], name=op.f('fk_paper_relations_target_paper_id_papers')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_paper_relations')),
        sa.UniqueConstraint('source_paper_id', 'target_paper_id', 'relation_type', name='uq_paper_relation')
    )
    op.create_index('idx_paper_relations_hop_count', 'paper_relations', ['hop_count'], unique=False)
    op.create_index('idx_paper_relations_source', 'paper_relations', ['source_paper_id'], unique=False)
    op.create_index('idx_paper_relations_source_hop', 'paper_relations', ['source_paper_id', 'hop_count'], unique=False)
    op.create_index('idx_paper_relations_target', 'paper_relations', ['target_paper_id'], unique=False)
    op.create_index('idx_paper_relations_target_hop', 'paper_relations', ['target_paper_id', 'hop_count'], unique=False)
    op.create_index('idx_paper_relations_type', 'paper_relations', ['relation_type'], unique=False)

    # paper_external_ids table
    op.create_table('paper_external_ids',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('paper_id', sa.String(length=255), nullable=False),
        sa.Column('id_type', sa.String(length=50), nullable=False),
        sa.Column('external_id', sa.String(length=500), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("id_type IN ('DOI', 'ArXiv', 'PubMed', 'PMCID', 'MAG', 'DBLP', 'ACL')", name='check_id_type'),
        sa.ForeignKeyConstraint(['paper_id'], ['papers.paper_id'], name=op.f('fk_paper_external_ids_paper_id_papers')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_paper_external_ids')),
        sa.UniqueConstraint('paper_id', 'id_type', 'external_id', name='uq_paper_external_id')
    )
    op.create_index('idx_paper_external_ids_external_id', 'paper_external_ids', ['external_id'], unique=False)
    op.create_index('idx_paper_external_ids_paper_id', 'paper_external_ids', ['paper_id'], unique=False)
    op.create_index('idx_paper_external_ids_type', 'paper_external_ids', ['id_type'], unique=False)
    op.create_index('idx_paper_external_ids_type_external', 'paper_external_ids', ['id_type', 'external_id'], unique=False)

    # paper_fields_of_study table
    op.create_table('paper_fields_of_study',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('paper_id', sa.String(length=255), nullable=False),
        sa.Column('field_name', sa.String(length=200), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['paper_id'], ['papers.paper_id'], name=op.f('fk_paper_fields_of_study_paper_id_papers')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_paper_fields_of_study')),
        sa.UniqueConstraint('paper_id', 'field_name', name='uq_paper_field_of_study')
    )
    op.create_index('idx_paper_fields_of_study_confidence', 'paper_fields_of_study', ['confidence_score'], unique=False)
    op.create_index('idx_paper_fields_of_study_field_name', 'paper_fields_of_study', ['field_name'], unique=False)
    op.create_index('idx_paper_fields_of_study_paper_id', 'paper_fields_of_study', ['paper_id'], unique=False)

    # paper_keywords table
    op.create_table('paper_keywords',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('paper_id', sa.String(length=255), nullable=False),
        sa.Column('keyword', sa.String(length=200), nullable=False),
        sa.Column('relevance_score', sa.Float(), nullable=True),
        sa.Column('extraction_method', sa.String(length=100), nullable=True),
        sa.Column('model_name', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['paper_id'], ['papers.paper_id'], name=op.f('fk_paper_keywords_paper_id_papers')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_paper_keywords')),
        sa.UniqueConstraint('paper_id', 'keyword', name='uq_paper_keyword')
    )
    op.create_index('idx_paper_keywords_extraction_method', 'paper_keywords', ['extraction_method'], unique=False)
    op.create_index('idx_paper_keywords_keyword', 'paper_keywords', ['keyword'], unique=False)
    op.create_index('idx_paper_keywords_paper_id', 'paper_keywords', ['paper_id'], unique=False)
    op.create_index('idx_paper_keywords_relevance_score', 'paper_keywords', ['relevance_score'], unique=False)

    # processing_queue table
    op.create_table('processing_queue',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('paper_id', sa.String(length=255), nullable=False),
        sa.Column('task_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('max_retries', sa.Integer(), nullable=False),
        sa.Column('execution_time_seconds', sa.Float(), nullable=True),
        sa.Column('parameters', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint('max_retries >= 0', name='check_max_retries_positive'),
        sa.CheckConstraint('priority >= 0', name='check_priority_positive'),
        sa.CheckConstraint('retry_count >= 0', name='check_retry_count_positive'),
        sa.CheckConstraint("status IN ('pending', 'running', 'completed', 'failed')", name='check_status'),
        sa.CheckConstraint("task_type IN ('crawl', 'summarize', 'generate')", name='check_task_type'),
        sa.ForeignKeyConstraint(['paper_id'], ['papers.paper_id'], name=op.f('fk_processing_queue_paper_id_papers')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_processing_queue'))
    )
    op.create_index('idx_processing_queue_created_at', 'processing_queue', ['created_at'], unique=False)
    op.create_index('idx_processing_queue_paper_id', 'processing_queue', ['paper_id'], unique=False)
    op.create_index('idx_processing_queue_priority', 'processing_queue', ['priority'], unique=False)
    op.create_index('idx_processing_queue_status', 'processing_queue', ['status'], unique=False)
    op.create_index('idx_processing_queue_status_priority', 'processing_queue', ['status', 'priority'], unique=False)
    op.create_index('idx_processing_queue_task_status', 'processing_queue', ['task_type', 'status'], unique=False)
    op.create_index('idx_processing_queue_task_type', 'processing_queue', ['task_type'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('processing_queue')
    op.drop_table('paper_keywords')
    op.drop_table('paper_fields_of_study')
    op.drop_table('paper_external_ids')
    op.drop_table('paper_relations')
    op.drop_table('paper_authors')
    op.drop_table('papers')
    op.drop_table('authors')
    op.drop_table('journals')
    op.drop_table('venues')
