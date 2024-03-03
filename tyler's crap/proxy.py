import typing

import js2py
import requests
from fake_useragent import UserAgent
from bs4 import BeautifulSoup
from collections import deque
from enum import Enum

ua = UserAgent()

class ProxyStatus(Enum):
    FREE = 0
    BAD = -1
    IN_USE = 1

class Proxy:
    def __init__(self, ip: str, port: str, status: ProxyStatus = ProxyStatus.FREE):
        self.ip = ip
        self.port = port
        self.parsed = f"socks5h://{ip}:{port}"
        self.status = status
        self.total_calls = 0
        self.average_response = -1.0


PROXIES: deque[Proxy] = deque()

# Retrieve latest proxies
def update_proxies():
    """
    This function is really complex. Here's how it works:

    1. gets the proxy list from spys
    2. obtains the randomly generated variables used for the hidden port numbers
    3. goes through each proxy and gets the calculation for the port number
    4. performs the calculation
    5. saves data

    This monstrosity could have been avoided if they had just let me scrape


    This is what you get.
    :return:
    """
    global PROXIES
    PROXIES = deque()
    PROXIES.append(Proxy("", ""))

    proxies_doc = requests.get('https://spys.one/en/socks-proxy-list', headers={"User-Agent": ua.random,
                                                                                "Content-Type": "application/x-www-form-urlencoded"}).text
    soup = BeautifulSoup(proxies_doc, 'html.parser')
    tables = list(soup.find_all("table"))  # Get ALL the tables

    # Variable definitions
    variables_raw = str(soup.find_all("script")[6]).replace('<script type="text/javascript">', "").replace('</script>',
                                                                                                           '').split(
        ';')[:-1]
    variables = {}
    for var in variables_raw:
        name = var.split('=')[0]
        value = var.split("=")[1]
        if '^' not in value:
            variables[name] = int(value)
        else:
            prev_var = variables[var.split("^")[1]]
            variables[name] = int(value.split("^")[0]) ^ int(prev_var)  # Gotta love the bit math

    trs = tables[2].find_all("tr")[2:]
    for tr in trs:
        address = tr.find("td").find("font")

        if address is None:  # Invalid rows
            continue

        raw_port = [i.replace("(", "").replace(")", "") for i in
                    str(address.find("script")).replace("</script>", '').split("+")[1:]]

        port = ""
        for partial_port in raw_port:
            first_variable = variables[partial_port.split("^")[0]]
            second_variable = variables[partial_port.split("^")[1]]
            port += "(" + str(first_variable) + "^" + str(second_variable) + ")+"
        port = js2py.eval_js('function f() {return "" + ' + port[:-1] + '}')()
        PROXIES.append(Proxy(address.get_text(), port))
    return len(PROXIES)


def request_proxy() -> Proxy | None:
    p = PROXIES.popleft()
    count = 0
    while p.status != ProxyStatus.FREE and count < len(PROXIES):
        PROXIES.append(p)
        p = PROXIES.popleft()
        count += 1

    if count >= len(PROXIES):
        return None  # No available proxies

    p.status = ProxyStatus.IN_USE
    return p

def return_proxy(p: Proxy, status: ProxyStatus = ProxyStatus.FREE):
    p.status = status
    PROXIES.append(p)

