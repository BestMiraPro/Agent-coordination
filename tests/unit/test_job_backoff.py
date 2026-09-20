from packages.persistence.jobs import retry_delay_seconds


def test_retry_delay_is_exponential_and_capped() -> None:
    assert retry_delay_seconds(0) == 0
    assert retry_delay_seconds(1) == 2
    assert retry_delay_seconds(2) == 4
    assert retry_delay_seconds(3) == 8
    assert retry_delay_seconds(20) == 300
