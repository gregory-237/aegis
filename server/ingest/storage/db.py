"""Состояние машин и события -> PostgreSQL (psycopg2 + пул соединений).

Пустой DSN -> хранилище выключено (graceful, для dev без БД).
"""
from __future__ import annotations

import datetime as dt
import json
import logging
from typing import Optional

log = logging.getLogger("ingest.db")

try:
    import psycopg2
    from psycopg2.pool import ThreadedConnectionPool
except ImportError:  # psycopg2 не установлен — работаем без БД
    psycopg2 = None
    ThreadedConnectionPool = None  # type: ignore[assignment]


_UPSERT_MACHINE = """
INSERT INTO machines (agent_id, hostname, os, arch, ip,
                      agent_version, config_version, status, last_seen)
VALUES (%(agent_id)s, %(hostname)s, %(os)s, %(arch)s,
        NULLIF(%(ip)s, '')::inet,
        %(agent_version)s, %(config_version)s, %(status)s, %(last_seen)s)
ON CONFLICT (agent_id) DO UPDATE SET
  hostname       = COALESCE(NULLIF(EXCLUDED.hostname, ''), machines.hostname),
  os             = COALESCE(NULLIF(EXCLUDED.os, ''), machines.os),
  arch           = COALESCE(NULLIF(EXCLUDED.arch, ''), machines.arch),
  ip             = COALESCE(EXCLUDED.ip, machines.ip),
  agent_version  = COALESCE(NULLIF(EXCLUDED.agent_version, ''), machines.agent_version),
  config_version = COALESCE(NULLIF(EXCLUDED.config_version, ''), machines.config_version),
  status         = EXCLUDED.status,
  last_seen      = EXCLUDED.last_seen
RETURNING id;
"""

_INSERT_EVENT = """
INSERT INTO events (machine_id, agent_id, type, severity, message, payload)
VALUES ((SELECT id FROM machines WHERE agent_id = %(agent_id)s),
        %(agent_id)s, %(type)s, %(severity)s, %(message)s, %(payload)s::jsonb)
RETURNING id;
"""

_SELECT_POLICY = """
SELECT p.version, p.policy
FROM machines m JOIN profiles p ON m.profile_id = p.id
WHERE m.agent_id = %(agent_id)s;
"""


class StateStore:
    def __init__(self, dsn: str, minconn: int = 1, maxconn: int = 5) -> None:
        self.enabled = bool(dsn) and psycopg2 is not None
        self._pool: Optional["ThreadedConnectionPool"] = None
        if not dsn:
            log.warning("PostgreSQL не настроен (AEGIS_PG_DSN пуст) — состояние не сохраняется")
            return
        if psycopg2 is None:
            log.warning("psycopg2 не установлен — состояние не сохраняется")
            return
        self._pool = ThreadedConnectionPool(minconn, maxconn, dsn)
        log.info("PostgreSQL подключён")

    def _run(self, sql: str, params: dict):
        assert self._pool is not None
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
                return row[0] if row else None
        finally:
            self._pool.putconn(conn)

    def upsert_machine(
        self,
        agent_id: str,
        *,
        hostname: str = "",
        os: str = "",
        arch: str = "",
        ip: str = "",
        agent_version: str = "",
        config_version: str = "",
        status: str = "online",
        last_seen: Optional[dt.datetime] = None,
    ) -> Optional[int]:
        if not self.enabled:
            return None
        return self._run(
            _UPSERT_MACHINE,
            {
                "agent_id": agent_id,
                "hostname": hostname,
                "os": os,
                "arch": arch,
                "ip": ip,
                "agent_version": agent_version,
                "config_version": config_version,
                "status": status,
                "last_seen": last_seen or dt.datetime.now(dt.timezone.utc),
            },
        )

    def record_event(
        self,
        agent_id: str,
        type_: str,
        severity: str,
        message: str,
        payload: Optional[dict] = None,
    ) -> Optional[int]:
        if not self.enabled:
            return None
        return self._run(
            _INSERT_EVENT,
            {
                "agent_id": agent_id,
                "type": type_,
                "severity": severity,
                "message": message,
                "payload": json.dumps(payload or {}),
            },
        )

    def get_policy_for_agent(self, agent_id: str) -> Optional[dict]:
        """Политика назначенного машине профиля: {'version':.., 'policy':{..}} или None."""
        if not self.enabled:
            return None
        assert self._pool is not None
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(_SELECT_POLICY, {"agent_id": agent_id})
                row = cur.fetchone()
                if not row:
                    return None
                return {"version": row[0], "policy": row[1] or {}}
        finally:
            self._pool.putconn(conn)

    def close(self) -> None:
        if self._pool is not None:
            self._pool.closeall()
