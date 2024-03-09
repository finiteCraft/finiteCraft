import json
import subprocess
import time
import librarian
import pymongo
import itertools
from autocrafter.Proxy import Proxy
from autocrafter.Scheduler import Scheduler
from autocrafter.tools import parse_crafts_into_tree, perform_initial_proxy_ranking, get_url_proxies, ImprovedThread

db = pymongo.MongoClient("mongodb://127.0.0.1")


def get_db_elements():
    cols = list(db["crafts"].list_collection_names())
    return cols




raw_proxies = get_url_proxies(
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt")


print(f"Retrieved {len(raw_proxies)} proxies")

o_value = []
proxies: list[Proxy] = []

do_ping = True


for i, p in enumerate(raw_proxies):
    px = Proxy(ip=p['ip'], port=p['port'], protocol=p['protocol'])
    proxies.append(px)
print("Ranking proxies...")

perform_initial_proxy_ranking(proxies)

current_depth = 1


while True:
    pick_from = get_db_elements()
    if len(pick_from) == 0:
        pick_from = ["Fire", "Water", "Wind", "Earth"]
        emojis = ["🔥", "💧", "🌬️", "🌍"]
        for i, item in enumerate(pick_from):
            col = db.get_database("crafts").get_collection(item)
            col.insert_one({"type": "info", "depth": 0, "emoji": emojis[i], "discovered": False})
    combin = list(itertools.combinations_with_replacement(pick_from, 2))

    s = Scheduler(combin, proxies, name="Julian")

    s_thread = ImprovedThread(target=s.run)

    s_thread.start()
    slept = 0
    print(s_thread.is_alive())
    while s_thread.is_alive():
        time.sleep(1)
        slept += 1

        if slept % 30 == 0:
            print("committing committicide")
            librarian.remove_directories()
            raw_database = {}

            for col in db.get_database("crafts").list_collection_names():
                raw_database.update({col: list(db["crafts"][col].find({}, {"_id": 0}))})
            for element in raw_database:
                data = raw_database[element]
                info = {}
                crafted_by = []
                for document in data:
                    if document["type"] == "crafted_by":
                        crafted_by.append(document["craft"])
                    elif document["type"] == "info":
                        del document["type"]
                        info = document
                librarian.store_data(element, {"discovered": info["discovered"], "emoji": info["emoji"],
                                               "depth": info["depth"]}, "display", local=True)
                librarian.store_data(element, {"crafted_by": crafted_by, "depth": info["depth"]}, "search", local=True)
            librarian.save_cache()
            librarian.update_remote()

    o = parse_crafts_into_tree(s.output_crafts)

    current_depth += 1

