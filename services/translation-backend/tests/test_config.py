import pytest
from pydantic import ValidationError

from submarine_backend.config import Settings


@pytest.mark.parametrize("host", ["127.0.0.1", "::1"])
def test_loopback_host_is_accepted(host: str) -> None:
    assert Settings(host=host).host == host


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.10", "localhost"])
def test_non_ip_or_non_loopback_host_is_rejected(host: str) -> None:
    with pytest.raises(ValidationError):
        Settings(host=host)
