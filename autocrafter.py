import json
import subprocess
import time

import pymongo
import itertools
from backend.Proxy import Proxy
from backend.Scheduler import Scheduler
from backend.tools import parse_crafts_into_tree, perform_initial_proxy_ranking, get_url_proxies, ImprovedThread
import git
from git import Repo
repo = Repo("../infinite-crafts/.git")
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
            raw_database = {}
            for col in db.get_database("crafts").list_collection_names():
                raw_database.update({col: list(db["crafts"][col].find({}, {"_id": 0}))})
            database = {}
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
                database.update({element: {"info": info, "crafted_by": crafted_by}})
            print("database loaded")
            json.dump(database, open("../infinite-crafts/all_data.json", "w"))
            print("resetting...")
            repo.index.reset()
            print("adding...")
            repo.index.add(["all_data.json"])
            print("committing")
            repo.index.commit("Updated data")
            print("lloading")
            origin = repo.remote(name='origin')
            print("pushing")
            origin.push()
            print('done')




            # subprocess.run(["git", "commit", "-m", '"updated crafts"'], shell=True)
            # subprocess.run(["git", "push"], shell=True)






    o = parse_crafts_into_tree(s.output_crafts)

    current_depth += 1

