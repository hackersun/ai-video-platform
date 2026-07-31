import sys
from types import SimpleNamespace

from app.features.video_generation.adapters.ark import create_ark_client


def test_ark_client_uses_direct_network_and_disables_hidden_retries(monkeypatch) -> None:
    captured = {}

    def ark(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setitem(sys.modules, "volcenginesdkarkruntime", SimpleNamespace(Ark=ark))

    create_ark_client("secret", "https://ark.example/api/v3")

    assert captured["http_client"]._trust_env is False
    assert captured["max_retries"] == 0
