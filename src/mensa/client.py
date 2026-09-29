import httpx

from . import cache
from .constants import *
from .error import MensaError


def _get(url: str) -> httpx.Response:
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as http_client:
            resp = http_client.get(url)
            resp.raise_for_status()
            return resp
    except httpx.HTTPError as err:
        raise MensaError("[client]:Network error", err)


def _fetch(
    url: str, use_cache: bool = False, cache_key=CANTEENS_CACHE, cache_ttl=CANTEENS_TTL
) -> list[dict]:
    if use_cache:
        cached = cache.get(cache_key, ttl=cache_ttl)
        if cached is not None:
            return cached
    data = _get(url).json()
    if use_cache:
        cache.set(cache_key, data)
    return data


def fetch_canteens_raw(use_cache: bool = False) -> list[dict]:
    url = f"{API_BASE_URL}{CANTEENS_ENDPOINT}"
    return _fetch(url, use_cache=use_cache, cache_key=CANTEENS_CACHE, cache_ttl=CANTEENS_TTL)


def fetch_meals_raw(canteen_id: int, use_cache: bool = False) -> list[dict]:
    cache_key = f"{MEALS_CACHE_TEMPLATE.format(canteen_id=canteen_id)}"
    url = f"{API_BASE_URL}{MEALS_ENDPOINT_TEMPLATE.format(canteen_id=canteen_id)}"
    return _fetch(url, use_cache=use_cache, cache_key=cache_key, cache_ttl=MEALS_TTL)
