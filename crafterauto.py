import itertools
import json
import time

import pymongo

import librarian
from autocrafter.Proxy import Proxy
from autocrafter.Scheduler import Scheduler
from autocrafter.tools import (parse_crafts_into_tree, perform_initial_proxy_ranking, get_url_proxies, ImprovedThread,
                               get_depth_of)

db = pymongo.MongoClient("mongodb://127.0.0.1")


def get_db_elements():
    cols = list(db["crafts"].list_collection_names())
    return cols




o_value = []
proxies: list[Proxy] = []

do_ping = True
def do_proxy_stuff():
    global proxies
    raw_proxies = get_url_proxies(
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt")

    print(f"Retrieved {len(raw_proxies)} proxies")
    for i, p in enumerate(raw_proxies):
        px = Proxy(ip=p['ip'], port=p['port'], protocol=p['protocol'])
        proxies.append(px)
    print("Ranking proxies...")
    perform_initial_proxy_ranking(proxies)
    print("done")

do_proxy_stuff()
try:
    breadcrumb = [int(i) for i in open("crafter.breadcrumb").readlines()[0].replace("\n", "").split(",")]
except Exception as exc:
    print("Failed to read breadcrumb! Setting to 1,0...")
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
    print("generating combinations for depth", current_depth)
    for item in itertools.combinations_with_replacement(pick_from, 2):
        if (item[0] != "Nothing" and item[1] != "Nothing") and get_depth_of(item[0], db) == current_depth - 1 or get_depth_of(item[1], db) == current_depth - 1:
            combin.append(item)
    print("task done")
    if len(combin) == 0:
        print("ERROR: No combinations were generated. Please reset crafter.breadcrumb.")
        break
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
            ch_breadfile.write(str(current_depth)+"," + str(completed_crafts))
        slept += 1
        alive = 0
        for proxy in proxies:
            if proxy.disabled_until == 0:
                alive += 1
        if alive / len(proxies) < 0.1:  # If 90% of proxies die, regenerate them
            do_proxy_stuff()
            s.proxies = proxies
            print(f"Proxies have been regenerated ({alive} alive out of {len(proxies)} proxies)")
        if slept % 600 == 0 and push_to_github:
            librarian.remove_directories()
            raw_database = {}

            for col in db.get_database("crafts").list_collection_names():
                raw_database.update({col: list(db["crafts"][col].find({}, {"_id": 0}))})
            stats = {"unique": len(raw_database), "recipes": 0, "tyler": 1, "julian": 1, "mongodb": db["crafts"].command("dbstats")}
            json.dump(stats, open(librarian.LOCAL_DB_PATH+"/stats.json", "w+"))
            for element in raw_database:
                data = raw_database[element]
                info = {}
                crafted_by = []
                for document in data:
                    if document["type"] == "crafts":
                        stats["recipes"] += 1
                    if document["type"] == "crafted_by":
                        crafted_by.append(document["craft"])
                    elif document["type"] == "info":
                        del document["type"]
                        info = document
                if len(list(info.keys())) == 0:
                    print(element)
                librarian.store_data(element, {"discovered": info["discovered"], "emoji": info["emoji"],
                                               "depth": info["depth"]}, "display", local=True)
                librarian.store_data(element, {"crafted_by": crafted_by, "depth": info["depth"]}, "search", local=True)
            librarian.save_cache()
            librarian.update_remote()



    current_depth += 1
