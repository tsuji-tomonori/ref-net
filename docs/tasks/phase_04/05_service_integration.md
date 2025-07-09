# Phase 4-05: サービス間連携設定

## 目的
RefNetシステムの各サービス（API、Crawler、Summarizer、Generator）が適切に連携して動作するための設定を実装する。

## 問題点
- サービス間の通信フローが不完全
- エンドツーエンドの処理フローが未実装
- 環境変数の設定が不足
- エラーハンドリングとリトライ機構が不十分

## 実装内容

### 1. APIサービスの連携機能実装

#### package/api/src/refnet_api/routers/papers.py（更新）
```python
from refnet_shared.celery_app import app as celery_app

@router.post("/papers/crawl")
async def trigger_paper_crawl(
    paper_url: str,
    db: Session = Depends(get_db)
):
    """論文のクロールをトリガー"""
    try:
        # Semantic Scholar Paper IDを抽出
        paper_id = extract_paper_id(paper_url)

        # データベースに論文エントリを作成
        paper = Paper(
            paper_id=paper_id,
            url=paper_url,
            is_crawled=False,
            is_summarized=False,
            is_generated=False
        )
        db.add(paper)
        db.commit()

        # Crawlerタスクをキュー
        task = celery_app.send_task(
            'refnet_crawler.tasks.crawl_task.crawl_paper',
            args=[paper.paper_id],
            queue='crawler'
        )

        return {
            "status": "queued",
            "paper_id": paper.paper_id,
            "task_id": task.id
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/papers/{paper_id}/status")
async def get_paper_status(
    paper_id: str,
    db: Session = Depends(get_db)
):
    """論文の処理状況を取得"""
    paper = db.query(Paper).filter(Paper.paper_id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    return {
        "paper_id": paper.paper_id,
        "is_crawled": paper.is_crawled,
        "is_summarized": paper.is_summarized,
        "is_generated": paper.is_generated,
        "created_at": paper.created_at,
        "updated_at": paper.updated_at
    }
```

### 2. Crawlerサービスの連携実装

#### package/crawler/src/refnet_crawler/tasks/crawl_task.py（更新）
```python
from refnet_shared.celery_app import app as celery_app

@celery_app.task(bind=True, name='refnet_crawler.tasks.crawl_task.crawl_paper')
def crawl_paper(self, paper_id: str):
    """論文をクロールし、次の処理をトリガー"""
    try:
        with get_session() as session:
            paper = session.query(Paper).filter(Paper.paper_id == paper_id).first()
            if not paper:
                raise ValueError(f"Paper {paper_id} not found")

            # Semantic Scholar APIから論文情報を取得
            client = SemanticScholarClient()
            paper_data = client.get_paper(paper_id)

            # 論文情報を更新
            paper.title = paper_data['title']
            paper.abstract = paper_data['abstract']
            paper.authors = json.dumps(paper_data['authors'])
            paper.year = paper_data['year']
            paper.venue = paper_data['venue']
            paper.pdf_url = paper_data.get('openAccessPdf', {}).get('url')
            paper.is_crawled = True

            # 参照論文を追加
            for ref in paper_data.get('references', []):
                if ref.get('paperId'):
                    ref_paper = Paper(
                        paper_id=ref['paperId'],
                        title=ref.get('title', ''),
                        is_crawled=False,
                        is_summarized=False,
                        is_generated=False
                    )
                    session.merge(ref_paper)  # 既存の場合は更新

                    # 関係を作成
                    citation = Citation(
                        citing_paper_id=paper.paper_id,
                        cited_paper_id=ref['paperId']
                    )
                    session.merge(citation)

            # 被引用論文を追加
            for cit in paper_data.get('citations', []):
                if cit.get('paperId'):
                    cit_paper = Paper(
                        paper_id=cit['paperId'],
                        title=cit.get('title', ''),
                        is_crawled=False,
                        is_summarized=False,
                        is_generated=False
                    )
                    session.merge(cit_paper)

                    # 関係を作成
                    citation = Citation(
                        citing_paper_id=cit['paperId'],
                        cited_paper_id=paper.paper_id
                    )
                    session.merge(citation)

            session.commit()

            # PDFが利用可能な場合、要約タスクをトリガー
            if paper.pdf_url:
                celery_app.send_task(
                    'refnet_summarizer.tasks.summarize_task.summarize_paper',
                    args=[paper.paper_id],
                    queue='summarizer'
                )
            else:
                # PDFがない場合は直接Markdown生成へ
                celery_app.send_task(
                    'refnet_generator.tasks.generate_task.generate_markdown',
                    args=[paper.paper_id],
                    queue='generator'
                )

            return {
                'status': 'success',
                'paper_id': paper.paper_id,
                'title': paper.title,
                'references_count': len(paper_data.get('references', [])),
                'citations_count': len(paper_data.get('citations', []))
            }

    except Exception as e:
        self.retry(exc=e, countdown=60, max_retries=3)
```

### 3. Summarizerサービスの連携実装

#### package/summarizer/src/refnet_summarizer/tasks/summarize_task.py（更新）
```python
from refnet_shared.celery_app import app as celery_app

@celery_app.task(bind=True, name='refnet_summarizer.tasks.summarize_task.summarize_paper')
def summarize_paper(self, paper_id: str):
    """論文を要約し、次の処理をトリガー"""
    try:
        with get_session() as session:
            paper = session.query(Paper).filter(Paper.paper_id == paper_id).first()
            if not paper:
                raise ValueError(f"Paper {paper_id} not found")

            if not paper.pdf_url:
                # PDFがない場合はスキップ
                paper.is_summarized = True
                paper.summary = "PDF not available"
                session.commit()

                # Markdown生成をトリガー
                celery_app.send_task(
                    'refnet_generator.tasks.generate_task.generate_markdown',
                    args=[paper.paper_id],
                    queue='generator'
                )
                return {'status': 'skipped', 'reason': 'no_pdf'}

            # PDFをダウンロードして処理
            pdf_processor = PDFProcessor()
            pdf_content = pdf_processor.download_pdf(paper.pdf_url)
            text_content = pdf_processor.extract_text(pdf_content)

            # AI要約を生成
            ai_client = get_ai_client()
            summary = ai_client.summarize(
                text_content,
                max_length=1000,
                language='japanese'
            )

            # 要約を保存
            paper.summary = summary
            paper.full_text = text_content[:50000]  # 最初の50,000文字を保存
            paper.is_summarized = True
            session.commit()

            # Markdown生成をトリガー
            celery_app.send_task(
                'refnet_generator.tasks.generate_task.generate_markdown',
                args=[paper.paper_id],
                queue='generator'
            )

            return {
                'status': 'success',
                'paper_id': paper.paper_id,
                'summary_length': len(summary)
            }

    except Exception as e:
        self.retry(exc=e, countdown=120, max_retries=3)
```

### 4. Generatorサービスの連携実装

#### package/generator/src/refnet_generator/tasks/generate_task.py（更新）
```python
from refnet_shared.celery_app import app as celery_app
import os
from pathlib import Path

@celery_app.task(bind=True, name='refnet_generator.tasks.generate_task.generate_markdown')
def generate_markdown(self, paper_id: str):
    """論文のMarkdownを生成"""
    try:
        with get_session() as session:
            paper = session.query(Paper).filter(Paper.paper_id == paper_id).first()
            if not paper:
                raise ValueError(f"Paper {paper_id} not found")

            # 関連論文情報を取得
            references = session.query(Paper).join(
                Citation, Citation.cited_paper_id == Paper.paper_id
            ).filter(Citation.citing_paper_id == paper_id).all()

            citations = session.query(Paper).join(
                Citation, Citation.citing_paper_id == Paper.paper_id
            ).filter(Citation.cited_paper_id == paper_id).all()

            # Markdown生成
            generator = GeneratorService()
            markdown_content = generator.generate_paper_markdown(
                paper=paper,
                references=references,
                citations=citations
            )

            # ファイルパスを生成
            output_dir = Path(os.getenv('OBSIDIAN_VAULT_PATH', '/output/obsidian'))
            output_dir.mkdir(parents=True, exist_ok=True)

            # ファイル名をサニタイズ
            safe_title = "".join(c for c in paper.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_title = safe_title[:100]  # 最大100文字
            filename = f"{safe_title}_{paper.paper_id[:8]}.md"
            filepath = output_dir / filename

            # Markdownファイルを保存
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

            # データベースを更新
            paper.markdown_path = str(filepath)
            paper.is_generated = True
            session.commit()

            # 参照論文の自動クロールをトリガー（深さ制限あり）
            current_depth = paper.crawl_depth or 0
            max_depth = int(os.getenv('MAX_CRAWL_DEPTH', '2'))

            if current_depth < max_depth:
                for ref in references[:5]:  # 最大5つの参照論文をクロール
                    if not ref.is_crawled:
                        ref.crawl_depth = current_depth + 1
                        session.commit()

                        celery_app.send_task(
                            'refnet_crawler.tasks.crawl_task.crawl_paper',
                            args=[ref.paper_id],
                            queue='crawler',
                            countdown=10  # 10秒後に実行
                        )

            return {
                'status': 'success',
                'paper_id': paper.paper_id,
                'filepath': str(filepath),
                'references_triggered': min(5, len([r for r in references if not r.is_crawled]))
            }

    except Exception as e:
        self.retry(exc=e, countdown=60, max_retries=3)
```

### 5. 環境変数の完全な設定

#### .env.example（完全版）
```env
# PostgreSQL
POSTGRES_DB=refnet
POSTGRES_USER=refnet
POSTGRES_PASSWORD=changeme
DATABASE_URL=postgresql://refnet:changeme@postgres:5432/refnet

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# API Keys
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
SEMANTIC_SCHOLAR_API_KEY=your-semantic-scholar-api-key

# Flower
FLOWER_USER=admin
FLOWER_PASSWORD=changeme

# Output
OBSIDIAN_VAULT_PATH=/output/obsidian

# Crawling
MAX_CRAWL_DEPTH=2
CRAWL_DELAY_SECONDS=1

# AI Service
AI_PROVIDER=openai  # or anthropic
AI_MODEL=gpt-4-turbo-preview
AI_MAX_TOKENS=4000
AI_TEMPERATURE=0.7

# Service URLs (内部通信用)
API_URL=http://api:8000
CRAWLER_URL=http://crawler:8001
SUMMARIZER_URL=http://summarizer:8002
GENERATOR_URL=http://generator:8003
```

### 6. データベースモデルの更新

#### package/shared/src/refnet_shared/models/paper.py（追加フィールド）
```python
class Paper(Base):
    __tablename__ = "papers"

    # 既存のフィールド...

    # 追加フィールド
    crawl_depth = Column(Integer, default=0)  # クロールの深さ
    markdown_path = Column(String, nullable=True)  # 生成されたMarkdownのパス
    error_message = Column(Text, nullable=True)  # エラーメッセージ
    retry_count = Column(Integer, default=0)  # リトライ回数
```

### 7. Alembicマイグレーション

#### 新しいマイグレーションファイルを生成
```bash
cd package/shared
alembic revision -m "Add integration fields to paper model"
```

#### マイグレーションファイルの内容
```python
def upgrade():
    op.add_column('papers', sa.Column('crawl_depth', sa.Integer(), default=0))
    op.add_column('papers', sa.Column('markdown_path', sa.String(), nullable=True))
    op.add_column('papers', sa.Column('error_message', sa.Text(), nullable=True))
    op.add_column('papers', sa.Column('retry_count', sa.Integer(), default=0))

def downgrade():
    op.drop_column('papers', 'retry_count')
    op.drop_column('papers', 'error_message')
    op.drop_column('papers', 'markdown_path')
    op.drop_column('papers', 'crawl_depth')
```

## 動作確認手順

### 1. システム全体の起動
```bash
# 環境変数を設定
cp .env.example .env
# .envファイルを編集してAPIキーを設定

# Dockerコンテナを起動
scripts/docker-dev.sh up

# データベースマイグレーション
scripts/docker-dev.sh migrate
```

### 2. 論文クロールのトリガー
```bash
# APIエンドポイント経由で論文をクロール
curl -X POST http://localhost:8000/api/papers/crawl \
  -H "Content-Type: application/json" \
  -d '{"paper_url": "https://www.semanticscholar.org/paper/5b98992cd68d082b709d7861374fbf8a932d364b"}'
```

### 3. 処理状況の確認
```bash
# 論文の処理状況を確認
curl http://localhost:8000/api/papers/{paper_id}/status

# Flowerで処理状況を確認
open http://localhost:5555
```

### 4. 生成されたMarkdownの確認
```bash
# Obsidian Vaultディレクトリを確認
ls -la output/obsidian/
```

## チェックリスト

- [ ] 環境変数が正しく設定されている
- [ ] 全サービスが正常に起動している
- [ ] APIエンドポイントから論文クロールをトリガーできる
- [ ] Crawlerが論文情報を取得し、Summarizerに引き継ぐ
- [ ] SummarizerがPDFを処理し、Generatorに引き継ぐ
- [ ] GeneratorがMarkdownを生成し、ファイルが保存される
- [ ] 参照論文の自動クロールが深さ制限内で動作する
- [ ] Flowerでタスクの実行状況が確認できる
- [ ] エラー時にリトライが実行される

## レビュー観点

### 1. サービス間通信の正確性
- [ ] **APIエンドポイント**: 適切なHTTPステータスコードとレスポンス形式
- [ ] **タスク送信**: `send_task()`の引数（タスク名、引数、キュー）が正しい
- [ ] **引数の型**: タスク間で渡される引数の型が一貫している
- [ ] **非同期処理**: 適切な非同期処理フローが実装されている
- [ ] **タスクチェーン**: 各サービスが正しい順序でタスクを連携している

### 2. データ整合性・トランザクション
- [ ] **データベース操作**: 各タスクでのトランザクション境界が適切
- [ ] **重複処理防止**: 同じ論文の重複処理が防止されている
- [ ] **データ競合**: 複数ワーカーでの同時処理時の競合状態が考慮されている
- [ ] **ロールバック**: エラー時の適切なロールバック処理
- [ ] **外部キー制約**: 参照・被引用関係の整合性が保たれている

### 3. エラーハンドリング・耐障害性
- [ ] **リトライ機構**: 適切なリトライ間隔と最大回数の設定
- [ ] **例外処理**: 各種例外に対する適切な処理とログ出力
- [ ] **部分的な失敗**: 一部のタスクが失敗しても全体に影響しない
- [ ] **タイムアウト処理**: 長時間実行されるタスクのタイムアウト設定
- [ ] **サーキットブレーカー**: 外部APIの連続失敗時の保護機能

### 4. パフォーマンス最適化
- [ ] **並列処理**: 適切な並列度での処理実行
- [ ] **メモリ使用量**: 大量データ処理時のメモリ効率
- [ ] **データベースクエリ**: N+1問題の回避とクエリ最適化
- [ ] **ファイルI/O**: 効率的なファイル読み書き処理
- [ ] **キャッシュ**: 適切なキャッシュ戦略の実装

### 5. セキュリティ
- [ ] **入力検証**: APIエンドポイントでの入力値検証
- [ ] **SQLインジェクション**: パラメータ化クエリの使用
- [ ] **ファイルパス**: パストラバーサル攻撃の防止
- [ ] **認証・認可**: 適切な認証機構の実装
- [ ] **機密情報**: APIキーや認証情報の適切な管理

### 6. 設定管理・環境
- [ ] **環境変数**: 必要な環境変数がすべて定義されている
- [ ] **設定の検証**: 起動時の設定値検証
- [ ] **デフォルト値**: 適切なデフォルト値の設定
- [ ] **環境分離**: 開発・テスト・本番環境での設定分離
- [ ] **設定の暗号化**: 機密設定の暗号化

### 7. 監視・ログ・可観測性
- [ ] **構造化ログ**: 適切なログレベルと構造化されたログ出力
- [ ] **メトリクス**: 処理時間、成功率、エラー率の監視
- [ ] **分散トレーシング**: サービス間の処理追跡
- [ ] **ヘルスチェック**: 各サービスの健康状態監視
- [ ] **アラート**: 異常時の適切なアラート設定

### 8. データ品質・検証
- [ ] **データ検証**: 外部APIからのデータの妥当性検証
- [ ] **スキーマ検証**: JSONスキーマやデータ型の検証
- [ ] **NULL値処理**: NULL値やオプショナルフィールドの適切な処理
- [ ] **文字エンコーディング**: 適切な文字エンコーディング処理
- [ ] **データサニタイズ**: 出力データの適切なサニタイズ

### 9. ファイル管理・ストレージ
- [ ] **ファイルパス**: 適切なファイルパスの生成と管理
- [ ] **ディレクトリ作成**: 必要なディレクトリの自動作成
- [ ] **ファイル権限**: 適切なファイルアクセス権限
- [ ] **ストレージ容量**: ディスク容量の監視と管理
- [ ] **バックアップ**: 重要なファイルのバックアップ戦略

### 10. 拡張性・保守性
- [ ] **モジュール化**: 各機能が適切にモジュール化されている
- [ ] **設定の外部化**: ハードコードされた値の除去
- [ ] **依存関係の管理**: 適切な依存関係の定義
- [ ] **バージョン管理**: データベーススキーマの変更管理
- [ ] **新機能追加**: 新しい処理フローの追加が容易

### 11. テスト可能性
- [ ] **単体テスト**: 各タスクが独立してテスト可能
- [ ] **統合テスト**: サービス間の連携テスト
- [ ] **エンドツーエンドテスト**: 完全なフローのテスト
- [ ] **モック対応**: 外部依存のモック化
- [ ] **テストデータ**: 適切なテストデータの準備

### 12. 運用・デプロイ
- [ ] **ローリングアップデート**: サービス停止なしでの更新
- [ ] **設定の動的更新**: 運用中の設定変更
- [ ] **障害復旧**: 障害発生時の復旧手順
- [ ] **データマイグレーション**: スキーマ変更時の移行処理
- [ ] **監視ダッシュボード**: 運用状況の可視化

### 13. 外部API連携
- [ ] **レート制限**: API呼び出し頻度の制限
- [ ] **認証管理**: APIキーの適切な管理
- [ ] **エラーハンドリング**: API呼び出し時のエラー処理
- [ ] **レスポンス検証**: APIレスポンスの妥当性検証
- [ ] **フォールバック**: API利用不可時の代替処理

### 14. リソース管理
- [ ] **メモリリーク**: メモリリークの防止
- [ ] **ファイルハンドル**: 適切なファイルハンドルの管理
- [ ] **データベース接続**: 接続プールの適切な管理
- [ ] **一時ファイル**: 一時ファイルの適切なクリーンアップ
- [ ] **リソース制限**: 適切なリソース制限の設定
