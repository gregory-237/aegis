#!/usr/bin/env bash
# Генерация PKI для mTLS: свой CA, серверный сертификат с SAN и клиентский
# сертификат агента. Всё кладётся в /certs (в .gitignore — не коммитим).
#
# Использование:
#   bash scripts/gen-certs.sh
# Параметры через env:
#   SERVER_CN  — CN серверного сертификата (default: aegis-ingest)
#   SERVER_SAN — SAN сервера (default: DNS:localhost,DNS:aegis-ingest,IP:127.0.0.1)
#                Сервер ОБЯЗАН иметь SAN с именем/IP, к которым подключается агент.
#   AGENT_CN   — CN клиентского сертификата агента (default: agent-001)
#   DAYS       — срок действия выпускаемых сертификатов (default: 825)
set -euo pipefail

# На Git Bash (Windows) MSYS преобразует аргумент "/O=Aegis/CN=..." в путь.
# Исключаем из авто-конвертации только subject (начинается с "/O="), пути к файлам
# при этом конвертируются нормально. На обычном Linux переменная игнорируется.
export MSYS2_ARG_CONV_EXCL="/O="

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CERTS="$ROOT/certs"
mkdir -p "$CERTS"

SERVER_CN="${SERVER_CN:-aegis-ingest}"
SERVER_SAN="${SERVER_SAN:-DNS:localhost,DNS:aegis-ingest,IP:127.0.0.1}"
AGENT_CN="${AGENT_CN:-agent-001}"
DAYS="${DAYS:-825}"
CA_DAYS="${CA_DAYS:-3650}"

echo ">> certs dir: $CERTS"

# --- 1. Корневой CA -----------------------------------------------------------
if [[ -f "$CERTS/ca.crt" ]]; then
  echo ">> CA уже существует, пропускаю (удали certs/ca.* чтобы пересоздать)"
else
  echo ">> генерирую CA"
  openssl genrsa -out "$CERTS/ca.key" 4096
  openssl req -x509 -new -nodes -key "$CERTS/ca.key" -sha256 -days "$CA_DAYS" \
    -subj "/O=Aegis/CN=Aegis Root CA" \
    -out "$CERTS/ca.crt"
fi

# --- 2. Серверный сертификат (с SAN) -----------------------------------------
echo ">> генерирую серверный сертификат (CN=$SERVER_CN, SAN=$SERVER_SAN)"
openssl genrsa -out "$CERTS/server.key" 2048
openssl req -new -key "$CERTS/server.key" \
  -subj "/O=Aegis/CN=$SERVER_CN" \
  -out "$CERTS/server.csr"
printf "subjectAltName=%s\nextendedKeyUsage=serverAuth\n" "$SERVER_SAN" > "$CERTS/server.ext"
openssl x509 -req -in "$CERTS/server.csr" \
  -CA "$CERTS/ca.crt" -CAkey "$CERTS/ca.key" -CAcreateserial \
  -days "$DAYS" -sha256 \
  -extfile "$CERTS/server.ext" \
  -out "$CERTS/server.crt"

# --- 3. Клиентский сертификат агента -----------------------------------------
echo ">> генерирую клиентский сертификат агента (CN=$AGENT_CN)"
openssl genrsa -out "$CERTS/agent.key" 2048
openssl req -new -key "$CERTS/agent.key" \
  -subj "/O=Aegis/CN=$AGENT_CN" \
  -out "$CERTS/agent.csr"
printf "extendedKeyUsage=clientAuth\n" > "$CERTS/agent.ext"
openssl x509 -req -in "$CERTS/agent.csr" \
  -CA "$CERTS/ca.crt" -CAkey "$CERTS/ca.key" -CAcreateserial \
  -days "$DAYS" -sha256 \
  -extfile "$CERTS/agent.ext" \
  -out "$CERTS/agent.crt"

rm -f "$CERTS"/*.csr "$CERTS"/*.ext

echo ">> готово. содержимое certs/:"
ls -1 "$CERTS"
echo ">> server SAN:"
openssl x509 -in "$CERTS/server.crt" -noout -ext subjectAltName || true
