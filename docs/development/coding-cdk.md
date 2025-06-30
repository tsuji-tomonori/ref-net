# AWS CDK開発規約

## 基本方針

- 論理分割: API、ストレージ、コンピュートなど論理的ユニットごとにStackまたはConstructを分離
- 再利用性重視: 単一責任の原則でConstruct設計、パラメータ化可能なPropsインターフェース
- 一貫性維持: CDKバージョンと言語（Python 3.12）統一、依存管理の標準化

## プロジェクト構造

```
package/infra/
├─ src/
│   └─ refnet_infra/
│      ├─ constructs/   # 再利用可能Construct
│      ├─ stacks/       # 論理スタック定義
│      └─ app.py        # CDK Appエントリ
├─ tests/               # ユニットテスト
└─  cdk.json             # CDK設定
```

### スタック分割

- 機能領域ごとにスタック分離（認証、データ、API、モニタリング）
- デプロイ・削除時の依存関係を明確化
- Construct間依存はPropsまたはStackPropsで明示的定義、循環依存回避

## Constructモジュール化

### 設計原則

- Constructは単一リソースから複数リソース組み合わせまで表現可能な基本単位
- L2/L3カスタムConstructで高レベル抽象を提供

### 命名規則

- Constructクラス: 用途を示す末尾に`Construct`付与（例: `UserPoolConstruct`）
- その他の命名規則は[coding-standards](coding-standards.md) を参照

## コーディング規約

基本的なコーディング規約は[coding-standards](coding-standards.md) を参照。CDK固有の規約は以下とする：

### CDK固有規約

- すべての公開API（ConstructのPropsインターフェース、パブリックメソッド）にDocstring必須
- 目的・引数・戻り値を明記
- Constructクラスには使用例をDocstringに含める

## テスト

### スナップショットテスト

- CloudFormationテンプレート全体を`__snapshots__/`下に保存・比較
- `syrupy`または`pytest-snapshot`プラグイン使用
- `snapshot.assert_match(template.to_json())`でテンプレートJSON比較
- 意図的変更時のみ`pytest --snapshot-update`実行
- 環境依存差分（アセットハッシュ、順序）の正規化実装

### リソースアサーションテスト

- `aws_cdk.assertions.Template`で特定リソース検証
- `has_resource_properties(resource_type, expected_props)`
- `has_resource(resource_type)`
- 動的値は`Capture()`でパターンマッチング検証
- `find_resources`、`resource_count_is`で複数リソース検証

## セキュリティとガバナンス

- 環境分離: 開発・ステージング・本番を別アカウントまたは別環境変数で分離
- 機密情報: Secrets Manager、SSMパラメータストア利用、コードベース除外
- IAMポリシー: 必要最小限権限、ポリシーテンプレート中央管理
- セキュリティ検証: AspectsまたはCloudFormation Guardで宣言的検証
