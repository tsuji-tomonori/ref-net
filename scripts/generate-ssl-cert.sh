#!/bin/bash

# 自己署名SSL証明書生成スクリプト（開発用）
# セキュリティ強化版

set -e

SSL_DIR="docker/nginx/ssl"
CERT_FILE="server.crt"
KEY_FILE="server.key"
CSR_FILE="server.csr"
DAYS=365

# 証明書情報
COUNTRY="JP"
STATE="Tokyo"
CITY="Tokyo"
ORG="RefNet"
OU="Development"
CN="localhost"

echo "SSL証明書の生成を開始します..."

# ディレクトリの作成
mkdir -p "$SSL_DIR"

# 秘密鍵の生成（4096bitに強化）
echo "秘密鍵を生成中（4096bit）..."
openssl genrsa -out "$SSL_DIR/$KEY_FILE" 4096

# 証明書署名要求（CSR）の生成
echo "証明書署名要求（CSR）を生成中..."
openssl req -new -key "$SSL_DIR/$KEY_FILE" -out "$SSL_DIR/$CSR_FILE" -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORG/OU=$OU/CN=$CN"

# 自己署名証明書の生成（SAN対応）
echo "自己署名証明書を生成中..."
openssl x509 -req -days $DAYS -in "$SSL_DIR/$CSR_FILE" -signkey "$SSL_DIR/$KEY_FILE" -out "$SSL_DIR/$CERT_FILE" -extensions v3_req -extfile <(
cat <<EOF
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
C = $COUNTRY
ST = $STATE
L = $CITY
O = $ORG
OU = $OU
CN = $CN

[v3_req]
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
DNS.2 = *.localhost
DNS.3 = refnet.local
DNS.4 = *.refnet.local
IP.1 = 127.0.0.1
IP.2 = ::1
EOF
)

# CSRファイルの削除
rm "$SSL_DIR/$CSR_FILE"

# 権限の設定（セキュリティ強化）
chmod 600 "$SSL_DIR/$KEY_FILE"
chmod 644 "$SSL_DIR/$CERT_FILE"

echo "SSL証明書の生成が完了しました:"
echo "  証明書: $SSL_DIR/$CERT_FILE"
echo "  秘密鍵: $SSL_DIR/$KEY_FILE"
echo "  有効期限: $DAYS日"
echo "  キーサイズ: 4096bit"

# 証明書の詳細を表示
echo ""
echo "証明書の詳細:"
openssl x509 -in "$SSL_DIR/$CERT_FILE" -text -noout | grep -A 1 "Subject:"
openssl x509 -in "$SSL_DIR/$CERT_FILE" -text -noout | grep -A 3 "Subject Alternative Name:" || echo "  Subject Alternative Name: DNS:localhost, IP:127.0.0.1"
openssl x509 -in "$SSL_DIR/$CERT_FILE" -text -noout | grep -A 2 "Not Before"

echo ""
echo "注意: これは開発環境用の自己署名証明書です。"
echo "本番環境では正式な証明書を使用してください。"
