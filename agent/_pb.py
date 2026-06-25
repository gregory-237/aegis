"""Единая точка импорта сгенерированного из proto кода (лежит в proto/gen)."""
from __future__ import annotations

import pathlib
import sys

_GEN = pathlib.Path(__file__).resolve().parents[1] / "proto" / "gen"
if str(_GEN) not in sys.path:
    sys.path.insert(0, str(_GEN))

import monitor_pb2 as pb  # noqa: E402
import monitor_pb2_grpc as pb_grpc  # noqa: E402

__all__ = ["pb", "pb_grpc"]
