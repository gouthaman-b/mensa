from unittest.mock import Mock, patch

from mensa import client
from mensa.constants import API_BASE_URL, CANTEENS_ENDPOINT, MEALS_ENDPOINT_TEMPLATE


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload

    def raise_for_status(self):
        return None


def test_fetch_canteens_raw_ignores_cache():
    expected = [{"id": 1, "name": "Mensa A"}]
    fake_get = Mock(return_value=FakeResponse(expected))

    with (
        patch.object(client, "_get", fake_get),
        patch.object(client.cache, "get", side_effect=AssertionError("cache should not be used")),
        patch.object(client.cache, "set", side_effect=AssertionError("cache should not be used")),
    ):
        result = client.fetch_canteens_raw(use_cache=False)

    assert result == expected
    assert fake_get.call_args.args[0] == f"{API_BASE_URL}{CANTEENS_ENDPOINT}"


def test_fetch_meals_raw_ignores_cache():
    expected = [{"id": 42, "name": "Gemüse-Curry"}]
    fake_get = Mock(return_value=FakeResponse(expected))

    with (
        patch.object(client, "_get", fake_get),
        patch.object(client.cache, "get", side_effect=AssertionError("cache should not be used")),
        patch.object(client.cache, "set", side_effect=AssertionError("cache should not be used")),
    ):
        result = client.fetch_meals_raw(7, use_cache=False)

    assert result == expected
    assert (
        fake_get.call_args.args[0]
        == f"{API_BASE_URL}{MEALS_ENDPOINT_TEMPLATE.format(canteen_id=7)}"
    )
