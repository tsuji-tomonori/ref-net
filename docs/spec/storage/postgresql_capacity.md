# PostgreSQL容量設計仕様書

## 1. 概要

本仕様書は、ObsidianによるRAG論文関係性の可視化システムにおけるPostgreSQLデータベースの容量設計について定義する。
論文メタデータ、引用関係、処理キュー、AI要約データの保存に必要な容量を見積もり、スケーラビリティを考慮した設計を行う。

## 2. データモデル概要

### 2.1 主要テーブル

1. **papers** - 論文メタデータ
2. **paper_relations** - 論文間の引用・被引用関係
3. **processing_queue** - 再帰的処理のためのジョブキュー
4. **paper_summaries** - AI生成要約（オプション）

### 2.2 データ特性

- 論文数: 初期1,000件 → 最大100,000件を想定
- 引用関係: 1論文あたり平均20件（参照10件、被引用10件）
- 更新頻度: 論文メタデータは一度取得後は更新なし、AI要約のみ追加更新

## 3. テーブル別容量見積もり

### 3.1 papers テーブル

#### レコード構造
| カラム | データ型 | サイズ |
|--------|----------|--------|
| paper_id | VARCHAR(40) | 40B |
| title | TEXT | 200B（平均） |
| authors | JSONB | 500B（平均） |
| year | INTEGER | 4B |
| abstract | TEXT | 2KB（平均） |
| citation_count | INTEGER | 4B |
| fields_of_study | JSONB | 200B |
| pdf_url | TEXT | 100B |
| created_at | TIMESTAMP | 8B |
| updated_at | TIMESTAMP | 8B |

**レコードサイズ**: 約3KB/レコード

#### 容量見積もり
| 論文数 | データサイズ | インデックス（30%） | 合計 |
|--------|--------------|-------------------|------|
| 1,000 | 3MB | 0.9MB | 3.9MB |
| 10,000 | 30MB | 9MB | 39MB |
| 100,000 | 300MB | 90MB | 390MB |

### 3.2 paper_relations テーブル

#### レコード構造
| カラム | データ型 | サイズ |
|--------|----------|--------|
| id | BIGSERIAL | 8B |
| source_paper_id | VARCHAR(40) | 40B |
| target_paper_id | VARCHAR(40) | 40B |
| relation_type | VARCHAR(20) | 20B |
| created_at | TIMESTAMP | 8B |

**レコードサイズ**: 約120B/レコード

#### 容量見積もり
| 論文数 | 関係数 | データサイズ | インデックス（50%） | 合計 |
|--------|--------|--------------|-------------------|------|
| 1,000 | 20,000 | 2.4MB | 1.2MB | 3.6MB |
| 10,000 | 200,000 | 24MB | 12MB | 36MB |
| 100,000 | 2,000,000 | 240MB | 120MB | 360MB |

### 3.3 processing_queue テーブル

#### レコード構造
| カラム | データ型 | サイズ |
|--------|----------|--------|
| id | BIGSERIAL | 8B |
| paper_id | VARCHAR(40) | 40B |
| priority | INTEGER | 4B |
| status | VARCHAR(20) | 20B |
| retry_count | INTEGER | 4B |
| created_at | TIMESTAMP | 8B |
| processed_at | TIMESTAMP | 8B |

**レコードサイズ**: 約100B/レコード

#### 容量見積もり
- アクティブキュー: 最大10,000レコード
- データサイズ: 1MB
- インデックス: 0.5MB
- 合計: 1.5MB（固定）

### 3.4 paper_summaries テーブル

#### レコード構造
| カラム | データ型 | サイズ |
|--------|----------|--------|
| paper_id | VARCHAR(40) | 40B |
| summary | TEXT | 5KB（平均） |
| keywords | JSONB | 200B |
| llm_model | VARCHAR(50) | 50B |
| created_at | TIMESTAMP | 8B |

**レコードサイズ**: 約5.3KB/レコード

#### 容量見積もり
| 論文数 | データサイズ | インデックス（20%） | 合計 |
|--------|--------------|-------------------|------|
| 1,000 | 5.3MB | 1.1MB | 6.4MB |
| 10,000 | 53MB | 10.6MB | 63.6MB |
| 100,000 | 530MB | 106MB | 636MB |

## 4. 総合容量見積もり

### 4.1 データベース全体

| 論文数 | テーブル容量 | システム領域（20%） | 合計容量 |
|--------|--------------|-------------------|----------|
| 1,000 | 15.4MB | 3.1MB | 18.5MB |
| 10,000 | 140.1MB | 28MB | 168.1MB |
| 100,000 | 1,387.5MB | 277.5MB | 1,665MB（1.7GB） |

### 4.2 成長予測

- 初年度: 10,000論文（170MB）
- 3年後: 50,000論文（850MB）
- 5年後: 100,000論文（1.7GB）

## 5. パフォーマンス最適化

### 5.1 インデックス設計

#### 主要インデックス
```sql
-- papers テーブル
CREATE INDEX idx_papers_year ON papers(year);
CREATE INDEX idx_papers_citation_count ON papers(citation_count DESC);
CREATE INDEX idx_papers_created_at ON papers(created_at);

-- paper_relations テーブル
CREATE INDEX idx_relations_source ON paper_relations(source_paper_id);
CREATE INDEX idx_relations_target ON paper_relations(target_paper_id);
CREATE INDEX idx_relations_type ON paper_relations(relation_type);

-- processing_queue テーブル
CREATE INDEX idx_queue_status_priority ON processing_queue(status, priority DESC);
CREATE INDEX idx_queue_paper_id ON processing_queue(paper_id);
```

### 5.2 パーティショニング戦略

100,000論文を超える場合の検討事項：
- paper_relationsテーブルの年別パーティショニング
- processing_queueの月別パーティショニング

## 6. バックアップ・リカバリ

### 6.1 バックアップサイズ

| 論文数 | フルバックアップ | 圧縮後（70%削減） |
|--------|-----------------|------------------|
| 10,000 | 168MB | 50MB |
| 100,000 | 1.7GB | 510MB |

### 6.2 バックアップ戦略

- 日次: 増分バックアップ
- 週次: フルバックアップ
- 保持期間: 30日間

## 7. 推奨ハードウェア要件

### 7.1 ストレージ

| 規模 | 推奨容量 | 理由 |
|------|----------|------|
| 小規模（〜10,000論文） | 10GB | データ + バックアップ + 成長余裕 |
| 中規模（〜50,000論文） | 50GB | データ + バックアップ + ログ |
| 大規模（〜100,000論文） | 100GB | データ + バックアップ + WAL |

### 7.2 メモリ

- shared_buffers: データベースサイズの25%
- work_mem: 4MB〜16MB
- maintenance_work_mem: 64MB〜256MB

## 8. 監視項目

### 8.1 容量監視

- データベースサイズ
- テーブル別サイズ
- インデックスサイズ
- 空き容量率（20%以上を維持）

### 8.2 パフォーマンス監視

- クエリ実行時間
- インデックスヒット率
- バキューム実行状況

## 9. 拡張性考慮事項

### 9.1 水平分割オプション

100,000論文を超える場合：
- 論文の分野別データベース分割
- 年代別データベース分割
- Read Replicaの導入

### 9.2 データアーカイブ

- 2年以上アクセスのない論文データの圧縮
- 引用数0の論文の別テーブル移行
- 処理済みキューデータの定期削除
