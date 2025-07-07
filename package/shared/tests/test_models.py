"""データベースモデルのテスト."""

from datetime import datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from refnet_shared.models.database import Author, Base, Paper, PaperRelation
from refnet_shared.models.database_manager import DatabaseManager
from refnet_shared.models.schemas import PaperCreate, PaperUpdate


@pytest.fixture
def db_manager():
    """テスト用データベース接続."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    manager = DatabaseManager("sqlite:///:memory:")
    manager.engine = engine
    manager.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    return manager


def test_paper_creation(db_manager):
    """論文作成テスト."""
    with db_manager.get_session() as session:
        paper = Paper(
            paper_id="test-paper-1",
            title="Test Paper",
            abstract="Test abstract",
            year=2023,
            citation_count=10
        )
        session.add(paper)
        session.commit()

        # 取得テスト
        retrieved_paper = session.query(Paper).filter_by(paper_id="test-paper-1").first()
        assert retrieved_paper is not None
        assert retrieved_paper.title == "Test Paper"
        assert retrieved_paper.citation_count == 10


def test_author_paper_relationship(db_manager):
    """著者と論文の関係テスト."""
    with db_manager.get_session() as session:
        # 論文作成
        paper = Paper(
            paper_id="test-paper-1",
            title="Test Paper",
            year=2023
        )

        # 著者作成
        author = Author(
            author_id="test-author-1",
            name="Test Author"
        )

        session.add(paper)
        session.add(author)
        session.commit()

        # 関係設定（paper_authorsテーブルに直接挿入）
        session.execute(text(
            "INSERT INTO paper_authors (paper_id, author_id, position, created_at) "
            "VALUES (:paper_id, :author_id, :position, :created_at)"
        ), {
            "paper_id": "test-paper-1",
            "author_id": "test-author-1",
            "position": 1,
            "created_at": datetime.utcnow()
        })
        session.commit()

        # 関係確認
        retrieved_paper = session.query(Paper).filter_by(paper_id="test-paper-1").first()
        assert len(retrieved_paper.authors) == 1
        assert retrieved_paper.authors[0].name == "Test Author"


def test_paper_relation_creation(db_manager):
    """論文関係作成テスト."""
    with db_manager.get_session() as session:
        # 論文作成
        paper1 = Paper(paper_id="paper-1", title="Paper 1", year=2023)
        paper2 = Paper(paper_id="paper-2", title="Paper 2", year=2023)

        # 関係作成
        relation = PaperRelation(
            source_paper_id="paper-1",
            target_paper_id="paper-2",
            relation_type="citation",
            hop_count=1
        )

        session.add(paper1)
        session.add(paper2)
        session.add(relation)
        session.commit()

        # 関係確認
        retrieved_relation = session.query(PaperRelation).first()
        assert retrieved_relation.source_paper_id == "paper-1"
        assert retrieved_relation.target_paper_id == "paper-2"
        assert retrieved_relation.relation_type == "citation"


def test_database_manager_health_check(db_manager):
    """データベースマネージャーヘルスチェックテスト."""
    health = db_manager.health_check()
    assert health["status"] == "healthy"


def test_table_stats(db_manager):
    """テーブル統計テスト."""
    with db_manager.get_session() as session:
        # テストデータ追加
        paper = Paper(paper_id="test-paper", title="Test", year=2023)
        session.add(paper)
        session.commit()

    stats = db_manager.get_table_stats()
    assert "papers" in stats
    assert stats["papers"] >= 1


def test_paper_schema_validation():
    """論文スキーマ検証テスト."""
    # 正常なデータ
    valid_data = PaperCreate(
        paper_id="test-paper",
        title="Test Paper",
        abstract="Test abstract",
        year=2023,
        citation_count=10,
        language="en"
    )
    assert valid_data.paper_id == "test-paper"

    # 異常なデータ
    with pytest.raises(ValueError):
        PaperCreate(
            paper_id="test-paper",
            title="",  # 空タイトル
            abstract="Test abstract",
            year=2023,
            language="en"
        )


def test_paper_update_schema():
    """論文更新スキーマテスト."""
    # PaperUpdateは全フィールドがオプショナル
    update_data = PaperUpdate(  # type: ignore[call-arg]
        title="Updated Title",
        citation_count=20
    )
    assert update_data.title == "Updated Title"
    assert update_data.citation_count == 20
    assert update_data.abstract is None  # 設定されていない項目


def test_paper_schema_boundary_values():
    """論文スキーマ境界値テスト."""
    # 最小年度（1900年）
    paper_min_year = PaperCreate(
        paper_id="test-min-year",
        title="Min Year Paper",
        abstract="Test abstract",
        year=1900,
        language="en"
    )
    assert paper_min_year.year == 1900

    # 最大年度（2100年）
    paper_max_year = PaperCreate(
        paper_id="test-max-year",
        title="Max Year Paper",
        abstract="Test abstract",
        year=2100,
        language="en"
    )
    assert paper_max_year.year == 2100

    # 引用数0（最小値）
    paper_zero_citations = PaperCreate(
        paper_id="test-zero-citations",
        title="Zero Citations Paper",
        abstract="Test abstract",
        year=2023,
        citation_count=0,
        language="en"
    )
    assert paper_zero_citations.citation_count == 0


def test_paper_schema_invalid_data():
    """論文スキーマ無効データテスト."""
    # 負の引用数
    with pytest.raises(ValueError):
        PaperCreate(
            paper_id="test-invalid",
            title="Invalid Paper",
            abstract="Test abstract",
            year=2023,
            citation_count=-1,
            language="en"
        )

    # 範囲外の年度（1899年）
    with pytest.raises(ValueError):
        PaperCreate(
            paper_id="test-invalid-year-low",
            title="Invalid Year Paper",
            abstract="Test abstract",
            year=1899,
            language="en"
        )

    # 範囲外の年度（2101年）
    with pytest.raises(ValueError):
        PaperCreate(
            paper_id="test-invalid-year-high",
            title="Invalid Year Paper",
            abstract="Test abstract",
            year=2101,
            language="en"
        )


def test_paper_database_constraints(db_manager):
    """論文データベース制約テスト."""
    from refnet_shared.exceptions import DatabaseError

    # 最初のセッションで論文1を追加
    with db_manager.get_session() as session:
        paper1 = Paper(paper_id="duplicate-id", title="Paper 1", year=2023)
        session.add(paper1)
        session.commit()

    # 2番目のセッションで重複IDを追加しようとしてエラー
    with pytest.raises(DatabaseError):
        with db_manager.get_session() as session:
            paper2 = Paper(paper_id="duplicate-id", title="Paper 2", year=2023)
            session.add(paper2)
            session.commit()


def test_paper_relation_constraints(db_manager):
    """論文関係制約テスト."""
    from refnet_shared.exceptions import DatabaseError

    # 論文作成
    with db_manager.get_session() as session:
        paper1 = Paper(paper_id="paper-constraint-1", title="Paper 1", year=2023)
        paper2 = Paper(paper_id="paper-constraint-2", title="Paper 2", year=2023)
        session.add(paper1)
        session.add(paper2)
        session.commit()

    # 自分自身を参照する関係（制約違反）をテスト
    with pytest.raises(DatabaseError):
        with db_manager.get_session() as session:
            self_relation = PaperRelation(
                source_paper_id="paper-constraint-1",
                target_paper_id="paper-constraint-1",  # 同じID
                relation_type="citation",
                hop_count=1
            )
            session.add(self_relation)
            session.commit()


def test_paper_external_id_constraints(db_manager):
    """論文外部ID制約テスト."""
    from refnet_shared.exceptions import DatabaseError
    from refnet_shared.models.database import PaperExternalId

    # 論文作成
    with db_manager.get_session() as session:
        paper = Paper(paper_id="external-id-test", title="External ID Test", year=2023)
        session.add(paper)
        session.commit()

    # 無効なid_typeでエラーをテスト
    with pytest.raises(DatabaseError):
        with db_manager.get_session() as session:
            invalid_external_id = PaperExternalId(
                paper_id="external-id-test",
                id_type="INVALID_TYPE",  # 制約で許可されていない値
                external_id="12345"
            )
            session.add(invalid_external_id)
            session.commit()


def test_author_constraints(db_manager):
    """著者制約テスト."""
    from refnet_shared.exceptions import DatabaseError

    # 負のpaper_countでエラーをテスト
    with pytest.raises(DatabaseError):
        with db_manager.get_session() as session:
            invalid_author = Author(
                author_id="invalid-author",
                name="Invalid Author",
                paper_count=-1  # 制約違反
            )
            session.add(invalid_author)
            session.commit()


def test_processing_queue_constraints(db_manager):
    """処理キュー制約テスト."""
    from refnet_shared.exceptions import DatabaseError
    from refnet_shared.models.database import ProcessingQueue

    # 論文作成
    with db_manager.get_session() as session:
        paper = Paper(paper_id="queue-test", title="Queue Test", year=2023)
        session.add(paper)
        session.commit()

    # 無効なtask_typeでエラーをテスト
    with pytest.raises(DatabaseError):
        with db_manager.get_session() as session:
            invalid_queue_item = ProcessingQueue(
                paper_id="queue-test",
                task_type="invalid_task",  # 制約で許可されていない値
                status="pending"
            )
            session.add(invalid_queue_item)
            session.commit()


def test_large_text_fields(db_manager):
    """大きなテキストフィールドテスト."""
    with db_manager.get_session() as session:
        # 非常に長いタイトルとアブストラクト
        large_title = "A" * 10000  # 10KB
        large_abstract = "B" * 100000  # 100KB

        paper = Paper(
            paper_id="large-text-test",
            title=large_title,
            abstract=large_abstract,
            year=2023
        )
        session.add(paper)
        session.commit()

        # 正常に保存・取得できることを確認
        retrieved = session.query(Paper).filter_by(paper_id="large-text-test").first()
        assert len(retrieved.title) == 10000
        assert len(retrieved.abstract) == 100000


def test_json_field_types(db_manager):
    """JSON フィールド型テスト."""
    with db_manager.get_session() as session:
        # 論文作成
        paper = Paper(paper_id="json-test", title="JSON Test", year=2023)
        session.add(paper)
        session.commit()

        # ProcessingQueueのparametersフィールド（JSON型）
        from refnet_shared.models.database import ProcessingQueue

        # 複雑なJSONデータ
        complex_params = {
            "config": {
                "retries": 3,
                "timeout": 30,
                "options": ["verbose", "debug"]
            },
            "metadata": {
                "created_by": "test",
                "priority": "high"
            }
        }

        queue_item = ProcessingQueue(
            paper_id="json-test",
            task_type="crawl",
            status="pending",
            parameters=complex_params
        )
        session.add(queue_item)
        session.commit()

        # JSONデータが正しく保存・取得できることを確認
        retrieved = session.query(ProcessingQueue).filter_by(paper_id="json-test").first()
        assert retrieved.parameters["config"]["retries"] == 3
        assert "verbose" in retrieved.parameters["config"]["options"]


def test_database_manager_init_table_creation(db_manager):
    """データベースマネージャー初期化とテーブル作成テスト."""
    # テーブルが作成されていることを確認
    stats = db_manager.get_table_stats()
    # database.pyで定義されているテーブルのみを確認
    expected_tables = ["papers", "authors", "venues", "journals", "paper_relations",
                      "processing_queue", "paper_authors", "paper_external_ids"]
    for table in expected_tables:
        assert table in stats, f"Table {table} not found in {list(stats.keys())}"


def test_database_manager_vacuum_analyze():
    """VACUUM ANALYZEテスト（SQLiteはVACUUMをサポートしない）."""
    # SQLiteはVACUUM ANALYZEをサポートしないため例外が発生する
    manager = DatabaseManager("sqlite:///:memory:")

    # SQLiteではVACUUMコマンドでエラーになる
    try:
        manager.vacuum_analyze()
    except Exception:
        # SQLiteでは例外が発生することを期待
        pass


def test_database_manager_health_check_pool_info(db_manager):
    """ヘルスチェックプール情報テスト."""
    health = db_manager.health_check()
    # プール情報が含まれていることを確認
    assert "status" in health
    assert health["status"] == "healthy"
    # 正常なヘルスチェックではengine_pool_sizeが含まれている
    assert "engine_pool_size" in health


def test_database_manager_engine_url():
    """データベースマネージャーエンジンURL取得テスト."""
    manager = DatabaseManager("sqlite:///:memory:")
    assert hasattr(manager, "engine")
    assert manager.engine is not None


def test_database_manager_engine_dispose():
    """データベースマネージャーエンジン破棄テスト."""
    manager = DatabaseManager("sqlite:///:memory:")
    # エンジンが正常に破棄できることを確認
    manager.engine.dispose()

    # 破棄後も再接続できることを確認
    with manager.get_session() as session:
        result = session.execute(text("SELECT 1")).scalar()
        assert result == 1


def test_database_manager_session_rollback(db_manager):
    """セッションロールバックテスト."""
    with db_manager.get_session() as session:
        # トランザクション内でデータを追加
        paper = Paper(paper_id="rollback-test", title="Rollback Test", year=2023)
        session.add(paper)

        # ロールバック
        session.rollback()

    # ロールバック後にデータが存在しないことを確認
    with db_manager.get_session() as session:
        count = session.query(Paper).filter_by(paper_id="rollback-test").count()
        assert count == 0


def test_get_json_type_postgresql(monkeypatch):
    """PostgreSQL用JSON型テスト."""
    from sqlalchemy.dialects.postgresql import JSONB

    from refnet_shared.models.database import get_json_type

    # PostgreSQL URLを設定
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")

    json_type = get_json_type()
    assert json_type == JSONB


def test_get_json_type_sqlite(monkeypatch):
    """SQLite用JSON型テスト."""
    from sqlalchemy import JSON

    from refnet_shared.models.database import get_json_type

    # SQLite URLを設定
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")

    json_type = get_json_type()
    assert json_type == JSON


def test_get_json_type_default(monkeypatch):
    """デフォルトJSON型テスト."""
    from sqlalchemy import JSON

    from refnet_shared.models.database import get_json_type

    # DATABASE_URLを未設定にする
    monkeypatch.delenv("DATABASE_URL", raising=False)

    json_type = get_json_type()
    assert json_type == JSON


def test_database_manager_session_exception_handling():
    """セッション例外ハンドリングテスト."""
    from refnet_shared.exceptions import DatabaseError

    manager = DatabaseManager("sqlite:///:memory:")

    # セッション内で例外を発生させてロールバックをテスト
    with pytest.raises(DatabaseError):
        with manager.get_session() as _session:
            # 意図的に例外を発生
            raise RuntimeError("Test exception")


def test_database_manager_create_drop_tables():
    """テーブル作成・削除テスト."""
    manager = DatabaseManager("sqlite:///:memory:")

    # テーブル作成
    manager.create_tables()

    # テーブル削除
    manager.drop_tables()


def test_database_manager_create_tables_error(monkeypatch):
    """テーブル作成エラーテスト."""
    from refnet_shared.exceptions import DatabaseError
    from refnet_shared.models.database import Base

    manager = DatabaseManager("sqlite:///:memory:")

    # metadata.create_allを失敗させる
    def mock_create_all(*args, **kwargs):
        raise Exception("Database connection failed")

    monkeypatch.setattr(Base.metadata, "create_all", mock_create_all)

    with pytest.raises(DatabaseError, match="Failed to create tables"):
        manager.create_tables()


def test_database_manager_drop_tables_error(monkeypatch):
    """テーブル削除エラーテスト."""
    from refnet_shared.exceptions import DatabaseError
    from refnet_shared.models.database import Base

    manager = DatabaseManager("sqlite:///:memory:")

    # metadata.drop_allを失敗させる
    def mock_drop_all(*args, **kwargs):
        raise Exception("Database connection failed")

    monkeypatch.setattr(Base.metadata, "drop_all", mock_drop_all)

    with pytest.raises(DatabaseError, match="Failed to drop tables"):
        manager.drop_tables()


def test_database_manager_get_table_stats_error(monkeypatch):
    """テーブル統計取得エラーテスト."""
    from refnet_shared.exceptions import DatabaseError

    manager = DatabaseManager("sqlite:///:memory:")

    # セッション取得を失敗させる
    def mock_get_session(*args, **kwargs):
        raise Exception("Session creation failed")

    monkeypatch.setattr(manager, "get_session", mock_get_session)

    with pytest.raises(DatabaseError, match="Failed to get table stats"):
        manager.get_table_stats()


def test_database_manager_health_check_unhealthy():
    """データベースヘルスチェック異常テスト."""
    # 無効なデータベースURLを使用
    manager = DatabaseManager("sqlite:///invalid/path/to/database.db")

    health = manager.health_check()
    assert health["status"] == "unhealthy"
    assert "error" in health


def test_database_manager_vacuum_analyze_error():
    """VACUUM ANALYZEエラーテスト."""
    from refnet_shared.exceptions import DatabaseError

    # SQLiteはVACUUM ANALYZEをサポートしないためエラーになる
    manager = DatabaseManager("sqlite:///:memory:")

    with pytest.raises(DatabaseError, match="VACUUM ANALYZE failed"):
        manager.vacuum_analyze()


def test_database_manager_session_database_error(monkeypatch):
    """セッション内データベースエラーテスト."""
    from refnet_shared.exceptions import DatabaseError

    manager = DatabaseManager("sqlite:///:memory:")

    # セッション内で例外を発生させてDBエラーハンドリングをテスト
    with pytest.raises(DatabaseError, match="Database operation failed"):
        with manager.get_session() as session:
            # 無効なSQLを実行
            session.execute(text("INVALID SQL STATEMENT"))


def test_database_manager_connection_pool_error(monkeypatch):
    """接続プールエラーテスト."""
    # エンジン作成を失敗させる
    def mock_create_engine(*args, **kwargs):
        raise Exception("Engine creation failed")

    monkeypatch.setattr("refnet_shared.models.database_manager.create_engine", mock_create_engine)

    with pytest.raises(Exception, match="Engine creation failed"):
        DatabaseManager("sqlite:///:memory:")


def test_database_manager_close_error(monkeypatch):
    """データベース接続クローズエラーテスト."""
    manager = DatabaseManager("sqlite:///:memory:")

    # engine.disposeを失敗させる
    def mock_dispose():
        raise Exception("Failed to dispose engine")

    monkeypatch.setattr(manager.engine, "dispose", mock_dispose)

    # エラーが発生してもログに記録される（例外は発生しない）
    manager.close()
