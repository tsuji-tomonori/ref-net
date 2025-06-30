# pytest実装規約

## テスト構成

- `tests/`ディレクトリに配置。アプリケーション構造を反映したサブディレクトリ構成とする
- ファイル名: `test_<module>.py`
- クラス名: `Test<対象クラス名>`
- 関数名: `test_<機能説明>`

## AAAパターン

Arrange（準備）→Act（実行）→Assert（検証）の3フェーズを明確に分離。1テスト1検証とする。

## フィクスチャ

- 共通処理は`conftest.py`にフィクスチャとして定義
- スコープ: `function`（デフォルト）、`module`、`session`から最小限を選択
- 命名: 用途が明確な名前（例: `db_client`、`sample_user`）

## パラメトリゼーション

```python
@pytest.mark.parametrize("a, b, expected", [
    (1, 2, 3),
    (0, 0, 0),
    (-1, 1, 0),
])
def test_add(a, b, expected):
    assert add(a, b) == expected
```

## モック化

- 外部リソース（DynamoDB/S3/HTTP等）は必ずモック化
- `monkeypatch`または`pytest-mock`使用
- 正常系・異常系・例外を網羅

## カバレッジ

- 80％以上を維持
- CI: `pytest --cov=src --cov-fail-under=80`

## 実行オプション

- 開発時: `pytest -q`（簡易表示）、`pytest -q -x`（失敗時即終了）
- 統合テスト: `@pytest.mark.integration`マーカーを定義、`pytest -m integration`で実行

## テスト固有のコーディング規約

## 型ヒント

テスト関数にも型注釈を付与。フィクスチャの戻り値型も明示する。

## Docstring

複雑なテストケースには、テスト対象と検証内容を説明するDocstringを記述。

## テスト間の独立性

- グローバル状態を変更しない
- 各テストは他のテストに依存せず単独で実行可能とする
- テスト実行順序に依存しない設計

## アサーション

- 具体的なアサーションメッセージを付与: `assert result == expected, f"Expected {expected}, got {result}"`
- 複数アサーションは避け、1テスト1アサーションを原則とする

## テストデータ

- マジックナンバーを避け、意味のある定数として定義
- 境界値、異常値、空値を必ず含める
- フィクスチャまたはファクトリ関数でテストデータを生成
