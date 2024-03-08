import json
import os
import logging
import requests
from git import Repo

session = requests.sessions.Session()
LOCAL_DB_PATH = "../api"
repo = Repo(f"{LOCAL_DB_PATH}/.git")
DB_URL = "https://raw.githubusercontent.com/FiniteCraft/api/master/"
ALL_DATA_URL = "https://finitecraft.github.io/api/all_data.json"

cached_chunk_hash: int = -1
cached_data_type = ""
cache: dict[str, dict] = {}
chunk_updated = False
log = logging.getLogger("Librarian")
log.setLevel(logging.DEBUG)
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
    log.debug("Updating local git...")
    repo.index.reset()
    repo.index.add("--all")
    log.debug("Committing changes...")
    repo.index.commit("Updated data")
    log.debug("Pushing changes...")
    origin = repo.remote(name='origin')
    origin.push()


def save_cache():
    """Saves the data currently stored in the cache"""
    log.debug("Saving cache.")
    path = f"{LOCAL_DB_PATH}/{cached_data_type}"
    os.makedirs(path, exist_ok=True)
    json.dump(cache, open(f"{path}/{cached_chunk_hash}.json", "w"))
    log.debug(f"File {path}/{cached_chunk_hash}.json dumped.")


def load_chunk(ch: int, data_type="elements", create_new=False, local=False) -> None:
    """
    Loads the chunk with the given chunk hash into the cache.
    Raises and IndexError if chunk does not exist.
    :param ch: the chunk hash
    :param data_type: the type of chunk to load
    :param create_new: whether the function is allowed to create new chunks
    :param local: whether to search for a local version of the chunk
    """
    global cache
    global cached_chunk_hash
    global chunk_updated
    global cached_data_type

    rel_path = f"{data_type}/{ch}.json"

    if chunk_updated:
        save_cache()
    log.debug(f"Retrieving chunk {ch} (data type={data_type})...")

    if local:  # Searching in local database
        if os.path.exists(f"{LOCAL_DB_PATH}/{rel_path}"):
            cache = json.load(open(f"{LOCAL_DB_PATH}/{rel_path}"))
        elif create_new:
            cache = {}
        else:
            raise IndexError(f"Attempted to access non-existent chunk: {data_type}/{ch}.json")

    else:  # Searching in remote database
        response = session.get(f"{DB_URL}/{rel_path}")
        if response.status_code != 404:
            log.debug(f"Chunk {ch} (data type={data_type}) successfully downloaded!")
            cache = json.loads(response.content)
        elif create_new:
            log.debug(f"Chunk {ch} (data type={data_type}) does not exist! Creating new chunk...")
            cache = {}
        else:
            raise IndexError(f"Attempted to access non-existent chunk: {data_type}/{ch}.json")

    cached_chunk_hash = ch
    cached_data_type = data_type
    chunk_updated = False


def load_all_data() -> None:
    """
    Loads all the data into the cache.

    WARNING: After calling this function, you will no longer be able
    to load individual chunks.
    """
    global cache
    global cached_chunk_hash

    response = session.get(ALL_DATA_URL)
    if response.status_code == 404:
        raise IndexError(f"URL does not exist: {ALL_DATA_URL}")

    cache = json.loads(response.content)
    cached_chunk_hash = -2


def query_data(key: str, data_type="element", local=False) -> dict:
    """
    Fetches the data associated with the given key and data type.
    :param key: the key to search for
    :param data_type: the type of the data
    :param local: whether to use the local database
    :return: the data stored with the key
    """
    ch = chunk_hash(key)
    if ch != cached_chunk_hash and cached_chunk_hash != -2:
        log.debug(f"Loading chunk {ch} (data type={data_type})...")
        load_chunk(ch, data_type, local=local)

    return cache[key]


def store_data(key: str, data: dict, data_type="element", local=False) -> bool:
    """
    Stores the given data in the database.
    :param key: the key of the data
    :param data: the data to store
    :param data_type: the type of the data
    :param local: whether to use the local database
    :return: True if the key already existed, false otherwise
    """
    global chunk_updated

    ch = chunk_hash(key)
    if ch != cached_chunk_hash and cached_chunk_hash != -2:
        load_chunk(ch, data_type, create_new=True, local=local)

    chunk_updated = True
    newKey = key not in cache
    cache[key] = data
    log.debug(f"Saved element {key} to chunk hash {ch} successfully. Data saved: {data} (key in cache)")
    return newKey


# Name of element -> run some hashing function on it -> compression function ->
# chunk id -> load the chunk -> use the name of element to query the chunk dict


if __name__ == "__main__":
    print(query_data("Thundercougarfalconbird"))
