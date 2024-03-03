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
    except Exception:
        return False, datetime.timedelta(seconds=0)
    return True, resp.elapsed

pick_from = ["Fire", "Water", "Earth", "Wind"]
raw_proxies = get_proxies()
o_value = []
proxies: list[Proxy] = []
ping_threads = []

do_ping = True


for i, p in enumerate(raw_proxies):
    px = Proxy(ip=p['ip'], port=p['port'], protocol=p['protocol'])
    proxies.append(px)
    if do_ping:
        rvt = ImprovedThread(target=ping, args=[px.parsed])
        rvt.name = i
        rvt.start()
        ping_threads.append(rvt)

for pt in ping_threads:
    pt.join()
    print(pt.result, pt.name, proxies[int(pt.name)])
    proxies[int(pt.name)].submit(pt.result[0], pt.result[1].total_seconds(), pt.result[0], pt.result[0])

t = time.time()


for _ in range(4):
    to_calculate = list(itertools.combinations_with_replacement(pick_from, 2))

    s = Scheduler(to_calculate, proxies)

    s.run()

    o = parse_crafts_into_tree(s.output_crafts)
    print(s.progress)
    o_value.append(o)
    for i in o.keys():
        if i.split("`")[0] not in pick_from and i.split('`')[0] != "Nothing":
            pick_from.append(i.split("`")[0])

    print(time.time()-t)


#pprint(o_value[0])