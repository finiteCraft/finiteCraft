from pprint import pprint

import js2py
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

ua = UserAgent()


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

    post_req = {"xx0": "hehe null", "xpp": 5, "xf1": 0, "xf2": 0, "xf4": 0, "xf5": 2}

    temp_session = requests.Session()
    agent = str(ua.random)
    proxies_get = temp_session.get('https://spys.one/en/socks-proxy-list',
                                   headers={"User-Agent": agent,
                                            "Connection": "keep-alive",
                                            'Sec-Fetch-Dest': 'document',
                                            'Sec-Fetch-Mode': 'navigate',
                                            'Sec-Fetch-Site': 'same-origin',
                                            # 'Sec-GPC': '1',
                                            "Content-Type": "application/x-www-form-urlencoded"},
                                   ).text

    soup_get = BeautifulSoup(proxies_get, 'html.parser')
    tables = list(soup_get.find_all("table"))  # Get ALL the tables
    xx0 = soup_get.find("form").find("input")["value"]
    #print(xx0)
    post_req["xx0"] = xx0
    print(list(temp_session.cookies))
    proxies_post = temp_session.post('https://spys.one/en/socks-proxy-list',
                                     headers={"User-Agent": agent,
                                              "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                                              "Content-Type": "application/x-www-form-urlencoded",
                                              "Connection": "keep-alive",
                                              'Sec-Fetch-Dest': 'document',
                                              'Sec-Fetch-Mode': 'navigate',
                                              'Sec-Fetch-Site': 'same-origin',
                                              "Origin": "https://spys.one",
                                              "Upgrade-Insecure-Requests": "1",
                                              "Referer": "https://spys.one/en/socks-proxy-list/"}, data=post_req)
    pprint(dict(sorted(dict(proxies_post.headers).items())))
    proxies = []
    proxies_post = proxies_post.text
    print(proxies_post)
    # Variable definitions
    soup_post = BeautifulSoup(proxies_post, 'html.parser')
    #print(soup_post)
    variables_raw = str(soup_post.find_all("script")[6]).replace('<script type="text/javascript">', "") \
                       .replace('</script>', '').split(';')[:-1]


    variables = {}
    for var in variables_raw:
        name = var.split('=')[0]
        value = var.split("=")[1]
        if '^' not in value:
            print(name, value)
            variables[name.strip()] = int(value)
        else:
            prev_var = variables[var.split("^")[1].strip()]
            variables[name] = int(value.split("^")[0]) ^ int(prev_var)  # Gotta love the bit math

    trs = tables[2].find_all("tr")[2:]
    for tr in trs:
        address = tr.find("td").find("font")

        if address is None:  # Invalid rows
            continue

        raw_port = [i.replace("(", "").replace(")", "") for i in
                    str(address.find("script")).replace("</script>", '').split("+")[1:]]

        port = ""
        print(raw_port)
        for partial_port in raw_port:
            first_variable = variables[partial_port.split("^")[0]]
            second_variable = variables[partial_port.split("^")[1]]
            port += "(" + str(first_variable) + "^" + str(second_variable) + ")+"
        port = js2py.eval_js('function f() {return "" + ' + port[:-1] + '}')()
        proxies.append(
            {"ip": address.get_text(), "port": port, "parsed": f"socks5h://{address.get_text()}:{port}",
             "status": -1,
             "total_calls": 0, "average_response": 0, "used": 0, 'max_workers': 3, "session": requests.Session()})
    proxies.append({"ip": "", "port": "", "parsed": None, "status": -1,
                    "total_calls": 0, "average_response": 0, "used": 0, 'max_workers': 1,
                    "session": requests.Session()})  # The "local" worker
    print(len(proxies), proxies)
    return proxies


p = update_proxies()
# print(len(p), p)
#                                         document.write("<font class=spy2>:<\/font>" + (o5t0d4 ^ f6r8) + (e5s9t0 ^ p6v2) + (k1u1r8 ^ l2d4) + (e5s9t0 ^ p6v2))
#                                     103.35.189.217<script type="text/javascript">
