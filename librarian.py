import json
import os
import logging
import requests
from git import Repo
import shutil

SESSION = requests.sessions.Session()
LOCAL_DB_PATH = f"{os.path.dirname(os.path.realpath(__file__))}/../api"
REPO = Repo(f"{LOCAL_DB_PATH}/.git")
DB_URL = "https://raw.githubusercontent.com/FiniteCraft/api/master/"
ALL_DATA_URL = "https://finitecraft.github.io/api/all_data.json"
DATA_TYPES = ["display", "search"]

cached_chunk_hash: int = -1
cached_data_type = ""
cache: dict[str, dict] = {}
chunk_updated = False
log = logging.getLogger("Librarian")
log.setLevel(logging.INFO)
num_chunks = 64
CHUNK_CAPACITY = 100


def init():
    global num_chunks

    update_local()

    if os.path.exists(f"{LOCAL_DB_PATH}/settings.json"):
        with open(f"{LOCAL_DB_PATH}/settings.json", "r") as sp:
            settings = json.load(sp)
            num_chunks = settings["num_chunks"]
    else:
        num_chunks = 64
        with open(f"{LOCAL_DB_PATH}/settings.json", "w") as sp:
            settings = {"num_chunks": num_chunks}
            json.dump(settings, sp)


def remove_directories():
    """
    Remove the directory (used to reset git)
    :return:
    """
    for dir_name in DATA_TYPES:
        if os.path.exists(LOCAL_DB_PATH + "/" + dir_name):
            shutil.rmtree(LOCAL_DB_PATH + "/" + dir_name)


def chunk_hash(key: str, nc: int | None = None) -> int:
    """
    Generate the chunk hash for the given key using a combination
    of polynomial hash codes and modulo compression
    """
    if nc is None:
        nc = num_chunks

    prime = 7
    code = 0
    for c in key:
        code = prime * code + ord(c)
    return code % nc


def rehash(new_num_chunks):
    global num_chunks

    log.info("Beginning Rehash...")

    # Save cache before doing anything else
    log.debug(f"Saving cache...")
    save_cache()

    # Create temporary storage
    log.debug(f"Creating temp dir...")
    for t in DATA_TYPES:
        os.makedirs(f"{LOCAL_DB_PATH}/temp/{t}", exist_ok=True)

    if os.path.exists(f"{LOCAL_DB_PATH}/display"):
        files = os.listdir(f"{LOCAL_DB_PATH}/display")  # get all existing files
    else:
        files = []
    num_chunks = new_num_chunks

    for f in files:
        log.debug(f"Rehashing file: {f}")
        for t in DATA_TYPES:
            if not os.path.exists(f"{LOCAL_DB_PATH}/{t}/{f}"):
                continue

            fp = open(f"{LOCAL_DB_PATH}/{t}/{f}")
            old_chunk = json.load(fp)

            for key in old_chunk:
                ch = chunk_hash(key)
                if os.path.exists(f"{LOCAL_DB_PATH}/temp/{t}/{ch}.json"):
                    nfp = open(f"{LOCAL_DB_PATH}/temp/{t}/{ch}.json", "r")
                    new_chunk = json.load(nfp)
                    nfp.close()
                else:
                    new_chunk = dict()

                new_chunk[key] = old_chunk[key]

                nfp = open(f"{LOCAL_DB_PATH}/temp/{t}/{ch}.json", "w")
                json.dump(new_chunk, nfp)
                nfp.close()

            fp.close()

    log.debug("Removing old files...")
    remove_directories()
    log.debug("Moving new files out of temp dir...")
    for t in DATA_TYPES:
        shutil.move(f"{LOCAL_DB_PATH}/temp/{t}", f"{LOCAL_DB_PATH}/{t}")

    log.debug("Removing temp dir...")
    shutil.rmtree(f"{LOCAL_DB_PATH}/temp")

    # Update database num_chunks
    log.debug("Updating settings.json...")
    sp = open(f"{LOCAL_DB_PATH}/settings.json", "r")
    settings = json.load(sp)
    sp.close()
    sp = open(f"{LOCAL_DB_PATH}/settings.json", "w")
    settings["num_chunks"] = num_chunks
    json.dump(settings, sp)
    sp.close()

    log.info("Rehash Complete! Resetting cache...")
    reset_cache()
    log.info("Cache reset!")


def ensure_capacity(check_all=False):
    """
    Checks if the capacity of the chunks has been reached, and,
    if necessary, performs a rehash.

    :param check_all: if true, check all chunks. if false, only check the cache
    :return: whether a rehash was necessary
    """
    if not check_all:
        if len(cache) > CHUNK_CAPACITY:
            log.debug("Max capacity reached in cache. Rehashing...")
            rehash(num_chunks * 2)
            return True
        return False

    if os.path.exists(f"{LOCAL_DB_PATH}/display"):
        files = os.listdir(f"{LOCAL_DB_PATH}/display")  # get all existing files
    else:
        files = []

    for f in files:
        fp = open(f"{LOCAL_DB_PATH}/display/{f}")
        data = json.load(fp)
        if len(data) > CHUNK_CAPACITY:
            log.debug(f"Max capacity reached in file {f}. Rehashing...")
            fp.close()
            rehash(num_chunks * 2)
            return True
        fp.close()
    return False


def update_remote():
    """Pushes the library data to the online database"""
    log.info("Beginning push process...")
    REPO.git.execute("git add . --all")
    log.debug("Committing changes...")
    REPO.index.commit("Updated data")
    log.debug("Pushing changes...")
    origin = REPO.remote(name='origin')
    origin.push()
    log.info("Push attempt done.")
    REPO.index.reset()  # Do a reset here to only track files that still exist
    REPO.index.add("**")


def update_local():
    """Pulls from the online database to the library"""
    log.info("Beginning pull process...")
    log.debug("Pulling changes...")
    origin = REPO.remote(name='origin')
    origin.pull()
    log.info("Pull attempt done.")
    REPO.index.reset()  # Do a reset here to only track files that still exist
    REPO.index.add("**")



def save_cache():
    """Saves the data currently stored in the cache"""

    if cached_chunk_hash == -1:
        return

    log.debug("Saving cache.")
    path = f"{LOCAL_DB_PATH}/{cached_data_type}"
    os.makedirs(path, exist_ok=True)
    with open(f"{path}/{cached_chunk_hash}.json", "w") as fp:
        json.dump(cache, fp)
    log.debug(f"File {path}/{cached_chunk_hash}.json dumped.")


def reset_cache():
    global cached_chunk_hash
    global cached_data_type
    global cache
    global chunk_updated

    cached_chunk_hash = -1
    cached_data_type = ""
    cache = {}
    chunk_updated = False


def load_chunk(ch: int, data_type="display", create_new=False, local=False) -> None:
    """
    Loads the chunk with the given chunk hash into the cache.
    Raises an IndexError if chunk does not exist.
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
            with open(f"{LOCAL_DB_PATH}/{rel_path}") as fp:
                cache = json.load(fp)
        elif create_new:
            cache = {}
        else:
            raise IndexError(f"Attempted to access non-existent chunk: {data_type}/{ch}.json")

    else:  # Searching in remote database
        response = SESSION.get(f"{DB_URL}/{rel_path}")
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

    response = SESSION.get(ALL_DATA_URL)
    if response.status_code == 404:
        raise IndexError(f"URL does not exist: {ALL_DATA_URL}")

    cache = json.loads(response.content)
    cached_chunk_hash = -2


def query_data(key: str, data_type="display", local=False) -> dict | None:
    """
    Fetches the data associated with the given key and data type.
    :param key: the key to search for
    :param data_type: the type of the data
    :param local: whether to use the local database
    :return: the data stored with the key
    """
    ch = chunk_hash(key)
    if (ch != cached_chunk_hash or cached_data_type != data_type) and cached_chunk_hash != -2:
        log.debug(f"Loading chunk {ch} (data type={data_type})...")
        load_chunk(ch, data_type, local=local)

    if key in cache:
        return cache[key]
    return None


def store_data(key: str, data: dict, data_type="display", local=False) -> bool:
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
    if (ch != cached_chunk_hash or cached_data_type != data_type) and cached_chunk_hash != -2:
        load_chunk(ch, data_type, create_new=True, local=local)

    chunk_updated = True
    new_key = key not in cache
    cache[key] = data
    log.debug(f"Saved element {key} to chunk hash {ch} successfully. Data saved: {data} (key in cache)")

    return new_key


# Name of element -> run some hashing function on it -> compression function ->
# chunk id -> load the chunk -> use the name of element to query the chunk dict


if __name__ == "__main__":
    logging.basicConfig()
    log.setLevel(logging.DEBUG)
    update_local()
    init()
    rehash(128)
    update_remote()
