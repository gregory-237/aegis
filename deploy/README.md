# Развёртывание Aegis

Полный стек поднимается одним `docker compose`: PostgreSQL, VictoriaMetrics,
ingest (gRPC+mTLS), веб-панель (Django), Grafana. Сервер — Linux-хост (ВМ Proxmox VE).

## 1. Подготовка хоста (Proxmox VE)

1. Создать ВМ (Debian/Ubuntu), поставить Docker + docker compose plugin.
2. Открыть наружу порты: `1222` (агенты, mTLS), `8000` (веб-панель), при необходимости
   `3000` (Grafana). Порты БД/VM наружу не публиковать (оставить только внутри сети ВМ).
3. Склонировать репозиторий на хост.

## 2. Сертификаты (mTLS)

Серверный сертификат ОБЯЗАН содержать в SAN имя/IP, по которому агенты ходят на сервер.

```bash
# заменить на реальные имя/IP сервера
SERVER_SAN="DNS:aegis.example.com,IP:10.0.0.10" bash scripts/gen-certs.sh
```

Файлы появятся в `certs/` (он в .gitignore). compose монтирует их в ingest только на чтение.
Клиентский сертификат `certs/agent.crt` + `certs/agent.key` + `certs/ca.crt` ставятся на агента.

## 3. Конфигурация

```bash
cp deploy/.env.example deploy/.env
# отредактировать: пароли БД, AEGIS_WEB_SECRET_KEY, логин/пароль администратора,
# (опционально) токен Telegram-бота и chat_id, пароль Grafana
```

## 4. Запуск

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

- Веб-панель: `http://<host>:8000` (вход под AEGIS_ADMIN_USER/PASSWORD)
- Grafana: `http://<host>:3000` (admin / GRAFANA_PASSWORD), дашборд «Aegis — обзор машин»
- ingest слушает `:1222` (только mTLS)

Схема БД применяется автоматически (init.sql), миграции Django и создание ролей —
в web-entrypoint при старте контейнера.

## 5. Установка агента на машины (Linux/Windows)

Агент — на Python. Варианты доставки:

**A. Один исполняемый файл (рекомендуется), PyInstaller** — собрать под каждую ОС:

```bash
pip install pyinstaller -r agent/requirements.txt
pyinstaller --onefile --name aegis-agent agent/main.py
# dist/aegis-agent (Linux) или dist/aegis-agent.exe (Windows)
```

Положить рядом сертификаты и задать переменные окружения:

```bash
export AEGIS_SERVER_HOST=aegis.example.com
export AEGIS_SERVER_PORT=1222
export AEGIS_CA_CERT=/etc/aegis/ca.crt
export AEGIS_AGENT_CERT=/etc/aegis/agent.crt
export AEGIS_AGENT_KEY=/etc/aegis/agent.key
export AEGIS_POLICY_APPLY=1   # включить реальное применение firewall (нужен root/Administrator)
./aegis-agent
```

**B. Автозапуск при загрузке** — systemd (Linux) / cloud-init / Планировщик задач (Windows).
Пример unit-файла — `deploy/aegis-agent.service`.

## 6. Обновление политики

Профили (шаблоны политик) редактируются в веб-панели (роль admin) или через REST API,
назначаются машинам там же. Агент при следующем heartbeat увидит новую версию и применит её.
