-- RefNet データベース初期化

-- 拡張機能の有効化
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 初期インデックスの作成（パフォーマンス最適化）
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_papers_year
    ON papers(year) WHERE year IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_papers_citation_count
    ON papers(citation_count) WHERE citation_count > 0;

-- 全文検索インデックス
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_papers_title_fts
    ON papers USING gin(to_tsvector('english', title));

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_papers_abstract_fts
    ON papers USING gin(to_tsvector('english', abstract));

-- パフォーマンス設定
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
ALTER SYSTEM SET log_statement = 'all';
ALTER SYSTEM SET log_duration = on;

-- 統計情報更新
ANALYZE;

SELECT 'RefNet database initialized successfully' as status;
