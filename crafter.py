import itertools
import json
import time
import pymongo
import logging
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, AutoReconnect, NetworkTimeout
import argparse
import librarian
from crafterbackend.Proxy import Proxy
from crafterbackend.Scheduler import Scheduler
from crafterbackend.tools import (perform_initial_proxy_ranking, get_many_url_proxies, ImprovedThread,
                                  get_depth_of)

CONNECTION_STRING = "mongodb://192.168.1.143:27017"

parser = argparse.ArgumentParser(description="The crafter for https://github.com/finitecraft/api. "
                                             "This is a backend service and should be run using Docker Compose.")

parser.add_argument("--uri", help="The MongoDB URI (connection string)", default=CONNECTION_STRING,
                    type=str)
parser.add_argument("-w", '--workers', help="The number of Workers to use concurrently", type=int,
                    default=5)
parser.add_argument("--disable-proxy-rank", help="Disable the proxy ranking (speeds up start time but"
                                                 " slows down the program recognizing the usefulness of proxies).",
                    action="store_true")

log_levels = ["debug", "info", "warning", "error", "critical"]
parser.add_argument("-l", "--log-level", help="The log level to use for the program.", choices=log_levels,
                    default="info")

transcode_log_levels = {"debug": logging.DEBUG, "info": logging.INFO, "warning": logging.WARNING,
                        "error": logging.ERROR,
                        "critical": logging.CRITICAL}

args = parser.parse_args()

CONNECTION_STRING = args.uri
global_log_level = transcode_log_levels[args.log_level]
db = pymongo.MongoClient(CONNECTION_STRING, serverSelectionTimeoutMS=2000, connectTimeoutMS=1000, socketTimeoutMS=1000)


def check_mongodb_connection(database: pymongo.MongoClient):
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
                log.info(f"Failed to reconnect to MongoDB! (uri={CONNECTION_STRING})")
                continue
            log.info("Succesfully reconnected to MongoDB!")
            break


def get_db_elements():
    cols = list(db["crafts"].list_collection_names())
    return cols


librarian.init(log_level=global_log_level)
o_value = []
proxies: list[Proxy] = []
last_depth_count = {}
do_ping = True
log = logging.getLogger(name="AutoCrafter")
log.setLevel(global_log_level)

check_mongodb_connection(db)


def update_librarian(push=True):
    global last_depth_count
    log.info(f"Running update_librarian (push={push})")
    start = time.time()
    last_depth_count = {}
    raw_database = {}
    collection_names = db.get_database("crafts").list_collection_names()
    for i, collection in enumerate(collection_names):
        raw_database.update({collection: list(db["crafts"][collection].find({}, {"_id": 0}))})
    stats = {"unique": len(raw_database),
             "mongodb": db["crafts"].command("dbstats")}
    json.dump(stats, open(librarian.LOCAL_DB_PATH + "/stats.json", "w+"))
    for i, element_key in enumerate(raw_database):
        data = raw_database[element_key]
        info = {}
        crafted_by = []
        for document in data:
            # Don't need this, could readd later?
            # if document["type"] == "crafts":
            #     stats["recipes"] += 1
            if document["type"] == "crafted_by":
                crafted_by.append([document["craft"], document["predepth"], document["recursive"]])
            elif document["type"] == "info":
                del document["type"]
                info = document
        if element_key != "Nothing":  # Don't count null craft
            if info["depth"] not in last_depth_count.keys():
                last_depth_count[info["depth"]] = 1
            else:
                last_depth_count[info["depth"]] += 1
        librarian.store_data(element_key, {"discovered": info["discovered"], "emoji": info["emoji"],
                                           "depth": info["depth"]}, "display")
        pre = [i[0] for i in crafted_by if i[1]]
        post = [i[0] for i in crafted_by if not i[1]]
        librarian.store_data(element_key, {"pre": pre, "post": post, "depth": info["depth"]}, "search")
    librarian.cache_clear()
    if push:
        librarian.update_remote()
    log.info(f"Done running update_librarian (push={push}, elapsed={round(time.time()-start, 2)})")


def do_proxy_stuff():
    global proxies
    raw_proxies = get_many_url_proxies(
        ["https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt",
         "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/socks5.txt",
         "https://raw.githubusercontent.com/elliottophellia/yakumo/master/results/socks5/global/socks5_checked.txt",
         "https://raw.githubusercontent.com/prxchk/proxy-list/main/socks5.txt"])

    log.info(f"Retrieved {len(raw_proxies)} proxies")
    for i, p in enumerate(raw_proxies):
        px = Proxy(ip=p['ip'], port=p['port'], protocol=p['protocol'])
        proxies.append(px)
    if not args.disable_proxy_rank:
        log.info("Ranking proxies...")
        perform_initial_proxy_ranking(proxies)
        log.info("done")


do_proxy_stuff()

push_to_github = True

current_counter = 0

first_loop = True
current_depth = None
slept = 0


def combinatorial(x: int):
    return ((x * (x-1)) / 2) + x


def generate_combinations(elements: list[str], depth: int):
    try:
        elements.remove("Nothing")  # Remove null case
    except ValueError:
        pass
    for craft in itertools.combinations_with_replacement(elements, 2):
        while True:
            try:
                depth_0 = get_depth_of(craft[0], db)
                depth_1 = get_depth_of(craft[1], db)
            except (NetworkTimeout, ServerSelectionTimeoutError, AutoReconnect, ConnectionFailure):
                check_mongodb_connection(db)
                continue
            break
        if (depth_0 == depth or depth_1 == depth) and (depth_1 <= depth and depth_0 <= depth):
            yield craft, depth_0, depth_1


def generate_combinations_new(new_depth: int):
    this_depthfile = open(f"data/depth/{new_depth - 1}")
    for prev_depth in range(new_depth - 1):
        older_depthfile = open(f"data/depth/{prev_depth}")
        for l1 in older_depthfile:
            e1 = l1[:-1]
            for l2 in this_depthfile:
                e2 = l2[:-1]
                yield (e1, e2), prev_depth, new_depth - 1
            this_depthfile.seek(0)
                # print(first_element, second_element, depth-1, previous_depth)
                # yield (first_element[:-1], second_element[:-1]), depth-1, previous_depth
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


# while True:
#     # pick_from = get_db_elements()
#     update_librarian(push=False)
#
#     # if len(pick_from) == 0:
#     #     pick_from = ["Fire", "Water", "Wind", "Earth"]
#     #     emojis = ["🔥", "💧", "🌬️", "🌍"]
#     #     for element, item in enumerate(pick_from):
#     #         col = db.get_database("crafts").get_collection(item)
#     #         col.insert_one({"type": "info", "depth": 0, "emoji": emojis[element], "discovered": False})
#     #     last_depth_count = {0: 4, 1: 0}
#     # if last_depth_count == {0: 4}:
#     #     last_depth_count = {0: 4, 1: 0}
#     if current_depth is None:
#         current_depth = max(last_depth_count.keys(), default=1)
#     if last_depth_count == {}:
#         last_depth_count = {0: 4, 1: 0}
#     print(current_depth, last_depth_count)
#
#     select_from = []
#     sum_of_total = sum([last_depth_count[i] for i in range(0, current_depth)])
#     total_crafts = int(combinatorial(sum_of_total) - combinatorial(sum_of_total - last_depth_count[current_depth - 1]))
#     log.info(f"generating combinations for depth {current_depth} (total crafts: {total_crafts})")
#     depth_cache = {}
#     combin = generate_combinations_new(current_depth)
#     log.info("task done")
#     s = Scheduler(combin, total_crafts, proxies, mongo_connection_string=CONNECTION_STRING, name="Julian",
#                   max_workers=args.workers,
#                   log_level=global_log_level)
#     s_thread = ImprovedThread(target=s.run, daemon=True)
#
#     s_thread.start()
#     while s_thread.is_alive():
#         time.sleep(1)
#         check_mongodb_connection(db)
#         completed_crafts = s.progress["completed"] + s.progress["skipped"]
#         slept += 1
#         alive = 0
#         for proxy in proxies:
#             if proxy.disabled_until == 0:
#                 alive += 1
#         if alive / len(proxies) < 0.1:  # If 90% of proxies die, regenerate them
#             do_proxy_stuff()
#             s.proxies = proxies
#             log.warning(f"Proxies have been regenerated ({alive} alive out of {len(proxies)} proxies)")
#         if slept % 600 == 0 and push_to_github:
#             update_librarian(push=True)
#
#     current_depth += 1
