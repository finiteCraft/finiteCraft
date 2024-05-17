from crafterbackend.Proxy import Proxy
from crafterbackend.tools import *
from crafterbackend.constants import *
import warnings
warnings.filterwarnings('ignore')


def test_proxy_source(url, passes=5, protocol="socks5h"):
    print("--------------------------------------")
    print(f"Retrieving proxies from {url}")
    proxies = []
    raw_proxies = get_url_proxies(url, proxy_type=protocol)

    print(f"Retrieved {len(raw_proxies)} proxies from {url}")
    if not len(raw_proxies):
        print("No proxies lol")
        return
    for i, p in enumerate(raw_proxies):
        px = Proxy(ip=p['ip'], port=p['port'], protocol=p['protocol'])
        proxies.append(px)
    for i in range(passes):
        print(f"Ranking proxies... (pass={i+1}/{passes})")
        perform_initial_proxy_ranking(proxies, print_all=False)
    alive = 0
    speed = 0

    for proxy in proxies:
        if proxy.total_successes:
            alive += proxy.total_successes/proxy.total_submissions
            speed += proxy.average_response
    print(f"Score: {round(alive, 2)}/{len(proxies)} ({round(alive / len(proxies) * 100, 2)}%)"
          f"\nAverage response time for functional proxies: {round(speed / len(proxies), 2)}s")


for proxy in PROXIES:
    test_proxy_source(proxy, PROXIES[proxy])
