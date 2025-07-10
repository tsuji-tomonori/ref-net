# 監視手順書

## 概要

RefNetシステムの監視手順と対応方法を定義します。

## 監視対象

### 1. システムヘルス

- **サービス稼働状況**: 全サービスの起動状態
- **リソース使用率**: CPU、メモリ、ディスク使用率
- **ネットワーク**: 応答時間、エラー率

### 2. アプリケーション監視

- **API応答時間**: 95パーセンタイル値
- **エラー率**: 4xx、5xxエラーの発生率
- **タスク処理**: Celeryタスクの実行状況

### 3. データベース監視

- **接続数**: アクティブ接続数
- **クエリ性能**: 長時間実行クエリ
- **テーブルサイズ**: 主要テーブルのサイズ

## 監視ツール

### 1. Grafana ダッシュボード

アクセス: http://localhost:3000

#### デフォルトログイン
- ユーザー: admin
- パスワード: admin

#### 主要ダッシュボード

1. **システム全体ダッシュボード**
   - URL: http://localhost:3000/d/system-overview
   - 監視項目: サービス稼働状況、リソース使用率

2. **Celery監視ダッシュボード**
   - URL: http://localhost:3000/d/celery-monitoring
   - 監視項目: タスク実行数、エラー率、実行時間

#### アラート設定

重要なメトリクスにアラートを設定：

```yaml
# grafana/alerting/rules.yml
groups:
  - name: refnet-alerts
    rules:
      - alert: APIHighErrorRate
        expr: rate(refnet_http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "API error rate is high"

      - alert: CeleryTaskFailed
        expr: increase(celery_task_total{status="failed"}[5m]) > 5
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Multiple Celery tasks failed"
```

### 2. Flower (Celery監視)

アクセス: http://localhost:5555

#### 監視項目

- **ワーカー状態**: アクティブ/非アクティブ
- **タスクキュー**: 待機中・実行中タスク数
- **タスク履歴**: 成功/失敗タスクの履歴

#### 主要画面

1. **Workers**: ワーカー一覧と状態
2. **Tasks**: タスク実行履歴
3. **Broker**: Redis接続状態

### 3. Prometheus

アクセス: http://localhost:9090

#### 基本クエリ

```promql
# API応答時間
histogram_quantile(0.95, rate(refnet_http_request_duration_seconds_bucket[5m]))

# エラー率
rate(refnet_http_requests_total{status=~"5.."}[5m]) / rate(refnet_http_requests_total[5m])

# データベース接続数
refnet_db_connections_active

# Celeryタスク成功率
rate(celery_task_total{status="success"}[5m]) / rate(celery_task_total[5m])
```

## 監視手順

### 1. 日次チェック

#### 朝の確認（9:00）

```bash
#!/bin/bash
# scripts/daily-morning-check.sh

echo "=== RefNet日次監視レポート ==="
echo "日時: $(date)"
echo

# サービス稼働状況
echo "1. サービス稼働状況:"
docker-compose ps | grep -E "(Up|Exit)"

# API ヘルスチェック
echo "2. API ヘルスチェック:"
curl -s http://localhost/health | jq .

# データベース接続確認
echo "3. データベース接続:"
docker-compose exec postgres pg_isready -U refnet

# Redis接続確認
echo "4. Redis接続:"
docker-compose exec redis redis-cli ping

# ディスク使用量
echo "5. ディスク使用量:"
df -h | grep -E "/$|/var/lib/docker"

# メモリ使用量
echo "6. メモリ使用量:"
free -h
```

#### 夕方の確認（17:00）

```bash
#!/bin/bash
# scripts/daily-evening-check.sh

echo "=== RefNet夕方監視レポート ==="
echo "日時: $(date)"
echo

# 1日のタスク実行状況
echo "1. 本日のタスク実行状況:"
docker-compose exec redis redis-cli llen celery | echo "キュー待機: $(cat) タスク"

# エラーログ確認
echo "2. エラーログ確認:"
docker-compose logs --since 24h | grep -i error | wc -l | echo "エラー数: $(cat)"

# 論文データ更新確認
echo "3. 論文データ更新:"
docker-compose exec postgres psql -U refnet -c "SELECT COUNT(*) FROM papers WHERE updated_at >= CURRENT_DATE;" | tail -1
```

### 2. 週次チェック

#### 日曜日の詳細チェック

```bash
#!/bin/bash
# scripts/weekly-check.sh

echo "=== RefNet週次監視レポート ==="
echo "週: $(date +'%Y年%W週')"
echo

# パフォーマンスメトリクス
echo "1. 週次パフォーマンス:"
echo "- 平均応答時間: $(curl -s 'http://localhost:9090/api/v1/query?query=avg_over_time(histogram_quantile(0.95,rate(refnet_http_request_duration_seconds_bucket[5m]))[7d])' | jq -r '.data.result[0].value[1]') ms"
echo "- 週次エラー率: $(curl -s 'http://localhost:9090/api/v1/query?query=avg_over_time(rate(refnet_http_requests_total{status=~\"5..\"}[5m])[7d])' | jq -r '.data.result[0].value[1]') %"

# データベース統計
echo "2. データベース統計:"
docker-compose exec postgres psql -U refnet -c "SELECT schemaname, tablename, n_tup_ins, n_tup_upd, n_tup_del FROM pg_stat_user_tables WHERE schemaname = 'public';"

# ディスク使用量トレンド
echo "3. ディスク使用量:"
du -sh /var/lib/docker/volumes/refnet_*
```

### 3. 緊急時対応

#### 高負荷時の対応

```bash
#!/bin/bash
# scripts/emergency-high-load.sh

echo "=== 高負荷緊急対応 ==="

# 1. 現在の負荷状況確認
echo "1. 負荷状況:"
docker stats --no-stream

# 2. 長時間実行クエリの確認
echo "2. 長時間実行クエリ:"
docker-compose exec postgres psql -U refnet -c "SELECT pid, now() - pg_stat_activity.query_start AS duration, query FROM pg_stat_activity WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes';"

# 3. Celeryキューの確認
echo "3. Celeryキュー状況:"
docker-compose exec redis redis-cli llen celery

# 4. 緊急対応オプション
echo "4. 緊急対応オプション:"
echo "A. 長時間クエリの強制終了"
echo "B. Celeryワーカーの追加"
echo "C. タスクキューのクリア"
echo "D. サービス再起動"
```

## アラート対応

### 1. API エラー率上昇

#### 閾値
- 警告: 5% (5分間平均)
- 重要: 10% (5分間平均)

#### 対応手順
1. エラーログの確認
2. 外部API状態の確認
3. データベース接続状態の確認
4. 必要に応じてサービス再起動

### 2. データベース接続数上昇

#### 閾値
- 警告: 80接続
- 重要: 95接続

#### 対応手順
1. 長時間実行クエリの確認
2. 接続プールの確認
3. アプリケーションの接続リーク確認
4. 必要に応じてサービス再起動

### 3. Celeryタスク失敗

#### 閾値
- 警告: 10タスク/5分
- 重要: 20タスク/5分

#### 対応手順
1. 失敗タスクの内容確認
2. 外部API状態の確認
3. ワーカーログの確認
4. 必要に応じてタスクの再実行

## 監視データの保存

### 1. メトリクス保存期間

- **Prometheus**: 15日間
- **Grafana**: 永続化（PostgreSQL）
- **アプリケーションログ**: 30日間

### 2. バックアップ対象

```bash
# 監視データのバックアップ
tar -czf monitoring-backup-$(date +%Y%m%d).tar.gz \
  monitoring/grafana/data \
  monitoring/prometheus/data \
  logs/
```

## 監視改善

### 1. 新しいメトリクスの追加

1. アプリケーションコードでメトリクス追加
2. Prometheus設定更新
3. Grafanaダッシュボード更新
4. アラートルール追加

### 2. ダッシュボードの改善

1. 業務要件に応じたパネル追加
2. 閾値の調整
3. アラート条件の最適化

### 3. 自動化の推進

1. 定期チェックスクリプトの作成
2. 異常検知の自動化
3. 復旧作業の自動化
