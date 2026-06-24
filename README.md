# Aegis

Лёгкая self-hosted система мониторинга и базового управления конфигурацией
инфраструктуры: центральный сервер (Python) + агенты (Python) на машинах
Linux/Windows.

- Связь агент ↔ сервер: gRPC поверх TLS 1.3 с mTLS, порт 1222.
- Агент делает только исходящие соединения — на защищаемых машинах не
  открывается ни одного входящего порта.

## Что умеет

- Сбор метрик хоста (CPU, RAM, диски, сеть, swap) через `psutil` —
  кроссплатформенно для Linux и Windows.
- Локальный буфер метрик: при обрыве связи ничего не теряется, дошлётся
  после реконнекта.
- Применение политики безопасности при старте: правила firewall
  (`iptables` на Linux, Windows Firewall через `netsh` на Windows) и
  whitelist разрешённых доменов с default-deny остального.
- Контроль конфигурационного дрейфа: раз в минуту агент сверяет текущие
  правила с эталоном и восстанавливает их при отклонении.
- Веб-панель на Django: дашборд, страницы машин / событий / профилей,
  ролевой доступ (admin / observer), REST API на DRF, журнал аудита.
- Хранилища: PostgreSQL (состояние, профили, события, аудит) +
  VictoriaMetrics (временные ряды метрик).
- Grafana поверх VictoriaMetrics — готовый дашборд «Aegis — обзор машин».
- Telegram-уведомления при критических событиях.
- Развёртывание в один Docker Compose-файл.

## Структура

```
proto/          monitor.proto + сгенерированный код (proto/gen)
server/
  ingest/       gRPC+mTLS сервис приёма (server.py, storage/, alerts.py)
  web/          Django (дашборд, REST API, RBAC, аудит)
agent/          Python-агент: collector/, transport/, policy/, main.py
deploy/         Dockerfile'ы, docker-compose.yml, provisioning Grafana, init.sql
scripts/        gen-certs.sh — генерация PKI для mTLS
tests/          pytest
```

## Быстрый старт (dev)

```bash
# 1. окружение
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r server/ingest/requirements.txt \
            -r agent/requirements.txt \
            -r requirements-dev.txt

# 2. кодоген из proto (в proto/gen)
python -m grpc_tools.protoc -I proto \
  --python_out=proto/gen --grpc_python_out=proto/gen --pyi_out=proto/gen \
  proto/monitor.proto

# 3. сертификаты mTLS (свой CA + серверный с SAN + клиентский агента)
bash scripts/gen-certs.sh

# 4. поднять хранилища
docker compose -f deploy/docker-compose.yml up -d postgres victoriametrics

# 5. запустить приёмник
AEGIS_VM_URL=http://localhost:8428 \
AEGIS_PG_DSN=postgresql://aegis:aegis@localhost:5432/aegis \
python server/ingest/server.py

# 6. в другом терминале — агент
python agent/main.py
```

В логе ingest появятся heartbeat и метрики от агента. Соединение без валидного
клиентского сертификата сервер отклоняет.

Проверить, что метрики попадают в VictoriaMetrics:

```bash
curl 'http://localhost:8428/api/v1/export?match[]=cpu_usage_percent'
```

Состояние машин в PostgreSQL:

```bash
docker exec aegis-pg psql -U aegis -d aegis -c 'SELECT * FROM machines;'
```

## Полный стек в Docker

```bash
cp deploy/.env.example deploy/.env
$EDITOR deploy/.env
bash scripts/gen-certs.sh
docker compose -f deploy/docker-compose.yml up -d --build
```

Открыть:
- Веб-панель: `http://<host>:8000`
- Grafana: `http://<host>:3000`

Логин администратора создаётся при первом старте по переменным
`AEGIS_ADMIN_USER` / `AEGIS_ADMIN_PASSWORD`.

## Тесты

```bash
python -m pytest -q                           # 25 модульных тестов
docker exec aegis-web python manage.py test   # 4 теста Django
```

## Конфигурация

Все параметры — через переменные окружения; никаких адресов/портов/секретов
в коде. Полный список — в [deploy/.env.example](deploy/.env.example).
