"""Сбор метрик хоста. Кроссплатформенно через psutil (Linux/Windows)."""
from agent.collector.metrics import Sample, collect

__all__ = ["Sample", "collect"]
