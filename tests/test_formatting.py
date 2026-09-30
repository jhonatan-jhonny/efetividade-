from utils.formatting import calculate_change, per_100k


def test_rate_per_100k():
    assert per_100k(14, 240_000) == 14 / 240_000 * 100_000


def test_rate_preserves_null_and_invalid_population():
    assert per_100k(None, 100_000) is None
    assert per_100k(3, None) is None
    assert per_100k(3, 0) is None


def test_calculate_change_edge_cases():
    assert calculate_change(12, 10).percent == 20
    assert calculate_change(12, 0).percent is None
    assert calculate_change(None, 10).comparable is False
    assert calculate_change(12, 10, comparable=False).reason == "mudança metodológica"

