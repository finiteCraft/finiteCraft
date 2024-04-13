import itertools
import json
import time

import pymongo
import logging

import librarian
from autocrafter.Proxy import Proxy
from autocrafter.Scheduler import Scheduler
from autocrafter.tools import (perform_initial_proxy_ranking, get_many_url_proxies, ImprovedThread,
                               get_depth_of)

db = pymongo.MongoClient("mongodb://192.168.1.143:27017")


def get_db_elements():
    cols = list(db["crafts"].list_collection_names())
    return cols


librarian.init()
o_value = []
proxies: list[Proxy] = []

do_ping = True
log = logging.getLogger(name="AutoCrafter")
log.setLevel(logging.INFO)


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
    log.info("Ranking proxies...")
    perform_initial_proxy_ranking(proxies)
    log.info("done")


do_proxy_stuff()
try:
    breadcrumb = [int(i) for i in open("crafter.breadcrumb").readlines()[0].replace("\n", "").split(",")]
except:
    log.warning("Failed to read breadcrumb! Setting to 1,0...")
    breadcrumb = [1, 0]

push_to_github = True

current_counter = 0

first_loop = True
current_depth = breadcrumb[0]
slept = 0

while True:
    pick_from = get_db_elements()
    if len(pick_from) == 0:
        pick_from = ["Fire", "Water", "Wind", "Earth"]
        emojis = ["🔥", "💧", "🌬️", "🌍"]
        for i, item in enumerate(pick_from):
            col = db.get_database("crafts").get_collection(item)
            col.insert_one({"type": "info", "depth": 0, "emoji": emojis[i], "discovered": False})

    select_from = []

    combin = []
    log.info(f"generating combinations for depth {current_depth} (estimated: {len(pick_from)**2})")
    depth_cache = {}
    for item in itertools.combinations_with_replacement(pick_from, 2):
        if item[0] not in depth_cache.keys():
            depth_cache[item[0]] = get_depth_of(item[0], db)
            log.debug(f"added item to cache {len(depth_cache)+1}/{len(pick_from)}"
                      f" (item {item[0]} depth {depth_cache[item[0]]})")
        if item[1] not in depth_cache.keys():
            depth_cache[item[1]] = get_depth_of(item[1], db)
            log.debug(f"added item to cache {len(depth_cache)+1}/{len(pick_from)}"
                      f" (item {item[1]} depth {depth_cache[item[1]]})")
        depth_0 = depth_cache[item[0]]
        depth_1 = depth_cache[item[1]]
        if ((item[0] != "Nothing" and item[1] != "Nothing") and (depth_1 == current_depth - 1
                or depth_0 == current_depth - 1) and (depth_0 <= current_depth - 1 and depth_1 <= current_depth - 1)):
            combin.append(item)
    log.info("task done")
    if len(combin) == 0:
        log.error("ERROR: No combinations were generated. Resetting crafter.breadcrumb...")
        breadcrumb = [0, 1]
        current_depth = 0
        continue
    if first_loop:
        first_loop = False
        combin = combin[breadcrumb[1]:]
        finished_additive = breadcrumb[1]
    else:
        finished_additive = 0
    s = Scheduler(combin, proxies, name="Julian")
    s_thread = ImprovedThread(target=s.run)

    s_thread.start()
    while s_thread.is_alive():
        time.sleep(1)
        completed_crafts = s.progress["completed"] + s.progress["skipped"] + finished_additive
        with open("crafter.breadcrumb", "w") as ch_breadfile:
            ch_breadfile.truncate(0)
            ch_breadfile.write(str(current_depth) + "," + str(completed_crafts))
        slept += 1
        alive = 0
        for proxy in proxies:
            if proxy.disabled_until == 0:
                alive += 1
        if alive / len(proxies) < 0.1:  # If 90% of proxies die, regenerate them
            do_proxy_stuff()
            s.proxies = proxies
            log.warning(f"Proxies have been regenerated ({alive} alive out of {len(proxies)} proxies)")
        if slept % 6 == 0 and push_to_github:
            librarian.remove_directories()
            raw_database = {}
            for col in db.get_database("crafts").list_collection_names():
                raw_database.update({col: list(db["crafts"][col].find({}, {"_id": 0}))})
            stats = {"unique": len(raw_database),
                     "mongodb": db["crafts"].command("dbstats")}
            json.dump(stats, open(librarian.LOCAL_DB_PATH + "/stats.json", "w+"))
            for element in raw_database:
                data = raw_database[element]
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
                librarian.store_data(element, {"discovered": info["discovered"], "emoji": info["emoji"],
                                               "depth": info["depth"]}, "display", local=True)
                pre = [i[0] for i in crafted_by if i[1]]
                post = [i[0] for i in crafted_by if not i[1]]
                librarian.store_data(element, {"pre": pre, "post": post, "depth": info["depth"]}, "search", local=True)
            librarian.cache_clear()
            librarian.update_remote()

    current_depth += 1
