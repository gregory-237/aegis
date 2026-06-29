"""Тест конвертации JSON-политики профиля в pb.Policy на стороне ingest."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "proto" / "gen"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "server" / "ingest"))

from server import _policy_dict_to_pb  # noqa: E402


def test_policy_dict_to_pb_full():
    d = {
        "firewall": [
            {"chain": "OUTPUT", "action": "ACCEPT", "protocol": "tcp", "remote": "1.2.3.4", "port": 443}
        ],
        "allowed_domains": ["example.com", "api.local"],
        "monitored_services": ["sshd", "docker"],
        "metrics_interval_sec": 15,
    }
    pol = _policy_dict_to_pb(d)
    assert list(pol.allowed_domains) == ["example.com", "api.local"]
    assert list(pol.monitored_services) == ["sshd", "docker"]
    assert pol.metrics_interval_sec == 15
    assert len(pol.firewall) == 1
    assert pol.firewall[0].action == "ACCEPT"
    assert pol.firewall[0].port == 443


def test_policy_dict_to_pb_empty_defaults():
    pol = _policy_dict_to_pb({})
    assert list(pol.allowed_domains) == []
    assert pol.metrics_interval_sec == 30
    assert len(pol.firewall) == 0
