-- Схема состояния Aegis: профили, машины, события, аудит.
-- Метрики хранятся в VictoriaMetrics, не здесь.
-- Применяется автоматически при первом старте контейнера postgres.
-- Django-приложение подключается к этим же таблицам с managed=False.

CREATE TABLE IF NOT EXISTS profiles (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    -- политика целиком в JSON: firewall-правила, allowed_domains, monitored_services
    policy      JSONB NOT NULL DEFAULT '{}'::jsonb,
    version     TEXT NOT NULL DEFAULT 'v0',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS machines (
    id          SERIAL PRIMARY KEY,
    agent_id    TEXT NOT NULL UNIQUE,
    hostname    TEXT NOT NULL DEFAULT '',
    ip          INET,
    os          TEXT NOT NULL DEFAULT '',
    arch        TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'unknown',  -- online | offline | unknown
    agent_version  TEXT NOT NULL DEFAULT '',
    config_version TEXT NOT NULL DEFAULT '',
    last_seen   TIMESTAMPTZ,
    profile_id  INTEGER REFERENCES profiles(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_machines_status ON machines(status);
CREATE INDEX IF NOT EXISTS idx_machines_last_seen ON machines(last_seen);

CREATE TABLE IF NOT EXISTS events (
    id          BIGSERIAL PRIMARY KEY,
    machine_id  INTEGER REFERENCES machines(id) ON DELETE CASCADE,
    agent_id    TEXT NOT NULL,
    type        TEXT NOT NULL,                    -- drift | service_down | policy_applied | ...
    severity    TEXT NOT NULL DEFAULT 'INFO',     -- INFO | WARNING | CRITICAL
    message     TEXT NOT NULL DEFAULT '',
    payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_events_machine ON events(machine_id);
CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at);
CREATE INDEX IF NOT EXISTS idx_events_severity ON events(severity);

-- Аудит действий администратора в веб-панели.
CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    actor       TEXT NOT NULL DEFAULT '',         -- пользователь веб-панели
    action      TEXT NOT NULL,
    target      TEXT NOT NULL DEFAULT '',
    payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
