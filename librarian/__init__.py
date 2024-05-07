import ujson
import os
import logging
from collections.abc import Callable

import requests
from git import Repo
import shutil
from collections import deque

import librarian.structures as struct

# Initialization
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

    # Some file-wide constants
    CHUNK_CAPACITY = 1000    # The max size of a chunk
    CACHE_CAPACITY = 100     # The max number of chunks allowed to be simultaneously loaded
    DEFAULT_NUM_CHUNKS = 64  # Default number of chunks in the library

    chunk_map: dict[str, list[struct.Chunk | None]] = dict()  # A dictionary-array containing pointers to all loaded chunks
    num_chunks: int = 0  # Number of chunks in the database
    cache: deque[struct.Chunk] = deque()  # A queue of the loaded chunks. Used to keep track of order added

    def update_local():
        """Pulls from the online database to the library"""
        global chunk_map
        global cache
        global num_chunks

        LOG.info("Beginning pull process...")
        LOG.debug("Pulling changes...")
        origin = REPO.remote(name='origin')
        origin.fetch()
        REPO.git.reset('--hard', 'HEAD')
        LOG.info("Pull attempt done.")
        REPO.index.reset()  # Do a reset here to only track files that still exist
        REPO.index.add("**")

        # region Load the data from settings.json
        if os.path.exists(f"{LOCAL_DB_PATH}/settings.json"):
            with open(f"{LOCAL_DB_PATH}/settings.json", "r") as sp:
                settings = ujson.load(sp)
                num_chunks = settings["num_chunks"]
                struct.BUNDLE_TYPES = {btype: set(attr) for btype, attr in settings["bundle_types"].items()}

        else:
            num_chunks = DEFAULT_NUM_CHUNKS
            struct.BUNDLE_TYPES = {}
            with open(f"{LOCAL_DB_PATH}/settings.json", "w") as sp:
                settings = {"num_chunks": DEFAULT_NUM_CHUNKS, "bundle_types": {}}
                ujson.dump(settings, sp)
        # endregion

        # Initialize the chunk map
        chunk_map = {dt: [None for _ in range(num_chunks)] for dt in struct.BUNDLE_TYPES}
        chunk_map[struct.GENERAL_BUNDLE] = [None for _ in range(num_chunks)]
        cache = deque()

    update_local()

    LOG.info("Loaded Librarian.")


# region Basic Utilities

def set_logging(log_level: int):
    LOG.setLevel(log_level)


def save_settings():
    LOG.debug("Saving settings...")
    with open(f"{LOCAL_DB_PATH}/settings.json", "w") as sp:

        settings = {"num_chunks": num_chunks, "bundle_types": {dt: list(attr) for dt, attr in struct.BUNDLE_TYPES.items()}}
        ujson.dump(settings, sp, indent=4)
    LOG.debug("Settings saved.")


def reset_database():
    """
    Clears existing data in the database and restructures it from scratch.
    Only affects bundle folders and settings file.
    """
    LOG.debug("Clearing old database, say goodbye lol")
    if os.path.exists(f"{LOCAL_DB_PATH}/{struct.GENERAL_BUNDLE}"):
        shutil.rmtree(f"{LOCAL_DB_PATH}/{struct.GENERAL_BUNDLE}")
    for dir_name in struct.BUNDLE_TYPES:
        if os.path.exists(f"{LOCAL_DB_PATH}/{dir_name}"):
            shutil.rmtree(f"{LOCAL_DB_PATH}/{dir_name}")

    LOG.debug("Recreating database from scratch")

    os.makedirs(f"{LOCAL_DB_PATH}/{struct.GENERAL_BUNDLE}")
    for btype in struct.BUNDLE_TYPES:
        os.makedirs(f"{LOCAL_DB_PATH}/{btype}")

    save_settings()
            

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


def load_chunk(ch: int, bundle_type=struct.GENERAL_BUNDLE, create_new=False, local=False) -> struct.Chunk:
    """
    Loads the chunk with the given chunk hash into the cache.
    Raises an IndexError if chunk does not exist.
    :param ch: the chunk hash
    :param bundle_type: the type of chunk to load
    :param create_new: whether the function is allowed to create new chunks
    :param local: whether to search for a local version of the chunk
    """
    global cache
    global chunk_map

    rel_path = f"{bundle_type}/{ch}.json"

    if len(cache) >= CACHE_CAPACITY:
        cache_pop()

    LOG.debug(f"Retrieving chunk {ch} (data type={bundle_type})...")

    if local:  # Searching in local database
        if os.path.exists(f"{LOCAL_DB_PATH}/{rel_path}"):
            with open(f"{LOCAL_DB_PATH}/{rel_path}") as fp:
                data = ujson.load(fp)
        elif create_new:
            data = {}
        else:
            raise IndexError(f"Attempted to access non-existent chunk: {bundle_type}/{ch}.json")

    else:  # Searching in remote database
        response = SESSION.get(f"{DB_URL}/{rel_path}")
        if response.status_code != 404:
            data = ujson.loads(response.content)
        elif create_new:
            LOG.debug(f"Chunk {ch} (data type={bundle_type}) does not exist! Creating new chunk...")
            data = {}
        else:
            raise IndexError(f"Attempted to access non-existent chunk: {bundle_type}/{ch}.json")

    chunk = struct.Chunk(ch, bundle_type, {tag: struct.dict_to_nibble(d, tag, bundle_type) for tag, d in data.items()})
    chunk_map[bundle_type][ch] = chunk  # Save the chunk here
    cache.append(chunk)    # Still add it to queue to keep track of order added
    LOG.debug(f"Chunk {ch} (data type={bundle_type}) successfully loaded!")
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
    for t in struct.BUNDLE_TYPES:
        os.makedirs(f"{LOCAL_DB_PATH}/temp/{t}", exist_ok=True)

    if len(struct.BUNDLE_TYPES) and os.path.exists(f"{LOCAL_DB_PATH}/{list(struct.BUNDLE_TYPES.keys())[0]}"):
        files = os.listdir(f"{LOCAL_DB_PATH}/{list(struct.BUNDLE_TYPES.keys())[0]}")  # get all existing files
    else:
        files = []
    num_chunks = new_num_chunks
    chunk_map = {dt: [None for _ in range(num_chunks)] for dt in struct.BUNDLE_TYPES}

    for f in files:
        LOG.debug(f"Rehashing file: {f}")
        for t in struct.BUNDLE_TYPES:
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
    reset_database()
    LOG.debug("Moving new files out of temp dir...")
    for t in struct.BUNDLE_TYPES:
        shutil.move(f"{LOCAL_DB_PATH}/temp/{t}", f"{LOCAL_DB_PATH}/{t}")

    LOG.debug("Removing temp dir...")
    shutil.rmtree(f"{LOCAL_DB_PATH}/temp")


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
        
# endregion


# region Datatype Interaction

def get_bundle_types() -> dict[str, set[str]]:
    return struct.BUNDLE_TYPES


def declare_new_bundle_type(bundle_type: str, attributes: set[str]):
    """Declares a new bundle_type for use. Give a set of attributes for it to have."""
    if bundle_type in struct.BUNDLE_TYPES:
        raise ValueError(f"Datatype \"{bundle_type}\" already exists")

    # Set up bundle type
    struct.BUNDLE_TYPES[bundle_type] = attributes.copy()
    os.makedirs(f"{LOCAL_DB_PATH}/{bundle_type}")
    chunk_map[bundle_type] = [None for _ in range(num_chunks)]
    save_settings()

    # Pre-compute new bundles
    for chunkfile in os.listdir(f"{LOCAL_DB_PATH}/{struct.GENERAL_BUNDLE}"):
        fp = open(f"{LOCAL_DB_PATH}/{struct.GENERAL_BUNDLE}/{chunkfile}")
        general_data: dict[str, dict] = ujson.load(fp)

        wp = open(f"{LOCAL_DB_PATH}/{bundle_type}/{chunkfile}", "w")
        filtered_data = {tag: dict() for tag, data in general_data.items()}

        for tag, data in general_data.items():  # For each tag
            if len(attributes.difference(data.keys())) > 0:  # If it is missing an attribute required by new bundle type
                LOG.warning(f"Tag '{tag}' missing attributes for new bundle type '{bundle_type}'")

            for attr, value in data.items(): # For each attribute
                if attr in attributes:  # If it is a required attribute
                    filtered_data[tag][attr] = value  # Store it

        ujson.dump(filtered_data, wp)


def remove_bundle_type(bundle_type: str) -> bool:
    """Removes a bundle_type and all data of that type. Returns if bundle_type was removed successfully."""
    if bundle_type not in struct.BUNDLE_TYPES:
        return False

    struct.BUNDLE_TYPES.pop(bundle_type)
    shutil.rmtree(f"{LOCAL_DB_PATH}/{bundle_type}")
    save_settings()
    return True


def map_data(bundle_type_old: str, bundle_type_new: str, mapping: Callable[[struct.Nibble], struct.Nibble]) -> None:
    """
    Maps all data from one bundle_type to the new bundle_type using the provided mapping function.
    Be aware that this will overwrite all the data in the new bundle_type,
    so it's best to use this when creating new bundle_types, but stay away from it normally.
    :param bundle_type_old: the bundle_type to map from
    :param bundle_type_new: the bundle_type to map to
    :param mapping: the custom mapping function
    :return:
    """
    LOG.debug(f"Mapping data from '{bundle_type_old}' to '{bundle_type_new}'...")
    if bundle_type_old not in struct.BUNDLE_TYPES or bundle_type_new not in struct.BUNDLE_TYPES:
        raise ValueError("Datatype does not exist")

    if os.path.exists(f"{LOCAL_DB_PATH}/{bundle_type_old}"):
        files = os.listdir(f"{LOCAL_DB_PATH}/{bundle_type_old}")
    else:
        files = []

    for file in files:
        LOG.debug(f"Mapping file {file}...")

        fp = open(f"{LOCAL_DB_PATH}/{bundle_type_old}/{file}")
        old_chunk_dict = ujson.load(fp)
        fp.close()

        new_chunk_dict = {}
        for tag, data in old_chunk_dict.items():
            old_nibble = struct.dict_to_nibble(data, tag, bundle_type_old)
            new_chunk_dict[tag] = mapping(old_nibble).to_json()

        wp = open(f"{LOCAL_DB_PATH}/{bundle_type_new}/{file}", "w")
        ujson.dump(new_chunk_dict, wp)
        wp.close()

    LOG.debug("Mapping complete!")

# endregion


# region Cache Functions

def cache_pop():
    """Removes the first chunk from the cache, and saves it if it has been updated."""
    chunk = cache.popleft()
    chunk_map[chunk.bundle_type][chunk.hsh] = None

    if chunk.updated:
        LOG.debug("Saving cache.")
        path = f"{LOCAL_DB_PATH}/{chunk.bundle_type}"
        os.makedirs(path, exist_ok=True)
        with open(f"{path}/{chunk.hsh}.json", "w") as fp:
            ujson.dump({tag: nib.to_json() for tag, nib in chunk.nibbles.items()}, fp)
        LOG.debug(f"File {path}/{chunk.hsh}.json dumped.")
    del chunk


def cache_clear():
    """Clears out the cache, saving any updated chunks."""
    while len(cache):
        cache_pop()


def cache_contains(hsh: int, bundle_type: str) -> bool:
    """Checks if the cache contains a chunk with the given chunk hash and data type."""
    return chunk_map[bundle_type][hsh] is not None


def cache_get(hsh: int, bundle_type: str) -> struct.Chunk | None:
    """
    Returns the first chunk in the cache with the given chunk hash and data type.
    If no chunk exists, return None.
    """
    return chunk_map[bundle_type][hsh]

# endregion


# region Data Functions

def query_data(key: str, bundle_type=struct.GENERAL_BUNDLE, local=False) -> struct.Nibble | None:
    """
    Fetches the data associated with the given key and data type.
    :param key: the key to search for
    :param bundle_type: the type of the data
    :param local: whether to use the local database
    :return: the data stored with the key
    """
    ch = chunk_hash(key)
    chunk = cache_get(ch, bundle_type)
    if chunk is None:
        LOG.debug(f"Loading chunk {ch} (data type={bundle_type})...")
        chunk = load_chunk(ch, bundle_type, local=local)

    if key in chunk.nibbles:
        return chunk.nibbles[key]
    return None


def store_data(tag: str, data: dict, allow_missing_attributes=False) -> None:
    """
    Stores the given data in the database.
    This overwrites everything that was previously associated with this tag.
    :param tag: the tag of the data
    :param data: the data to store
    :param allow_missing_attributes: boolean flag to control whether warnings are raised for missing attributes
    """

    ch = chunk_hash(tag)
    chunk = cache_get(ch, struct.GENERAL_BUNDLE)
    if chunk is None:
        chunk = load_chunk(ch, struct.GENERAL_BUNDLE, create_new=True, local=True)

    # Update the general dataset
    chunk.updated = True
    chunk.nibbles[tag] = struct.dict_to_nibble(data, tag, struct.GENERAL_BUNDLE)

    # Update the pre-computed bundles
    for btype, attributes in struct.BUNDLE_TYPES.items():

        matching_attributes = attributes.intersection(data.keys())
        missing_attributes = attributes.difference(data.keys())
        if not allow_missing_attributes and len(missing_attributes) > 0:  # Warn about missing required attributes
            LOG.warning(f"Attempting to store data for tag '{tag}', but missing require data for Bundle Type '{btype}'")
        if len(matching_attributes) <= 0: # No matching attributes, skip to next bundle type
            continue

        chunk = cache_get(ch, btype)  # Load chunk for bundle type
        if chunk is None:
            chunk = load_chunk(ch, btype, create_new=True, local=True)

        chunk.updated = True
        if tag not in chunk.nibbles:
            chunk.nibbles[tag] = struct.Nibble(tag, btype)

        nibble = chunk.nibbles[tag]
        for attr in matching_attributes:  # Update associated attributes
            nibble[attr] = data[attr]



    LOG.debug(f"Saved element {tag} to chunk hash {ch} successfully.")


def update_data(tag: str, data: dict) -> None:
    """
    Updates the data associated with the tag by adding on the data given.
    This does not overwrite what already existed unless explicitly specified.
    Note that this expects some data to already exist in the database.
    :param tag: the tag of the data
    :param data: the data to store
    """

    ch = chunk_hash(tag)
    chunk = cache_get(ch, struct.GENERAL_BUNDLE)
    if chunk is None:
        chunk = load_chunk(ch, struct.GENERAL_BUNDLE, create_new=True, local=True)

    # Update the general dataset
    if tag not in chunk.nibbles:
        raise ValueError(f"Tried to update non-existent data for tag '{tag}'")

    chunk.nibbles[tag] = struct.dict_to_nibble(data, tag, struct.GENERAL_BUNDLE)
    chunk.updated = True

    # Update the pre-computed bundles
    for btype, attributes in struct.BUNDLE_TYPES.items():

        matching_attributes = attributes.intersection(data.keys())
        # don't need to do the missing attribute check since we expect the data to already exist
        if len(matching_attributes) <= 0: # No matching attributes, skip to next bundle type
            continue

        chunk = cache_get(ch, btype)  # Load chunk for bundle type
        if chunk is None:
            chunk = load_chunk(ch, btype, create_new=True, local=True)

        chunk.updated = True
        if tag not in chunk.nibbles:
            chunk.nibbles[tag] = struct.Nibble(tag, btype)

        nibble = chunk.nibbles[tag]
        for attr in matching_attributes:  # Update associated attributes
            nibble[attr] = data[attr]

    LOG.debug(f"Saved element {tag} to chunk hash {ch} successfully.")

# endregion

