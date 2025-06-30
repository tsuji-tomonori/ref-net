# プロジェクト概要

ObsidianによるRAG論文関係性の可視化システムである。

1. "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"を起点とする
2. 参照文献・被引用文献を網羅的に収集する
3. 収集した論文の関連文献を再帰的に収集する
4. Obsidianで論文ネットワークを可視化する

# 実装方針

- Python + AWS サーバーレス構成
- 従量課金モデルでコスト最適化
- 初期費用・固定費用を最小化
- 簡潔・簡素・単一の原則を順守

# 実装手順

1. ブランチ作成: `echo "claude/$(date +'%Y%m%d%H%M%S')"`
2. ドキュメント更新: @docs配下の確認・更新・新規作成後commit (@.gitmessage 準拠)
3. テスト作成: 単体テストのみ、外部リソースはモック化
4. テスト失敗確認: 作成テストの失敗確認後commit (@.gitmessage 準拠)
5. 実装: ドキュメント準拠、改修範囲外は変更禁止
   - コーディング規約: @docs/development/coding-standards.md
   - CDK規約: @docs/development/coding-cdk.md
6. テスト: `moon :check` 成功まで修正
    - コーディング規約: @docs/development/coding-test.md
7. PR作成: @.github/pull_request_template.md 準拠
