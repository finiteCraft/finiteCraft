import ujson
import os
import logging
from collections.abc import Callable

import requests
from git import Repo
import shutil
from collections import deque

import librarian.structures as struct

if "H_LIB" not in globals():
    H_LIB = None  # Header tag to keep from re-initializing the data on successive imports
    
    # Librarian expects you to have a GitHub repo set up as the
    # destination for all the stored data. This is how it will retrieve data,
    # but more importantly, this is how it will save its. For this to work,
    # you NEED to have a local instance of your repository that this program
    # can edit. Once you have it, replace LOCAL_DB_PATH with a path to the
    # directory containing the associated .git file.
    DB_URL = "https://raw.githubusercontent.com/FiniteCraft/api/master/"
    SESSION = requests.sessions.Session()
    LOCAL_DB_PATH = f"{os.path.dirname(os.path.realpath(__file__))}/../../api"
    REPO = Repo(f"{LOCAL_DB_PATH}/.git")
    
    # Logging setup
    LOG = logging.getLogger("Librarian")
    LOG.setLevel(logging.INFO)

    # Some file-wide constants
    CHUNK_CAPACITY = 1000    # The max size of a chunk
    CACHE_CAPACITY = 100     # The max number of chunks allowed to be simultaneously loaded
    DEFAULT_NUM_CHUNKS = 64  # Default number of chunks in the library

    chunk_map: dict[str, list[struct.Chunk | None]] = {}  # A dictionary-array containing pointers to all loaded chunks
    num_chunks: int = 0  # Number of chunks in the database
    cache: deque[struct.Chunk] = deque()  # A queue of the loaded chunks. Used to keep track of order added

    # region Load the data from settings.json
    if os.path.exists(f"{LOCAL_DB_PATH}/settings.json"):
        with open(f"{LOCAL_DB_PATH}/settings.json", "r") as sp:
            settings = ujson.load(sp)
            num_chunks = settings["num_chunks"]
            struct.DATATYPES = {dt: set(attr) for dt, attr in settings["datatypes"].items()}

    else:
        num_chunks = DEFAULT_NUM_CHUNKS
        struct.DATATYPES = {}
        with open(f"{LOCAL_DB_PATH}/settings.json", "w") as sp:
            settings = {"num_chunks": DEFAULT_NUM_CHUNKS, "datatypes": {}}
            ujson.dump(settings, sp)
    # endregion

    # Initialize the chunk map
    chunk_map = {dt: [None for _ in range(num_chunks)] for dt in struct.DATATYPES}

    LOG.info("Loaded Librarian.")


# region Basic Utilities

def set_logging(log_level: int):
    LOG.setLevel(log_level)


def save_settings():
    LOG.debug("Saving settings...")
    with open(f"{LOCAL_DB_PATH}/settings.json", "w") as sp:

        settings = {"num_chunks": num_chunks, "datatypes": {dt: list(attr) for dt, attr in struct.DATATYPES.items()}}
        ujson.dump(settings, sp, indent=4)
    LOG.debug("Settings saved.")


def remove_directories():
    """
    Remove the directory (used to reset git)
    :return:
    """
    LOG.debug("Clearing directories, say goodbye lol")
    for dir_name in struct.DATATYPES:
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


def load_chunk(ch: int, datatype="display", create_new=False, local=False) -> struct.Chunk:
    """
    Loads the chunk with the given chunk hash into the cache.
    Raises an IndexError if chunk does not exist.
    :param ch: the chunk hash
    :param datatype: the type of chunk to load
    :param create_new: whether the function is allowed to create new chunks
    :param local: whether to search for a local version of the chunk
    """
    global cache
    global chunk_map

    rel_path = f"{datatype}/{ch}.json"

    if len(cache) >= CACHE_CAPACITY:
        cache_pop()

    LOG.debug(f"Retrieving chunk {ch} (data type={datatype})...")

    if local:  # Searching in local database
        if os.path.exists(f"{LOCAL_DB_PATH}/{rel_path}"):
            with open(f"{LOCAL_DB_PATH}/{rel_path}") as fp:
                data = ujson.load(fp)
        elif create_new:
            data = {}
        else:
            raise IndexError(f"Attempted to access non-existent chunk: {datatype}/{ch}.json")

    else:  # Searching in remote database
        response = SESSION.get(f"{DB_URL}/{rel_path}")
        if response.status_code != 404:
            data = ujson.loads(response.content)
        elif create_new:
            LOG.debug(f"lib_struct.Chunk {ch} (data type={datatype}) does not exist! Creating new chunk...")
            data = {}
        else:
            raise IndexError(f"Attempted to access non-existent chunk: {datatype}/{ch}.json")

    chunk = struct.Chunk(ch, datatype, {tag: struct.dict_to_nibble(d, tag, datatype) for tag, d in data.items()})
    chunk_map[datatype][ch] = chunk  # Save the chunk here
    cache.append(chunk)    # Still add it to queue to keep track of order added
    LOG.debug(f"lib_struct.Chunk {ch} (data type={datatype}) successfully loaded!")
    return chunk


def rehash(new_num_chunks):
    """Rehashes all the data in the database to fit the new number of chunks."""
    global chunk_map
    global num_chunks

    LOG.info("Beginning Rehash...")

    # Save cache before doing anything else
    LOG.debug(f"Saving cache...")
    cache_clear()

    # Create temporary storage
    LOG.debug(f"Creating temp dir...")
    for t in struct.DATATYPES:
        os.makedirs(f"{LOCAL_DB_PATH}/temp/{t}", exist_ok=True)

    if len(struct.DATATYPES) and os.path.exists(f"{LOCAL_DB_PATH}/{list(struct.DATATYPES.keys())[0]}"):
        files = os.listdir(f"{LOCAL_DB_PATH}/{list(struct.DATATYPES.keys())[0]}")  # get all existing files
    else:
        files = []
    num_chunks = new_num_chunks
    chunk_map = {dt: [None for _ in range(num_chunks)] for dt in struct.DATATYPES}

    for f in files:
        LOG.debug(f"Rehashing file: {f}")
        for t in struct.DATATYPES:
            if not os.path.exists(f"{LOCAL_DB_PATH}/{t}/{f}"):
                continue

            fp = open(f"{LOCAL_DB_PATH}/{t}/{f}")
            old_chunk = ujson.load(fp)

            for key in old_chunk:
                ch = chunk_hash(key)
                if os.path.exists(f"{LOCAL_DB_PATH}/temp/{t}/{ch}.json"):
                    nfp = open(f"{LOCAL_DB_PATH}/temp/{t}/{ch}.json", "r")
                    new_chunk = ujson.load(nfp)
                    nfp.close()
                else:
                    new_chunk = dict()

                new_chunk[key] = old_chunk[key]

                nfp = open(f"{LOCAL_DB_PATH}/temp/{t}/{ch}.json", "w")
                ujson.dump(new_chunk, nfp)
                nfp.close()

            fp.close()

    LOG.debug("Removing old files...")
    remove_directories()
    LOG.debug("Moving new files out of temp dir...")
    for t in struct.DATATYPES:
        shutil.move(f"{LOCAL_DB_PATH}/temp/{t}", f"{LOCAL_DB_PATH}/{t}")

    LOG.debug("Removing temp dir...")
    shutil.rmtree(f"{LOCAL_DB_PATH}/temp")

    # Update database num_chunks
    save_settings()


def ensure_capacity():
    """
    Checks if the capacity of the chunks has been reached, and,
    if necessary, performs a rehash.
    :return: whether a rehash was necessary
    """
    if os.path.exists(f"{LOCAL_DB_PATH}/display"):
        files = os.listdir(f"{LOCAL_DB_PATH}/display")  # get all existing files
    else:
        files = []

    for f in files:
        fp = open(f"{LOCAL_DB_PATH}/display/{f}")
        data = ujson.load(fp)
        if len(data) > CHUNK_CAPACITY:
            LOG.debug(f"Max capacity reached in file {f}. Rehashing...")
            fp.close()
            rehash(num_chunks * 2)
            ensure_capacity()
            return True
        fp.close()
    return False


def update_remote():
    """Pushes the library data to the online database"""
    LOG.info("Beginning push process...")
    REPO.git.add(all=True)  # This does work on Linux. Use REPO.git.execute("git add . --all") on Windows
    LOG.debug("Committing changes...")
    REPO.index.commit("Updated data")
    LOG.debug("Pushing changes...")
    origin = REPO.remote(name='origin')
    origin.push()
    LOG.info("Push attempt done.")
    REPO.index.reset()  # Do a reset here to only track files that still exist
    REPO.index.add("**")


def update_local():
    """Pulls from the online database to the library"""
    LOG.info("Beginning pull process...")
    LOG.debug("Pulling changes...")
    origin = REPO.remote(name='origin')
    origin.fetch()
    REPO.git.reset('--hard', 'HEAD')
    LOG.info("Pull attempt done.")
    REPO.index.reset()  # Do a reset here to only track files that still exist
    REPO.index.add("**")
        
# endregion


# region Datatype Interaction

def get_datatypes() -> dict[str, set[str]]:
    return struct.DATATYPES


def declare_new_datatype(datatype: str, attributes: set[str]):
    """Declares a new datatype for use. Give a set of attributes for it to have."""
    if datatype in struct.DATATYPES:
        raise ValueError(f"Datatype \"{datatype}\" already exists")

    struct.DATATYPES[datatype] = attributes.copy()
    os.makedirs(f"{LOCAL_DB_PATH}/{datatype}")
    chunk_map[datatype] = [None for _ in range(num_chunks)]
    save_settings()


def remove_datatype(datatype: str) -> bool:
    """Removes a datatype and all data of that type. Returns if datatype was removed successfully."""
    if datatype not in struct.DATATYPES:
        return False

    struct.DATATYPES.pop(datatype)
    shutil.rmtree(f"{LOCAL_DB_PATH}/{datatype}")
    save_settings()
    return True


def map_data(datatype_old: str, datatype_new: str, mapping: Callable[[struct.Nibble], struct.Nibble]) -> None:
    """
    Maps all data from one datatype to the new datatype using the provided mapping function.
    Be aware that this will overwrite all the data in the new datatype,
    so it's best to use this when creating new datatypes, but stay away from it normally.
    :param datatype_old: the datatype to map from
    :param datatype_new: the datatype to map to
    :param mapping: the custom mapping function
    :return:
    """
    LOG.debug(f"Mapping data from '{datatype_old}' to '{datatype_new}'...")
    if datatype_old not in struct.DATATYPES or datatype_new not in struct.DATATYPES:
        raise ValueError("Datatype does not exist")

    if os.path.exists(f"{LOCAL_DB_PATH}/{datatype_old}"):
        files = os.listdir(f"{LOCAL_DB_PATH}/{datatype_old}")
    else:
        files = []

    for file in files:
        LOG.debug(f"Mapping file {file}...")

        fp = open(f"{LOCAL_DB_PATH}/{datatype_old}/{file}")
        old_chunk_dict = ujson.load(fp)
        fp.close()

        new_chunk_dict = {}
        for tag, data in old_chunk_dict.items():
            old_nibble = struct.dict_to_nibble(data, tag, datatype_old)
            new_chunk_dict[tag] = mapping(old_nibble).to_json()

        wp = open(f"{LOCAL_DB_PATH}/{datatype_new}/{file}", "w")
        ujson.dump(new_chunk_dict, wp)
        wp.close()

    LOG.debug("Mapping complete!")

# endregion


# region Cache Functions

def cache_pop():
    """Removes the first chunk from the cache, and saves it if it has been updated."""
    chunk = cache.popleft()
    chunk_map[chunk.datatype][chunk.hsh] = None

    if chunk.updated:
        LOG.debug("Saving cache.")
        path = f"{LOCAL_DB_PATH}/{chunk.datatype}"
        os.makedirs(path, exist_ok=True)
        with open(f"{path}/{chunk.hsh}.json", "w") as fp:
            ujson.dump({tag: nib.to_json() for tag, nib in chunk.nibbles.items()}, fp)
        LOG.debug(f"File {path}/{chunk.hsh}.json dumped.")
    del chunk


def cache_clear():
    """Clears out the cache, saving any updated chunks."""
    while len(cache):
        cache_pop()


def cache_contains(hsh: int, datatype: str) -> bool:
    """Checks if the cache contains a chunk with the given chunk hash and data type."""
    return chunk_map[datatype][hsh] is not None


def cache_get(hsh: int, datatype: str) -> struct.Chunk | None:
    """
    Returns the first chunk in the cache with the given chunk hash and data type.
    If no chunk exists, return None.
    """
    return chunk_map[datatype][hsh]

# endregion


# region Data Functions

def query_data(key: str, datatype="display", local=False) -> struct.Nibble | None:
    """
    Fetches the data associated with the given key and data type.
    :param key: the key to search for
    :param datatype: the type of the data
    :param local: whether to use the local database
    :return: the data stored with the key
    """
    ch = chunk_hash(key)
    chunk = cache_get(ch, datatype)
    if chunk is None:
        LOG.debug(f"Loading chunk {ch} (data type={datatype})...")
        chunk = load_chunk(ch, datatype, local=local)

    if key in chunk.nibbles:
        return chunk.nibbles[key]
    return None


def store_data(key: str, data: dict, datatype: str) -> bool:
    """
    Stores the given data in the database.
    :param key: the key of the data
    :param data: the data to store
    :param datatype: the type of data to store
    :return: True if the key already existed, false otherwise
    """

    nib = struct.dict_to_nibble(data, key, datatype)
    ch = chunk_hash(key)
    chunk = cache_get(ch, datatype)
    if chunk is None:
        chunk = load_chunk(ch, datatype, create_new=True, local=True)

    chunk.updated = True
    new_key = key not in chunk.nibbles
    chunk.nibbles[key] = nib
    LOG.debug(f"Saved element {key} to chunk hash {ch} successfully. Data saved: {nib} (key in cache)")

    return new_key

# endregion

