import json
import requests


session = requests.sessions.Session()
DB_URL = "https://raw.githubusercontent.com/FiniteCraft/infinite-crafts/master/"
ALL_DATA_URL = "https://finitecraft.github.io/api/all_data.json"

cached_chunk_hash: int = -1
cache: dict[str, dict] = {}

chunk_size = 100
def chunk_hash(key: str) -> int:
    prime = 7
    code = 0
    for c in key:
        code = 7 * code + ord(c)
    return code // chunk_size


def load_chunk(ch: int, data_type="elements") -> None:
    global cache
    global cached_chunk_hash

    response = session.get(f"{DB_URL}/{data_type}/{ch}.json")
    if response.status_code == 404:
        raise IndexError(f"Attempted to access non-existent chunk: {data_type}/{ch}.json")

    cache = json.loads(response.content)
    cached_chunk_hash = ch


def load_all_data() -> None:
    global cache
    global cached_chunk_hash

    response = session.get(ALL_DATA_URL)
    if response.status_code == 404:
        raise IndexError(f"URL does not exist: {ALL_DATA_URL}")

    cache = json.loads(response.content)
    cached_chunk_hash = -2


def query_data(key: str, data_type="element") -> dict:
    ch = chunk_hash(key)
    if ch != cached_chunk_hash and cached_chunk_hash != -2:
        load_chunk(ch, data_type)

    return cache[key]

def store_data(key: str, data: dict, data_type="element") -> bool:
    ch = chunk_hash(key)
    if ch != cached_chunk_hash and cached_chunk_hash != -2:
        load_chunk(ch, data_type)

    if key in cache:
        cache[key] = data


# Name of element -> run some hashing function on it -> compression function ->
# chunk id -> load the chunk -> use the name of element to query the chunk dict


if __name__ == "__main__":
    load_all_data()
    print(query_data("Thundercougarfalconbird"))
