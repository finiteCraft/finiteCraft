import json
import requests


session = requests.sessions.Session()
DB_URL = "https://raw.githubusercontent.com/FiniteCraft/finiteCraft/master/"

cached_chunk_hash: int = -1
cache: dict[int, dict] = {}

chunk_size = 100
def chunk_hash(key: int) -> int:
    return key // chunk_size


def load_chunk(ch: int, data_type="elements") -> None:
    global cache
    global cached_chunk_hash

    response = session.get(f"{DB_URL}/{data_type}/{ch}.json")
    if response.status_code == 404:
        raise IndexError(f"Attempted to access non-existent chunk: {data_type}/{ch}.json")

    cache = json.loads(response.content)
    cached_chunk_hash = ch


def query_data(key: int, data_type="element") -> dict:
    ch = chunk_hash(key)
    if ch != cached_chunk_hash:
        load_chunk(ch, data_type)

    return cache[key]


if __name__ == "__main__":
    query_data(103)
