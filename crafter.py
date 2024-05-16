import sys
import os
import shutil
from crafterbackend.constants import *
import pymongo
import logging
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, AutoReconnect, NetworkTimeout
import argparse
from crafterbackend.Proxy import Proxy
from crafterbackend.Scheduler import Scheduler
from crafterbackend.tools import (perform_initial_proxy_ranking, get_many_url_proxies, ImprovedThread)

CONNECTION_STRING = "mongodb://192.168.1.143:27017"

parser = argparse.ArgumentParser(description="The crafter for https://github.com/finitecraft/api. "
                                             "This is a backend service and should be run using Docker Compose.")

parser.add_argument("--uri", help="The MongoDB URI (connection string)", default=CONNECTION_STRING,
                    type=str)
parser.add_argument("-w", '--workers', help="The number of Workers to use concurrently"
                                            " (maximum CPS = workers * 5)", type=int,
                    default=10)
parser.add_argument("--disable-proxy-rank", help="Disable the proxy ranking (speeds up start time but"
                                                 " slows down the program recognizing the usefulness of proxies).",
                    action="store_true")

parser.add_argument("-p", "--push-delay", help="The delay between pushing to GitHub (seconds)", type=int,
                    default=600)

log_levels = ["debug", "info", "warning", "error", "critical"]
parser.add_argument("-l", "--log-level", help="The log level to use for the program.", choices=log_levels,
                    default="info")

parser.add_argument("--silence-workers",
                    help="Only print scheduler logs once the main loop has started", action="store_true")

transcode_log_levels = {"debug": logging.DEBUG, "info": logging.INFO, "warning": logging.WARNING,
                        "error": logging.ERROR,
                        "critical": logging.CRITICAL}

args = parser.parse_args()

CONNECTION_STRING = args.uri
global_log_level = transcode_log_levels[args.log_level]
db = pymongo.MongoClient(CONNECTION_STRING, serverSelectionTimeoutMS=2000, connectTimeoutMS=1000, socketTimeoutMS=1000)


def wait_for_mongodb_connection(database: pymongo.MongoClient):
    try:
        # The ismaster command is cheap and does not require auth.
        database.admin.command('ismaster')
    except (NetworkTimeout, ConnectionFailure, ServerSelectionTimeoutError, AutoReconnect):
        log.error(f"Disconnected from MongoDB! Waiting to reconnect now... (uri={CONNECTION_STRING})")
        while True:
            try:
                log.debug("Attempting to reconnect to MongoDB...")
                database = pymongo.MongoClient(CONNECTION_STRING, serverSelectionTimeoutMS=2000,
                                               connectTimeoutMS=1000, socketTimeoutMS=1000)
                database.admin.command('ismaster')
            except (NetworkTimeout, ConnectionFailure, ServerSelectionTimeoutError, AutoReconnect):
                log.warning(f"Failed to reconnect to MongoDB! (uri={CONNECTION_STRING})")
                continue
            log.info("Successfully reconnected to MongoDB!")
            break


def get_db_elements():
    cols = list(db[DATABASE].list_collection_names())
    return cols


# librarian.set_logging(log_level=global_log_level)  # Initialize Librarian with our log level

proxies: list[Proxy] = []  # A list of all the Proxies currently being used
last_depth_count = {}  # A dictionary of the format {<depth>: <number of elements in database with that depth>}.
# Updated by update_librarian()

# Initalize logging
log = logging.getLogger(name="AutoCrafter")
log.setLevel(global_log_level)

wait_for_mongodb_connection(db)  # Ensure we are connected to MongoDB before we proceed


def prepare_proxies():
    """
    Get and rank proxies from 4 different vetted sources and rank them according to their speed
    """
    global proxies
    raw_proxies = get_many_url_proxies(
        {"https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt": "socks5h",
         "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/socks4.txt": "socks4h",
         "https://raw.githubusercontent.com/elliottophellia/yakumo/master/results/socks5/global/socks5_checked.txt": "socks5h",
         "https://raw.githubusercontent.com/prxchk/proxy-list/main/socks5.txt": "socks5h"})

    log.info(f"Retrieved {len(raw_proxies)} proxies")
    for i, p in enumerate(raw_proxies):
        px = Proxy(ip=p['ip'], port=p['port'], protocol=p['protocol'])
        proxies.append(px)
    if not args.disable_proxy_rank:
        log.info("Ranking proxies...")
        perform_initial_proxy_ranking(proxies)
        log.info("done")


prepare_proxies()
push_to_github = True
current_counter = 0
first_loop = True
current_depth = None
slept = 0


def combinatorial(x: int):
    """
    Generate a combinatorial number for a given depth. This formula works like xP2 + x (combinatorial pick).
    """
    return ((x * (x - 1)) / 2) + x


def generate_combinations(new_depth: int):
    """
    Use the depthfiles to generate the combinations as a generator.
    Guarantees a combination every inner loop
    """
    try:
        this_depthfile = open(f"{DEPTHFILE_STORAGE}/{new_depth - 1}")
        for prev_depth in range(new_depth - 1):
            older_depthfile = open(f"{DEPTHFILE_STORAGE}/{prev_depth}")
            for l1 in older_depthfile:
                e1 = l1[:-1]
                for l2 in this_depthfile:
                    e2 = l2[:-1]
                    yield (e1, e2), prev_depth, new_depth - 1
                this_depthfile.seek(0)
            older_depthfile.close()

        # this_depthfile pointer should already be reset from previous loop
        while True:
            l1 = this_depthfile.readline()
            if len(l1) == 0:
                break  # Reached EOF
            fp_loc = this_depthfile.tell()  # Save file pointer location to come back to
            e1 = l1[:-1]
            yield (e1, e1), new_depth - 1, new_depth - 1
            for l2 in this_depthfile:  # Abuse file pointer to only loop through the succeeding elements
                e2 = l2[:-1]
                yield (e1, e2), new_depth - 1, new_depth - 1
            this_depthfile.seek(fp_loc)  # Reset file pointer to where we started

        this_depthfile.close()
    except FileNotFoundError:
        raise ValueError(f"Cannot calculate combinations for depth {new_depth}. "
                         f"Do not have elements of previous depths")


if __name__ == "__main__":  # Mainloop
    while True:
        read_depth = 0
        last_depth_count = {}
        while True:
            try:
                with open(f"{DEPTHFILE_STORAGE}/{read_depth}.size", "r") as f:
                    last_depth_count[read_depth] = int(f.readline())
            except FileNotFoundError:  # No more depthfiles to read
                break
            read_depth += 1
        log.info(f"Current depths according to depthfiles: {last_depth_count}")
        if current_depth is None:
            current_depth = max(last_depth_count.keys(), default=1)  # Figure out the depth we are currently on
        if last_depth_count == {}:  # If the database is empty,
            # populate last_depth_count with starter elements and empty depth 1 to prevent a crash
            emojis = ["🔥", "💧", "🌬️", "🌍"]
            for element, item in enumerate(STARTING_ELEMENTS.keys()):
                col = db.get_database(DATABASE).get_collection(item)
                col.insert_one({TYPE_NAME: INFO_PACKET_NAME, DEPTH_NAME: 0,
                                EMOJI_NAME: emojis[element], DISCOVERED_NAME: False})
            try:
                os.makedirs(DEPTHFILE_STORAGE)
            except FileExistsError:
                log.info("Depthfolder exists, continuing from there")
                pass
            for filename in os.listdir(DEPTHFILE_STORAGE):
                file_path = os.path.join(DEPTHFILE_STORAGE, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    log.warning('Failed to delete %s. Reason: %s' % (file_path, e))

            with open(f"{DEPTHFILE_STORAGE}/0", "a") as zerofile:
                zerofile.write("\n".join(STARTING_ELEMENTS.keys())+"\n")
            with open(f"{DEPTHFILE_STORAGE}/0.size", "a") as zerosizefile:
                zerosizefile.write("4")
            last_depth_count = {0: 4, 1: 0}
        if last_depth_count == {0: 4}:  # Edge case
            current_depth = 1
            last_depth_count = {0: 4, 1: 0}

        select_from = []

        sum_of_total = sum([last_depth_count[i] for i in range(0, current_depth)])

        # The number of RECIPES in the depth (for progress bar / more efficient stop condition)
        total_crafts = int(combinatorial(sum_of_total) -
                           combinatorial(sum_of_total - last_depth_count[current_depth - 1]))

        combination_generator = generate_combinations(current_depth)
        log.info(f"generator initalized for depth {current_depth} (total crafts: {total_crafts})")
        s = Scheduler(combination_generator, total_crafts, proxies, mongo_connection_string=CONNECTION_STRING,
                      name="Julian", max_workers=args.workers, log_level=global_log_level,
                      silence_tyler=args.silence_workers)

        s_thread = ImprovedThread(target=s.run)  # Run the scheduler
        s_thread.start()
        try:
            while s_thread.is_alive():  # Just kinda sit here until the thread is done
                wait_for_mongodb_connection(db)
                slept += 1

                # Determine the total number of proxies currently alive, in case we need to start over.
                alive = 0
                for proxy in proxies:
                    if proxy.disabled_until == 0:
                        alive += 1
                if alive / len(proxies) < 0.1:  # If 90% of proxies die, regenerate them
                    prepare_proxies()
                    s.proxies = proxies
                    log.warning(f"Proxies have been regenerated ({alive} alive out of {len(proxies)} proxies)")
        except KeyboardInterrupt:  # Catch manual quit
            log.info("Exiting!")
            sys.exit(0)
        current_depth += 1
