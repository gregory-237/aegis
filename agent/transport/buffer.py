"""Локальный буфер метрик: при обрыве связи копим на диск, дошлём после реконнекта."""
from __future__ import annotations

import json
import pathlib
from collections import deque
from datetime import datetime, timezone

from agent.collector import Sample


class MetricsBuffer:
    def __init__(self, path: pathlib.Path, max_items: int) -> None:
        self._path = path
        self._max = max_items
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, samples: list[Sample]) -> None:
        """Дописать метрики в буфер, удерживая размер в пределах max_items."""
        with self._path.open("a", encoding="utf-8") as f:
            for s in samples:
                f.write(
                    json.dumps(
                        {
                            "name": s.name,
                            "value": s.value,
                            "ts": s.ts.isoformat(),
                            "labels": s.labels,
                        }
                    )
                    + "\n"
                )
        self._trim()

    def drain(self) -> list[Sample]:
        """Прочитать всё накопленное и очистить файл. Вернуть список Sample."""
        if not self._path.exists():
            return []
        out: list[Sample] = []
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    out.append(
                        Sample(
                            name=d["name"],
                            value=float(d["value"]),
                            ts=datetime.fromisoformat(d["ts"]),
                            labels=dict(d.get("labels", {})),
                        )
                    )
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue  # битую строку пропускаем
        self._path.write_text("", encoding="utf-8")
        return out

    def is_empty(self) -> bool:
        return not self._path.exists() or self._path.stat().st_size == 0

    def _trim(self) -> None:
        """Грубое ограничение размера: оставляем последние max_items строк."""
        try:
            with self._path.open("r", encoding="utf-8") as f:
                lines = f.readlines()
        except OSError:
            return
        if len(lines) <= self._max:
            return
        keep = deque(lines, maxlen=self._max)
        self._path.write_text("".join(keep), encoding="utf-8")
