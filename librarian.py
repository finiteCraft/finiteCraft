import json
import os

import requests
from git import Repo

session = requests.sessions.Session()
repo = Repo("../api/.git")
DB_URL = "https://raw.githubusercontent.com/FiniteCraft/api/master/"
ALL_DATA_URL = "https://finitecraft.github.io/api/all_data.json"

cached_chunk_hash: int = -1
cached_data_type = ""
cache: dict[str, dict] = {}
chunk_updated = False

chunk_size = 100


def chunk_hash(key: str) -> int:
    """
    Generate the chunk hash for the given key using a combination
    of polynomial hash codes and an uncapped compression function
    (currently using integer division).
    """
    prime = 7
    code = 0
    for c in key:
        code = prime * code + ord(c)
    return code // chunk_size


def update_remote():
    """Pushes the library data to the online database"""
    repo.index.reset()
    repo.index.add(".")
    repo.index.commit("Updated data")
    origin = repo.remote(name='origin')
    origin.push()


def save_cache():
    """Saves the data currently stored in the cache"""
    path = f"../api/{cached_data_type}"
    os.makedirs(path, exist_ok=True)
    json.dump(cache, open(f"{path}/{cached_chunk_hash}.json", "w"))


def load_chunk(ch: int, data_type="elements", create_new=False) -> None:
    """
    Loads the chunk with the given chunk hash into the cache.
    Raises and IndexError if chunk does not exist.
    :param ch: the chunk hash
    :param data_type: the type of chunk to load
    :param create_new: whether the function is allowed to create new chunks
    """
    global cache
    global cached_chunk_hash
    global chunk_updated
    global cached_data_type

    if chunk_updated:
        save_cache()

    response = session.get(f"{DB_URL}/{data_type}/{ch}.json")
    if response.status_code == 404:
        if not create_new:
            raise IndexError(f"Attempted to access non-existent chunk: {data_type}/{ch}.json")
        cache = {}
    else:
        cache = json.loads(response.content)
    cached_chunk_hash = ch
    cached_data_type = data_type
    chunk_updated = False


def load_all_data() -> None:
    """
    Loads all the data into the cache.

    WARNING: After calling this function, you will no longer be able
    to load individual chunks.
    :return:
    """
    global cache
    global cached_chunk_hash

    response = session.get(ALL_DATA_URL)
    if response.status_code == 404:
        raise IndexError(f"URL does not exist: {ALL_DATA_URL}")

    cache = json.loads(response.content)
    cached_chunk_hash = -2


def query_data(key: str, data_type="element") -> dict:
    """
    Fetches the data associated with the given key and data type.
    :param key:
    :param data_type:
    :return:
    """
    ch = chunk_hash(key)
    if ch != cached_chunk_hash and cached_chunk_hash != -2:
        load_chunk(ch, data_type)

    return cache[key]


def store_data(key: str, data: dict, data_type="element") -> bool:
    """
    Stores the given data in the database.
    :param key: the key of the data
    :param data: the data to store
    :param data_type: the type of the data
    :return: True if the key already existed, false otherwise
    """
    global chunk_updated

    ch = chunk_hash(key)
    if ch != cached_chunk_hash and cached_chunk_hash != -2:
        load_chunk(ch, data_type, create_new=True)

    chunk_updated = True
    if key in cache:
        cache[key] = data
        return True

    cache[key] = data
    return False


# Name of element -> run some hashing function on it -> compression function ->
# chunk id -> load the chunk -> use the name of element to query the chunk dict


if __name__ == "__main__":
    print(query_data("Thundercougarfalconbird"))
