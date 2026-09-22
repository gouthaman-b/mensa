# HTTP Client
API_BASE_URL = "https://www.stwdo.de/api/v2/speiseplan"
CANTEENS_ENDPOINT = "/verbrauchsorte"
MEALS_ENDPOINT_TEMPLATE = "/naechste-2-wochen?verbrauchsortnr={canteen_id}&limit=100"
HTTP_TIMEOUT = 15.0

# Cache
APP_NAME = "mensa"
CANTEENS_TTL = 24 * 3600
MEALS_TTL = 3600
CANTEENS_CACHE = "canteens"
MEALS_CACHE_TEMPLATE = "meals:{canteen_id}"
