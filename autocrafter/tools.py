import datetime
import ipaddress
import json
import random
import sys
import threading
import time

import fake_useragent
import js2py
import pymongo
import requests
import urllib3.exceptions
from bs4 import BeautifulSoup
from requests.exceptions import InvalidSchema

ua = fake_useragent.UserAgent()


def verify_ip(ip: str) -> bool:
    """
    Check if a given IP is valid
    :param ip:
    :return: is it valid?
    """
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def verify_port(port: str | int) -> bool:
    """
    Check if a port is valid.
    :param port:
    :return: is it valid?
    """
    if type(port) is int:
        return port > 0
    else:
        return port.isnumeric()


def craft(one: str, two: str, proxy=None, timeout: int = 15, session: requests.Session | None = None) -> dict:
    """
    This function, using the proxy IP passed, will attempt to craft two elements together
    :param session:
    :param one:
    :param two: The second element to craft
    :param proxy: The proxy IP
    :param timeout: The amount of time to wait (maximum)
    :return: None if the attempt failed, or the JSON if it succeeded.
    """

    # Request headers
    headers = {
        'User-Agent': ua.random,
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://neal.fun/infinite-craft/',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-GPC': '1',
    }

    # Parameters
    params = {
        'first': one,
        'second': two,
    }

    # Proxy
    proxy_argument = {"https": proxy.parsed}

    try:
        # Are we using a session?
        if session is None:
            getter = requests
        else:
            getter = session

        response: requests.Response = getter.get('https://neal.fun/api/infinite-craft/pair', params=params,
                                                 headers=headers,
                                                 proxies=proxy_argument, verify=False, timeout=(timeout, timeout * 2))

    # Catch errors
    except requests.exceptions.ConnectTimeout:
        return {"status": "error", "type": "connection"}  # Failure
    except requests.exceptions.ConnectionError as e:
        return {"status": "error", "type": "connection"}  # Failure
    except requests.exceptions.ReadTimeout:
        return {"status": "error", "type": "read"}  # Failure
    except urllib3.exceptions.ProtocolError:
        return {"status": "error", "type": "read"}  # :(
    except requests.exceptions.ChunkedEncodingError:
        return {"status": "error", "type": "read"}  # :(((
    except requests.exceptions.RequestException:
        return {"status": "error", "type": "read"}  # :((((((((((
    string_response: str = response.content.decode('utf-8')  # Format byte response
    if "Retry-After" in response.headers:
        return {"status": "error", "type": "ratelimit", "penalty": int(response.headers["Retry-After"])}
    try:
        json_resp: dict = json.loads(string_response)
    except json.JSONDecodeError:  # If the response received was invalid return a ReadTimeout penalty
        return {"status": "error", "type": "read"}  # Failure

    json_resp.update(
        {"status": "success", "time_elapsed": response.elapsed.total_seconds()})  # Add success field before returning

    # isNew is a bad name.
    json_resp["discovered"] = json_resp["isNew"]
    del json_resp["isNew"]

    return json_resp


def score_proxy(p):
    """
    Get a number representing the usefulness of the proxy based on its data. Higher is better.
    :param p: The proxy to score
    :return: The score of the proxy
    """

    salt = random.random() / 5
    if p.disabled_until > time.time():  # INVALID PROXY WOOT WOOT
        return -100 + salt
    if p.worker is not None:
        return -100 + salt  # We can't use the proxy anyway :(
    if p.ip is None:
        return 100  # No proxy - very fast - high priority
    if p.total_submissions == 0:
        return 0 + salt

    if p.average_response != 0:
        return (1 / p.average_response) * (p.total_successes / p.total_submissions) + salt
    # Only possible case for this is a proxy that (a) has never functioned (b) whose timeout has expired
    # and (c) whose status is -1. Send unchecked in this case.
    return 0 + salt


def rank_proxies(proxies: list):
    """
    Rank the proxies from best to worst
    :return:
    """
    ranked = sorted(proxies, key=score_proxy, reverse=True)
    return ranked


class ImprovedThread(threading.Thread):
    """
    A very similar version of threading.Thread that returns the value of the thread process
    with Thread.join().
    This allows for batch processing to work.

    It also prints exceptions when they are thrown.
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize the ImprovedThread
        :param args:
        :param kwargs:
        """
        super().__init__(*args, **kwargs)
        self.result = None

    def run(self) -> None:
        """
        Run the ImprovedThread.
        :return:
        """
        if self._target is None:
            return  # could alternatively raise an exception, depends on the use case
        try:
            self.result = self._target(*self._args, **self._kwargs)
        except Exception as exc:
            print(f'{type(exc).__name__}: {exc}', file=sys.stderr)  # properly handle the exception
            raise exc

    def join(self, *args, **kwargs) -> dict:
        """
        The highlight of the class. Returns the thread result upon ending.
        :param args:
        :param kwargs:
        :return:
        """
        super().join(*args, **kwargs)
        return self.result


def get_spys_one_proxies() -> list:
    """
    This function is really complex. Here's how it works:

    1. gets the proxy list from spys
    2. obtains the randomly generated variables used for the hidden port numbers
    3. goes through each proxy and gets the calculation for the port number
    4. performs the calculation
    5. saves data

    This monstrosity could have been avoided if they had just let me scrape.


    This is what you get.
    :return:
    """
    proxies = []
    proxies_doc = (requests.get('https://spys.one/en/socks-proxy-list',
                                headers={"User-Agent": ua.random, "Content-Type": "application/x-www-form-urlencoded"})
                   .text)

    # Get the parser
    soup = BeautifulSoup(proxies_doc, 'html.parser')
    tables = list(soup.find_all("table"))  # Get ALL the tables

    # Variable definitions
    variables_raw = str(soup.find_all("script")[6]).replace('<script type="text/javascript">', "").replace('</script>',
                                                                                                           '').split(
        ';')[:-1]

    # Define the variables
    variables = {}
    for var in variables_raw:
        name = var.split('=')[0]
        value = var.split("=")[1]
        if '^' not in value:
            variables[name] = int(value)
        else:
            prev_var = variables[var.split("^")[1]]
            variables[name] = int(value.split("^")[0]) ^ int(prev_var)  # Gotta love the bit math

    # Get each row of the giant table
    trs = tables[2].find_all("tr")[2:]
    for tr in trs:
        # Try to find the area where the IP and encoded port are
        address = tr.find("td").find("font")

        if address is None:  # This row doesn't have an IP/port on it
            continue

        # I've blanked out the sheer amount of weirdness that happens here
        raw_port = [i.replace("(", "").replace(")", "") for i in
                    str(address.find("script")).replace("</script>", '').split("+")[1:]]

        # Calculate the prot
        port = ""
        for partial_port in raw_port:
            first_variable = variables[partial_port.split("^")[0]]
            second_variable = variables[partial_port.split("^")[1]]
            port += "(" + str(first_variable) + "^" + str(second_variable) + ")+"
        port = js2py.eval_js('function f() {return "" + ' + port[:-1] + '}')()

        proxies.append(
            {"ip": address.get_text(), "port": port, "protocol": "socks5h"})
    proxies.append({"ip": None, "port": None, "protocol": "socks5h"})  # The "local" worker

    return proxies


def get_proxyscrape_proxies() -> list:
    """
    ProxyScrape makes it ez at least
    :)
    I could use the data for rankings
    :return:
    """
    proxies = requests.get("https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&protocol=socks5&timeout=15000&proxy_format=ipport&format=json")
    pxs = json.loads(proxies.text)
    raw_proxies = []
    for item in pxs["proxies"]:
        raw_proxies.append({'ip': item['ip'], 'port': str(item['port']), 'protocol': 'socks5h'})
    return raw_proxies


def get_url_proxies(url) -> list:
    proxies = requests.get(url)
    pxs = proxies.text.split("\n")
    raw_proxies = []
    for item in pxs:
        item = item.replace("socks5://", "")

        if ":" in item:
            raw_proxies.append({'ip': item.split(":")[0], 'port': item.split(":")[1].replace("\r", ""), 'protocol': 'socks5h'})
    return raw_proxies


def get_many_url_proxies(prox_links):
    raw = []
    for prox_link in prox_links:
        for p in get_url_proxies(prox_link):
            if p not in raw:
                raw.append(p)
    return raw


def parse_crafts_into_tree(raw_crafts) -> dict:
    """
    Parse raw crafts into a craft tree.
    :param raw_crafts: the input crafts
    :return: the parsed tree
    """
    out = {}

    for c in raw_crafts:
        input_craft = c[0]

        output_result = c[1]
        key = output_result["result"] + "`" + output_result["emoji"]
        if key not in out.keys():
            out.update({key: [input_craft]})
        else:
            if input_craft not in out[key] and [input_craft[1], input_craft[0]] not in out[key]:
                out[key].append(input_craft)
    return out


depth_item_cache = {}
max_depth_cache_size = 10 ** 8  # cache size


def get_depth_of(element, db):
    if len(depth_item_cache.keys()):
        oldest = list(depth_item_cache.keys())[0]
    else:
        oldest = None
    if element in ["Wind", "Fire", "Earth", "Water"]:
        return 0
    elif element in depth_item_cache.keys():
        depth = depth_item_cache[element]
        if oldest is not None:
            depth_item_cache.pop(oldest)
        depth_item_cache.update({element: depth})
        return depth
    else:
        craft_result_collection = db["crafts"].get_collection(encode_element_name(element))

        info_doc = craft_result_collection.find_one({"type": "info"})
        if info_doc is None:
            return 1
        if len(depth_item_cache) == max_depth_cache_size:
            if oldest is not None:
                depth_item_cache.pop(oldest)
            depth_item_cache.update({element: info_doc["depth"]})
        else:
            depth_item_cache[element] = info_doc["depth"]
        return info_doc["depth"]


def invalidate_element(element):
    if element in depth_item_cache.keys():
        del depth_item_cache[element]


def add_raw_craft_to_db(raw_craft: list[list[str, str], dict], db: pymongo.MongoClient) -> None:
    """
    Add a raw craft to the database.
    :param raw_craft: The raw craft to add
    :param db: the MongoClient to add to
    :return: None
    """
    is_recursive = raw_craft[0][0] == raw_craft[1]["result"] or raw_craft[0][1] == raw_craft[1]["result"]
    new_document_crafted_by = {"type": "crafted_by", "craft": raw_craft[0], "recursive": is_recursive}
    new_document_crafts_1 = {"type": "crafts", "craft": raw_craft[1]["result"], "with": raw_craft[0][0],
                             "recursive": is_recursive}
    new_document_crafts_2 = {"type": "crafts", "craft": raw_craft[1]["result"], "with": raw_craft[0][1],
                             "recursive": is_recursive}
    craft_item_two_collection = db["crafts"].get_collection(encode_element_name(raw_craft[0][1]))
    craft_item_one_collection = db["crafts"].get_collection(encode_element_name(raw_craft[0][0]))
    craft_result_collection = db["crafts"].get_collection(encode_element_name(raw_craft[1]["result"]))
    if new_document_crafts_1["with"] == new_document_crafts_2["with"]:  # double recipe (Water + Water)
        if craft_item_two_collection.find_one(new_document_crafts_1) is None:
            craft_item_two_collection.insert_one(new_document_crafts_1)
    else:
        if craft_item_two_collection.find_one(new_document_crafts_1) is None:
            craft_item_two_collection.insert_one(new_document_crafts_1)
        if craft_item_one_collection.find_one(new_document_crafts_2) is None:
            craft_item_one_collection.insert_one(new_document_crafts_2)

    if craft_result_collection.find_one(new_document_crafted_by) is None:
        craft_result_collection.insert_one(new_document_crafted_by)
    info_doc = craft_result_collection.find_one({"type": "info"})
    if raw_craft[1]["result"] in ["Fire", "Water", "Earth", "Wind"]:
        depth = 0
    else:
        depth = max(get_depth_of(raw_craft[0][0], db), get_depth_of(raw_craft[0][1], db)) + 1
    new_document_data = {"type": "info",
                         "emoji": raw_craft[1]["emoji"],
                         "discovered": raw_craft[1]["discovered"],
                         "depth": depth}
    if info_doc is None:
        craft_result_collection.insert_one(new_document_data)
    else:
        if info_doc["depth"] > new_document_data["depth"]:
            craft_result_collection.delete_one(info_doc)
            craft_result_collection.insert_one(new_document_data)


def check_craft_exists_db(craft_data: list[str, str] | tuple[str | str], db: pymongo.MongoClient,
                          return_craft_data=False):
    """
    Check if the craft exists in the database. Return the craft's output and emoji if return_craft_data is set
    :param craft_data: The raw craft. Just the two ingredients
    :param db: the database client
    :param return_craft_data: whether to return the raw craft data
    :return: False if the craft doesn't exist, and either True or the craft data depending on return_craft_data
    """
    if db is None:
        return False  # no database, doesn't exist
    craft_db = db["crafts"].get_collection(encode_element_name(craft_data[0])).find_one({"type": "crafts", "with": craft_data[1]})
    if not return_craft_data or craft_db is None:  # If we don't need to send the craft or we can't, return
        return craft_db is not None
    else:  # We are sending the craft data
        this_item_crafts = craft_db["craft"]
        info = db["crafts"].get_collection(encode_element_name(this_item_crafts)).find_one({"type": "info"})  # Try to get the info
        if info is not None:  # Just in case (this should never not happen)
            emoji = info["emoji"]
            is_discovered = info["discovered"]
        else:
            emoji = ""
            is_discovered = ""

        return {"result": this_item_crafts, "emoji": emoji, "discovered": is_discovered}  # Return the packaged craft


def ping(ip):
    """
    Ping a proxy IP
    :param ip: the proxy to ping
    :return: Whether the proxy responded
    """
    prox = {"https": ip}
    try:
        resp = requests.get("https://neal.fun", proxies=prox, timeout=(10, 5), verify=False)
    except InvalidSchema:  # pysocks not installed
        print("ERROR: SOCKS support is not installed!")
        return False, datetime.timedelta(seconds=0)
    except:  # I know this is bad, but we have to catch ANYTHING
        return False, datetime.timedelta(seconds=0)
    return True, resp.elapsed


def perform_initial_proxy_ranking(proxies):
    """
    Take a list of Proxies and ping each one
    :param proxies: the Proxies to ping
    :return: the Proxies (you don't need to use it tho)
    """
    ping_threads = []
    for i, px in enumerate(proxies):
        rvt = ImprovedThread(target=ping, args=[px.parsed])  # Start the pinging
        rvt.name = i
        rvt.start()
        ping_threads.append(rvt)

    for pt in ping_threads:  # Join the ping threads
        pt.join()
        # submit results
        proxies[int(pt.name)].submit(pt.result[0], pt.result[1].total_seconds(), pt.result[0], pt.result[0])
    return proxies


def encode_element_name(element):
    full_period = "\uff0e"
    full_dollar_sign = "\uff04"
    return element.replace(".", full_period).replace("$", full_dollar_sign)


def decode_element_name(element):
    full_period = "\uff0e"
    full_dollar_sign = "\uff04"
    return element.replace(full_period, ".").replace(full_dollar_sign, '$')