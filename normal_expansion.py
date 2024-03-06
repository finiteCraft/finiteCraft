from requests.exceptions import InvalidSchema

from backend.Scheduler import Scheduler
from backend.tools import *
from backend.Proxy import Proxy
import itertools
import time
import datetime
from pprint import pprint

def ping(ip):
    prox = {"https": ip}
    try:
        resp = requests.get("https://neal.fun", proxies=prox, timeout=(10, 5), verify=False)
    except InvalidSchema:
        print("SOCKS support is not installed!")
        return False, datetime.timedelta(seconds=0)
    except Exception as exc:
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr)  # properly handle the exception
        return False, datetime.timedelta(seconds=0)
    return True, resp.elapsed
print("Getting proxies...")
raw_proxies = get_proxies()


o_value = []
proxies: list[Proxy] = []

do_ping = True


for i, p in enumerate(raw_proxies):
    px = Proxy(ip=p['ip'], port=p['port'], protocol=p['protocol'])
    proxies.append(px)
print("Ranking proxies...")
perform_initial_proxy_ranking(proxies)


def get_db_elements():
    db = pymongo.MongoClient("mongodb://127.0.0.1")
    cols = list(db["crafts"].list_collection_names())
    return cols


while True:
    t = time.time()
    pick_from = get_db_elements()
    if len(pick_from) == 0:
        pick_from = ["Fire", "Water", "Wind", "Earth"]
    combin = list(itertools.combinations_with_replacement(pick_from, 2))
    num = input(f"How many crafts? (max={len(combin)}) ")

    to_calculate = random.sample(combin, int(num))

    s = Scheduler(to_calculate, proxies, name="Julian")

    s.run()

    o = parse_crafts_into_tree(s.output_crafts)
    print(s.progress)
    o_value.append(o)
    for i in o.keys():
        if i.split("`")[0] not in pick_from and i.split('`')[0] != "Nothing":
            pick_from.append(i.split("`")[0])

    print(time.time()-t)


#pprint(o_value[0])