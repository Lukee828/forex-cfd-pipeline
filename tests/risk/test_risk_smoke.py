import pytest

pytestmark = pytest.mark.skip(
    reason="Risk test slice scaffolded; real tests to follow."
)


def test_risk_placeholder():
    # Intentionally simple & skipped: keeps suite green until risk code lands.
    assert True
