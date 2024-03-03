import itertools
import json
import multiprocessing
import random
import time
import warnings
from concurrent.futures import ThreadPoolExecutor

import js2py
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import logging
ua = UserAgent()
proxies = []  # Will contain proxies
spare_crafts = []
requests_total = 0
total_amount_of_requests = 0
warnings.filterwarnings("ignore")  # Allow us to hide the "unsafe connection" with the proxies
logging.basicConfig(level=logging.INFO)


def craft(one, two, proxy=None, timeout=15):
    """
    This function, using the proxy IP passed, will attempt to craft two elements together
    :param one:
    :param two: The second element to craft
    :param proxy: The proxy IP
    :param timeout: The amount of time to wait (maximum)
    :return: None if the attempt failed, or the JSON if it succeeded.
    """
    global requests_total
    global proxies

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
        "X-Client-IP": "104.22.28.82",  # confuse cloudflare a bit
        "X-Originating-IP": "104.22.28.82",
        "X-Remote-IP": "104.22.28.82",
    }

    params = {
        'first': one,
        'second': two,
    }
    if proxy is not None:
        proxy_argument = {"https": proxy}
    else:
        proxy_argument = None
    try:
        response = requests.get('https://neal.fun/api/infinite-craft/pair', params=params, headers=headers,
                                proxies=proxy_argument, verify=False, timeout=timeout)
    except requests.exceptions.ConnectTimeout:
        return 300  # Failure
    except requests.exceptions.ConnectionError:
        return 300  # Failure
    string_response = response.content.decode('utf-8')  # Format byte response
    if "Retry-After" in response.headers:
        print("Craft with proxy", proxy, "was blocked because of a ratelimit. ")
        return int(response.headers["Retry-After"])

    try:
        json_resp = json.loads(string_response)
    except json.JSONDecodeError:  # If the response received was invalid (ratelimited, IP blocked, etc) return failure
        return 300
    requests_total += 1  # Increment the successful requests (stats)
    return json_resp


def score_proxy(p):
    """

    :param p:
    :return:
    """
    proxy_avg_response = p["average_response"]  # Example value: 3
    # total_req = p["total_calls"]  # Example value: 12
    is_functional = p['status'] <= 0 or p['status'] < time.time()
    if not is_functional:
        return -1
    if proxy_avg_response == 0:
        return 0
    return 1 / proxy_avg_response


def rank_proxies(proxy_id=None):
    """
    Rank the proxies from best to worst
    :return:
    """
    ranked = sorted(proxies, key=score_proxy, reverse=True)

    if proxy_id is None:
        return ranked
    else:
        return ranked



def worker(crafts, identification, proxy_id=None):
    """
    Represents a single worker.
    :param crafts: A list of tuple crafts to perform
    :param identification: the Worker ID
    :param proxy_id: If the worker has switched proxies,
     this is the proxy id
    """

    global spare_crafts

    time.sleep(random.random()*5)
    current_proxy = identification
    if proxy_id is not None:  # If proxy ID given, change it
        current_proxy = proxy_id
    log = logging.getLogger(f"Worker({identification})")
    if proxies[current_proxy]['used'] >= proxies[current_proxy]['max_workers']:  # Ensure we aren't "overloaded"
        log.error(f"Attempted to connect to an overloaded proxy ({current_proxy}). Now finished.")
        spare_crafts.extend(crafts)
        return

    proxies[current_proxy]['used'] += 1  # Latch on to chosen proxy
    for current_craft, c in enumerate(crafts):
        print(rank_proxies())
        log.info(f"Now crafting {c}, Craft Progress: {requests_total}/{total_amount_of_requests},"
                 f" Worker Progress: {current_craft}/{len(crafts)}")
        start = time.time()
        out = craft(c[0], c[1], proxies[current_proxy]['parsed'])  # Attempt to craft
        end = time.time()

        if type(out) is not dict:  # Craft failed, penalty is returned
            log.warning(f"Craft {c} failed!, Penalty: {out}")
            # Set proxy status to "bad, try again in <penalty> seconds"
            proxies[current_proxy]['status'] = int(end) + out
            proxies[current_proxy]['used'] -= 1  # Let go of proxy
            found = False

            # Find a proxy that (a) isn't currently in use and (b) isn't "bad"
            for ind, p in enumerate(proxies):
                # print(p)
                if (p['used'] < p['max_workers']) and (p['status'] <= 0 or p['status'] < time.time()):
                    current_proxy = ind  # Set the new current proxy
                    found = True
                    break

            if not found:  # There are no working not-in-use proxies :(
                # Add crafts this worker couldn't accomplish to spare_crafts
                spare_crafts.extend(crafts[current_craft:])
                log.error("Could not find proxy to reassign to, worker is finished.")
                return

            log.warning(f"Rescheduled proxy to {proxies[current_proxy]} (id={current_proxy})")
            worker(crafts[current_craft:], identification,
                   proxy_id=current_proxy)  # Restart with the new proxy
            return

        # For some reason, leading whitespace slips in for some cases.

        out['result'] = out['result'].strip()

        # Add the result to the tree

        if out['result'] not in list(base_tree.keys()):
            base_tree.update({out['result']: [[c[0], c[1]]]})
        else:
            if [c[0], c[1]] not in base_tree[out['result']]:
                base_tree[out['result']].append([c[0], c[1]])

        depth_max = max(base_depth[c[0]], base_depth[c[1]]) + 1
        # Add the depth
        if out['result'] not in list(base_depth.keys()):
            base_depth.update({out['result']: depth_max})
        else:
            if base_depth[out['result']] > depth_max:
                base_depth[out['result']] = depth_max

        base_emoji.update({out['result']: {"emoji": out['emoji'], "new": out["isNew"]}})

        # Update proxy stats

        proxies[current_proxy]['status'] = 0  # 0 = Usable
        proxies[current_proxy]['total_calls'] += 1
        if proxies[current_proxy]['total_calls'] == 1:
            proxies[current_proxy]['average_response'] = end - start
        else:
            proxies[current_proxy]['average_response'] = ((proxies[current_proxy]['average_response'] *
                                                           (proxies[current_proxy]['total_calls'] - 1)) +
                                                          (end - start)) / proxies[current_proxy][
                                                             'total_calls']

        # Check other proxies to see if we can switch to a faster one

        # Our proxy infomation
        current_proxy_used = proxies[current_proxy]['used']
        current_proxy_speed = proxies[current_proxy]['average_response']

        for check_proxy in proxies:
            continue

        # Make sure we don't get rate limited
        if time.time() - start < 0.2:
            time.sleep(0.2 - (end - start))


    save()  # When we get out of the loop, save data. TODO: MongoDB support


    # Check if there's any spare crafts left for us by other workers

    if len(spare_crafts):
        our_crafts = spare_crafts[:]
        log.info(f"Restarting to run {len(spare_crafts)} more tasks")
        spare_crafts = []
        proxies[current_proxy]['used'] -= 1
        worker(our_crafts, identification, proxy_id=current_proxy)
        return
    proxies[current_proxy]['used'] -= 1  # Disconnect so this functional proxy can be used if required
    log.info("Finished jobs, now done.")


def schedule(workers, word_set):
    """
    Schedule a word set to be crafted
    :param workers: the workers that can be used
    :param word_set: The word set to craft from
    :return: 
    """

    global spare_crafts
    global requests_total
    global total_amount_of_requests

    spare_crafts = []
    futures = []
    proxies_to_assign = []
    requests_total = 0
    total_required_proxy_assign_loops = (workers // len(proxies)) + 1
    for _ in range(total_required_proxy_assign_loops):
        proxies_to_assign.extend(proxies[:-1])  # Omit local proxy on extension
    with ThreadPoolExecutor(workers) as ex:
        print("Preparing combinations...", end='')
        combin = itertools.combinations_with_replacement(word_set, 2)
        crafts_to_perform = []
        for m, c in enumerate(combin):
            if [c[0], c[1]] not in existing_recipes or [c[1], c[0]] not in existing_recipes and not (c[0] == "Nothing") and not (c[1] == "Nothing"):
                crafts_to_perform.append([c[0], c[1]])

        total_amount_of_requests = m

        things_per = len(crafts_to_perform) // workers
        remaining_extra = len(crafts_to_perform) % workers
        start = 0
        print(f"done")
        print("Spawning workers...", end='')
        for worker_index in range(-1, workers-1):
            if worker_index == -1:
                proxy_to_use_index = -1
            else:
                proxy_to_use_index = proxies.index(proxies_to_assign[worker_index])
            if (worker_index + 1) <= remaining_extra:
                ft = ex.submit(worker, crafts_to_perform[start:start + things_per + 1], worker_index,
                               proxy_to_use_index)
                start += things_per + 1

                futures.append(ft)
            else:
                ft = ex.submit(worker, crafts_to_perform[start:start + things_per], worker_index,
                               proxy_to_use_index)
                start += things_per
                futures.append(ft)

        print("done")

    # print(spare_crafts)
    # print(futures)


print("Loading files...", end='')
with open('depth.json') as depth:
    base_depth = json.load(depth)

with open('tree.json') as tree:
    base_tree = json.load(tree)

with open('emoji.json') as emoji:
    base_emoji = json.load(emoji)

existing_recipes = []

print("done")


def save():
    """
    save the file ig
    """
    print("Saving...")
    with open('depth.json', 'w') as depth_write:
        json.dump(base_depth.copy(), depth_write)
    with open('tree.json', 'w') as tree_write:
        json.dump(base_tree.copy(), tree_write)
    with open('emoji.json', 'w') as emoji_write:
        json.dump(base_emoji.copy(), emoji_write)


def update_existing_recipes():
    """
    Update the existing known recipes from the tree
    """

    global existing_recipes
    values = []
    for val in base_tree.values():
        values.extend(val)
    existing_recipes = values[:]


update_existing_recipes()


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
    proxies = []
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
        proxies.append(
            {"ip": address.get_text(), "port": port, "parsed": f"socks5h://{address.get_text()}:{port}", "status": -1,
             "total_calls": 0, "average_response": 0, "used": 0, 'max_workers': 3})
    proxies.append({"ip": "", "port": "", "parsed": None, "status": -1,
                    "total_calls": 0, "average_response": 0, "used": 0, 'max_workers': 1})  # The "local" worker
    return proxies


# proxies = update_proxies()
# evolved = evolve(base_depth)
#
# print(evolved)

if __name__ == "__main__":
    print("Updating proxies...", end='')
    proxies = update_proxies()
    print(proxies)
    print(f"done ({len(proxies)} proxies including local)")
    inp = dict(random.sample(list(base_depth.items()), 50))
    #inp = base_depth
    schedule(24, inp)
