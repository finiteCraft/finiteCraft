import datetime
import ipaddress
import os.path
import random
import shutil
import sys
import threading
import time
from crafterbackend.constants import *
import fake_useragent
import pymongo
import requests
import urllib3.exceptions
from requests.exceptions import InvalidSchema
import ujson

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
    This function, using the proxy IP passed, will attempt to craft two elements together.
    Note that order does not matter.
    :param session:
    :param one: The first element to craft
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

    # Parameters to neal.fun's API
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
        json_resp: dict = ujson.loads(string_response)
    except ujson.JSONDecodeError:  # If the response received was invalid return a ReadTimeout penalty
        return {"status": "error", "type": "read"}  # Failure

    json_resp.update(
        {"status": "success", "time_elapsed": response.elapsed.total_seconds()})  # Add success field before returning

    # isNew is a bad name.
    json_resp[DISCOVERED_NAME] = json_resp["isNew"]
    if not DISCOVERED_NAME == "isNew":  # But you never know
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
        self.killed = False
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

    def start(self):
        self.__run_backup = self.run
        self.run = self.__run
        threading.Thread.start(self)

    def __run(self):
        sys.settrace(self.globaltrace)
        self.__run_backup()
        self.run = self.__run_backup

    def globaltrace(self, frame, event, arg):
        if event == 'call':
            return self.localtrace
        else:
            return None

    def localtrace(self, frame, event, arg):
        if self.killed:
            if event == 'line':
                raise SystemExit()
        return self.localtrace

    def kill(self):
        self.killed = True


def get_url_proxies(url, proxy_type: str = "socks5h") -> list:
    """
    Get proxies from a URL. Returns a list of dictionaries containing the proxy ip/port information.
    """
    proxies = requests.get(url)
    pxs = proxies.text.split("\n")
    raw_proxies = []
    for item in pxs:
        if ":" in item:
            raw_proxies.append(
                {'ip': item.split(":")[0], 'port': item.split(":")[1].replace("\r", ""),
                 'protocol': proxy_type})
    return raw_proxies


def get_many_url_proxies(prox_links):
    """
    Get many URL proxies. A wrapper for get_url_proxies.
    """
    raw = []
    for prox_link in prox_links.keys():
        for p in get_url_proxies(prox_link, prox_links[prox_link]):
            p["ip"] = p["ip"].replace(f"{prox_links[prox_link]}://", "")
            if p not in raw:
                raw.append(p)
    return raw


depth_lock = threading.Lock()


def regenerate_depthfiles(db: pymongo.MongoClient):
    """
    Regenerate the depthfiles from the DB data. This function will be called upon a detected inconsistency between the
    """
    try:
        shutil.rmtree(DEPTHFILE_STORAGE)
    except FileNotFoundError:
        pass
    os.makedirs(DEPTHFILE_STORAGE)
    for element_name in db[DATABASE].list_collection_names():
        try:
            info = dict(db[DATABASE].get_collection(element_name).find_one({TYPE_NAME: INFO_PACKET_NAME}))
        except TypeError:
            print(element_name)
        with open(f"{DEPTHFILE_STORAGE}/{info[DEPTH_NAME]}", "a") as f:
            f.write(f"{element_name}\n")
        if not os.path.exists(f"{DEPTHFILE_STORAGE}/{info[DEPTH_NAME]}.size"):
            update_sizefile = 1
        else:
            with open(f'{DEPTHFILE_STORAGE}/{info[DEPTH_NAME]}.size', 'r') as size:
                update_sizefile = int(size.readline()) + 1
        with open(f'{DEPTHFILE_STORAGE}/{info[DEPTH_NAME]}.size', 'w') as size:
            size.write(str(update_sizefile))


def add_raw_craft_to_db(raw_craft: list[list[str, str], int, int, str], db: pymongo.MongoClient) -> None:
    """
    Add a raw craft to the database.
    :param raw_craft: The raw craft to add (format: [("Human", "Bomb"), 4, 5, "Tyler"])
    :param db: the MongoClient to add to
    :return: None
    """
    # Is the craft recursive?
    is_recursive = raw_craft[0][0][0] == raw_craft[1][RESULT_NAME] or raw_craft[0][0][1] == raw_craft[1][RESULT_NAME]

    # Get the collections for both items and their result.
    craft_item_two_collection = db[DATABASE].get_collection(encode_element_name(raw_craft[0][0][1]))
    craft_item_one_collection = db[DATABASE].get_collection(encode_element_name(raw_craft[0][0][0]))
    craft_result_collection = db[DATABASE].get_collection(encode_element_name(raw_craft[1][RESULT_NAME]))
    info_doc = craft_result_collection.find_one({TYPE_NAME: INFO_PACKET_NAME})
    element_one_depth = raw_craft[0][1]
    element_two_depth = raw_craft[0][2]

    if raw_craft[1][RESULT_NAME] in STARTING_ELEMENTS.keys():  # Depth 0 check
        depth = 0
    else:
        depth = max(element_one_depth, element_two_depth) + 1  # Otherwise, max the depths and add 1

    if info_doc:  # If the info document exists, override with that value.
        final_element_depth = info_doc["depth"]
    else:
        final_element_depth = depth

    # Is the recipe predepth?
    is_predepth = final_element_depth >= element_one_depth and final_element_depth >= element_two_depth

    # The new info document
    new_document_data = {TYPE_NAME: INFO_PACKET_NAME,
                         EMOJI_NAME: raw_craft[1][EMOJI_NAME],
                         DISCOVERED_NAME: raw_craft[1][DISCOVERED_NAME],
                         DEPTH_NAME: depth}
    with depth_lock:
        info_doc = craft_result_collection.find_one({TYPE_NAME: INFO_PACKET_NAME})
        if info_doc is None:  # Doesn't exist, insert
            craft_result_collection.insert_one(new_document_data)
            if raw_craft[1][RESULT_NAME] != NULL:  # Prevent null craft :(
                with open(f'{DEPTHFILE_STORAGE}/{final_element_depth}', 'a') as f:
                    f.write(f"{raw_craft[1][RESULT_NAME]}\n")
                if not os.path.exists(f"{DEPTHFILE_STORAGE}/{final_element_depth}.size"):
                    update_sizefile = 1
                else:
                    with open(f'{DEPTHFILE_STORAGE}/{final_element_depth}.size', 'r') as size:
                        update_sizefile = int(size.readline()) + 1
                with open(f'{DEPTHFILE_STORAGE}/{final_element_depth}.size', 'w') as size:
                    size.write(str(update_sizefile))
        elif not os.path.exists(f'{DEPTHFILE_STORAGE}/{info_doc[DEPTH_NAME]}'):
            regenerate_depthfiles(db)

    if info_doc is not None and info_doc[DEPTH_NAME] > new_document_data[DEPTH_NAME]:  # Newer depth? Optimize the depth
        craft_result_collection.delete_one(info_doc)
        craft_result_collection.insert_one(new_document_data)

    # Generate new documents
    new_document_crafted_by = {TYPE_NAME: CBY_PACKET_NAME, CRAFT_NAME: raw_craft[0][0], RECURSIVE_NAME: is_recursive,
                               PREDEPTH_NAME: is_predepth}
    new_document_crafts_1 = {TYPE_NAME: CRAFTED_PACKET_NAME, CRAFT_NAME: raw_craft[1][RESULT_NAME],
                             WITH_NAME: raw_craft[0][0][0],
                             RECURSIVE_NAME: is_recursive, PREDEPTH_NAME: is_predepth}
    new_document_crafts_2 = {TYPE_NAME: CRAFTED_PACKET_NAME, CRAFT_NAME: raw_craft[1][RESULT_NAME],
                             WITH_NAME: raw_craft[0][0][1],
                             RECURSIVE_NAME: is_recursive, PREDEPTH_NAME: is_predepth}

    # Insertion logic
    if new_document_crafts_1[WITH_NAME] == new_document_crafts_2[WITH_NAME]:  # double recipe (Water + Water)
        if craft_item_two_collection.find_one(new_document_crafts_1) is None:
            craft_item_two_collection.insert_one(new_document_crafts_1)
    else:
        if craft_item_two_collection.find_one(new_document_crafts_1) is None:
            craft_item_two_collection.insert_one(new_document_crafts_1)
        if craft_item_one_collection.find_one(new_document_crafts_2) is None:
            craft_item_one_collection.insert_one(new_document_crafts_2)

    if craft_result_collection.find_one(new_document_crafted_by) is None:
        craft_result_collection.insert_one(new_document_crafted_by)


def check_craft_exists_db(craft_data: list[str, str] | tuple[str | str], db: pymongo.MongoClient):
    """
    Check if the craft exists in the database. Return the craft's output and emoji if return_craft_data is set
    :param craft_data: The raw craft. Just the two ingredients
    :param db: the database client
    :return: False if the craft doesn't exist, and either True or the craft data depending on return_craft_data
    """
    if db is None:
        return False  # no database, doesn't exist
    craft_db = db[DATABASE].get_collection(encode_element_name(craft_data[0])).find_one(
        {TYPE_NAME: CRAFTED_PACKET_NAME, WITH_NAME: craft_data[1]})
    return craft_db is not None


def ping(ip: str):
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
    """
    Encode element name so MongoDB can handle it. Still visually the same tho
    """
    full_period = "\uff0e"
    full_dollar_sign = "\uff04"
    return element.replace(".", full_period).replace("$", full_dollar_sign)


def decode_element_name(element):
    """
    Decode element name so we can handle it.
    """
    full_period = "\uff0e"
    full_dollar_sign = "\uff04"
    return element.replace(full_period, ".").replace(full_dollar_sign, '$')
