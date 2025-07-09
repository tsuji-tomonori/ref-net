#!/bin/bash

# 自己署名SSL証明書生成スクリプト（開発用）

SSL_DIR="docker/nginx/ssl"
mkdir -p "$SSL_DIR"

# 秘密鍵生成
openssl genrsa -out "$SSL_DIR/server.key" 2048

# 証明書署名要求生成
openssl req -new -key "$SSL_DIR/server.key" -out "$SSL_DIR/server.csr" -subj "/C=JP/ST=Tokyo/L=Tokyo/O=RefNet/CN=localhost"

# 自己署名証明書生成
openssl x509 -req -days 365 -in "$SSL_DIR/server.csr" -signkey "$SSL_DIR/server.key" -out "$SSL_DIR/server.crt"

# 証明書署名要求削除
rm "$SSL_DIR/server.csr"

echo "SSL certificates generated in $SSL_DIR/"
echo "Note: These are self-signed certificates for development only."
