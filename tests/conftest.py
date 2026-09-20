import pytest

from jev_vla_sim.api_smoke import synthetic_state
from jev_vla_sim.config import Config


@pytest.fixture
def cfg():
    return Config()


@pytest.fixture
def state(cfg):
    return synthetic_state(cfg)


@pytest.fixture(autouse=True)
def no_real_http(monkeypatch):
    # Tests can only use httpx.MockTransport; prevent accidental paid API/network requests.
    import httpx

    def blocked(*args, **kwargs):
        raise AssertionError("real network calls are prohibited in tests")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)
