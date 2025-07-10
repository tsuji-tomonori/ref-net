# インシデント対応フロー

## 概要

RefNetシステムで発生するインシデントの対応フローを定義します。

## インシデント分類

### 重要度レベル

| レベル | 定義 | 対応時間 | 例 |
|--------|------|----------|-----|
| P1 (重要) | サービス完全停止 | 即座 | 全サービス停止、データ損失 |
| P2 (高) | 主要機能の停止 | 2時間以内 | API応答不能、データベース接続不可 |
| P3 (中) | 一部機能の停止 | 8時間以内 | 特定機能のエラー、性能劣化 |
| P4 (低) | 軽微な問題 | 24時間以内 | 監視アラート、ログエラー |

### 影響範囲

- **全サービス**: システム全体の停止
- **コア機能**: API、データベース、主要ワーカー
- **補助機能**: 監視、一部バックグラウンドタスク

## 対応フロー

### 1. インシデント検知

#### 自動検知
- **監視アラート**: Grafana/Prometheusアラート
- **ヘルスチェック**: APIヘルスチェック失敗
- **外部監視**: 外部監視サービス（設定時）

#### 手動検知
- **ユーザー報告**: 利用者からの報告
- **定期チェック**: 定期監視での発見
- **運用作業中**: メンテナンス作業中の発見

### 2. 初期対応（15分以内）

```bash
#!/bin/bash
# scripts/incident-initial-response.sh

echo "=== インシデント初期対応 ==="
echo "開始時刻: $(date)"
echo "対応者: $(whoami)"
echo

# 1. システム状態確認
echo "1. システム状態確認:"
docker-compose ps

# 2. リソース使用状況
echo "2. リソース使用状況:"
docker stats --no-stream

# 3. 最新エラーログ
echo "3. 最新エラーログ:"
docker-compose logs --since 10m | grep -i error | tail -10

# 4. 外部API接続確認
echo "4. 外部API接続確認:"
curl -s -o /dev/null -w "%{http_code}" https://api.semanticscholar.org/v1/paper/search

# 5. 基本的な対応
echo "5. 基本的な対応:"
echo "A. サービス再起動"
echo "B. ログ詳細確認"
echo "C. エスカレーション"
```

### 3. 問題分析（30分以内）

#### システムレベル診断

```bash
#!/bin/bash
# scripts/incident-system-diagnosis.sh

echo "=== システムレベル診断 ==="

# 1. システムリソース
echo "1. システムリソース:"
echo "CPU使用率:"
top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1

echo "メモリ使用率:"
free | grep Mem | awk '{printf "%.2f%%\n", $3/$2 * 100.0}'

echo "ディスク使用率:"
df -h | grep -E "/$|/var" | awk '{print $5}'

# 2. ネットワーク状態
echo "2. ネットワーク状態:"
netstat -tulpn | grep -E ":80|:5432|:6379|:8000"

# 3. プロセス状態
echo "3. プロセス状態:"
ps aux | grep -E "docker|postgres|redis" | grep -v grep
```

#### アプリケーションレベル診断

```bash
#!/bin/bash
# scripts/incident-app-diagnosis.sh

echo "=== アプリケーションレベル診断 ==="

# 1. データベース状態
echo "1. データベース状態:"
docker-compose exec postgres psql -U refnet -c "
SELECT
  datname,
  numbackends,
  xact_commit,
  xact_rollback,
  tup_returned,
  tup_fetched,
  tup_inserted,
  tup_updated,
  tup_deleted
FROM pg_stat_database
WHERE datname = 'refnet';
"

# 2. 長時間実行クエリ
echo "2. 長時間実行クエリ:"
docker-compose exec postgres psql -U refnet -c "
SELECT
  pid,
  now() - pg_stat_activity.query_start AS duration,
  query,
  state
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '30 seconds'
AND query NOT LIKE '%pg_stat_activity%';
"

# 3. Redis状態
echo "3. Redis状態:"
docker-compose exec redis redis-cli info | grep -E "connected_clients|used_memory|keyspace"

# 4. Celery状態
echo "4. Celery状態:"
docker-compose exec redis redis-cli llen celery | echo "キュー長: $(cat)"
```

### 4. 対応実施

#### P1: 緊急対応

```bash
#!/bin/bash
# scripts/incident-p1-response.sh

echo "=== P1 緊急対応 ==="

# 1. 即座の復旧試行
echo "1. 即座の復旧試行:"
docker-compose restart

# 2. 代替手段の検討
echo "2. 代替手段:"
echo "- メンテナンスページ表示"
echo "- 最新バックアップからの復旧"
echo "- 外部通知（必要に応じて）"

# 3. エスカレーション
echo "3. エスカレーション:"
echo "- 上位者への連絡"
echo "- 技術支援の要請"
```

#### P2: 高優先度対応

```bash
#!/bin/bash
# scripts/incident-p2-response.sh

echo "=== P2 高優先度対応 ==="

# 1. 影響範囲の特定
echo "1. 影響範囲の特定:"
echo "- 停止している機能"
echo "- 影響を受けるユーザー"
echo "- 復旧予定時間"

# 2. 段階的復旧
echo "2. 段階的復旧:"
echo "- コア機能の復旧"
echo "- 補助機能の復旧"
echo "- 機能確認"

# 3. 監視強化
echo "3. 監視強化:"
echo "- 追加監視の設定"
echo "- 頻繁な状態確認"
```

### 5. 復旧確認

#### 機能確認チェックリスト

```bash
#!/bin/bash
# scripts/incident-recovery-check.sh

echo "=== 復旧確認チェックリスト ==="

# 1. サービス稼働確認
echo "1. サービス稼働確認:"
services=("nginx" "api" "postgres" "redis" "crawler" "summarizer" "generator")
for service in "${services[@]}"; do
  status=$(docker-compose ps $service | grep -c "Up")
  if [ $status -eq 1 ]; then
    echo "✓ $service: 稼働中"
  else
    echo "✗ $service: 停止中"
  fi
done

# 2. API機能確認
echo "2. API機能確認:"
api_check=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/health)
if [ $api_check -eq 200 ]; then
  echo "✓ API: 正常"
else
  echo "✗ API: 異常 (HTTP: $api_check)"
fi

# 3. データベース確認
echo "3. データベース確認:"
db_check=$(docker-compose exec postgres pg_isready -U refnet | grep -c "accepting connections")
if [ $db_check -eq 1 ]; then
  echo "✓ データベース: 正常"
else
  echo "✗ データベース: 異常"
fi

# 4. Celeryタスク確認
echo "4. Celeryタスク確認:"
# 簡単なテストタスクを実行
# curl -X POST http://localhost/tasks/test

# 5. 外部API接続確認
echo "5. 外部API接続確認:"
semantic_scholar_check=$(curl -s -o /dev/null -w "%{http_code}" https://api.semanticscholar.org/v1/paper/search?query=test)
if [ $semantic_scholar_check -eq 200 ]; then
  echo "✓ Semantic Scholar API: 正常"
else
  echo "✗ Semantic Scholar API: 異常"
fi
```

### 6. 事後対応

#### インシデント報告書

```markdown
# インシデント報告書

## 基本情報
- **発生日時**: YYYY-MM-DD HH:MM:SS
- **検知日時**: YYYY-MM-DD HH:MM:SS
- **復旧日時**: YYYY-MM-DD HH:MM:SS
- **対応者**:
- **重要度**: P1/P2/P3/P4

## 影響範囲
- **影響したサービス**:
- **影響したユーザー**:
- **データ損失**: 有/無

## 原因分析
- **直接原因**:
- **根本原因**:
- **発生経緯**:

## 対応内容
- **初期対応**:
- **本格対応**:
- **復旧手順**:

## 再発防止策
- **即座の対策**:
- **長期的な対策**:
- **監視強化**:

## 学習事項
- **対応で良かった点**:
- **改善すべき点**:
- **手順の更新**:
```

#### 振り返り会議

```markdown
# インシデント振り返り会議

## 参加者
- 対応者
- 運用責任者
- 技術責任者

## 議題
1. インシデント対応の振り返り
2. 改善点の特定
3. 再発防止策の検討
4. 手順書の更新

## 決定事項
- 改善施策とスケジュール
- 責任者の割り当て
- 次回フォローアップ日程
```

## 連絡体制

### 1. エスカレーション連絡先

| 役割 | 連絡先 | 対応時間 |
|------|--------|----------|
| 運用担当 | [連絡先] | 24時間 |
| 技術責任者 | [連絡先] | 平日9-18時 |
| 管理責任者 | [連絡先] | 緊急時のみ |

### 2. 外部連絡

- **クラウドプロバイダー**: [サポート連絡先]
- **外部API提供者**: [サポート連絡先]
- **監視サービス**: [サポート連絡先]

## 継続的改善

### 1. 手順書の更新

- インシデント対応後の手順書更新
- 新しい対応パターンの追加
- 自動化できる部分の特定

### 2. 監視の改善

- 新しいアラートルールの追加
- 監視間隔の調整
- 監視対象の追加

### 3. 訓練の実施

- 月次障害対応訓練
- 新しい対応手順の習得
- 対応時間の短縮化
