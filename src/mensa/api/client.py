import httpx

from .. import cache

API_BASE_URL = "https://www.stwdo.de/api/v2/speiseplan"
CANTEENS_ENDPOINT = "/verbrauchsorte"
MEALS_ENDPOINT_TEMPLATE = "/naechste-2-wochen?verbrauchsortnr={canteen_id}&limit=100"
HTTP_TIMEOUT = 15.0


def _get(url: str, params: dict | None = None) -> httpx.Response:
    with httpx.Client(timeout=HTTP_TIMEOUT) as http_client:
        resp = http_client.get(url)
        resp.raise_for_status()
        return resp


def fetch_canteens_raw(use_cache: bool = True) -> list[dict]:
    cache_key = "canteens"
    if use_cache:
        cached = cache.get(cache_key, ttl=cache.CANTEENS_TTL)
        if cached is not None:
            return cached
    url = f"{API_BASE_URL}{CANTEENS_ENDPOINT}"
    data = _get(url).json()
    cache.set(cache_key, data)
    return data


def fetch_meals_raw(canteen_id: int, use_cache: bool = True) -> list[dict]:
    cache_key = f"meals:{canteen_id}"
    if use_cache:
        cached = cache.get(cache_key, ttl=cache.MEALS_TTL)
        if cached is not None:
            return cached
    url = f"{API_BASE_URL}{MEALS_ENDPOINT_TEMPLATE.format(canteen_id=canteen_id)}"
    data = _get(url).json()
    cache.set(cache_key, data)
    return data
