import threading
import requests
import time
import json
from json.decoder import JSONDecodeError
from data import NULL_RECIPE_KEY
import proxy
from utilities import to_percent

LOCK = threading.Lock()

class FailThreadInterrupt(RuntimeError):
    def __init__(self, msg: str):
        super().__init__(msg)


rHEADERS = {
    'User-Agent': 'BocketBot',
    'Accept': '/',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': 'https://neal.fun/infinite-craft/',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-GPC': '1',
}
class CrafterThread(threading.Thread):
    def __init__(self, history: dict[str, any], batch: list[tuple[int, int]],
                 delay=0.0, id: int | None = None, timeout=5):
        """
        Creates a CrafterThread object, and automatically generates the combinations it
        will try from the given points.

        :param history: the history object to use for datakeeping
        :param batch: the batch assigned to this thread
        :param delay: the time between trying combinations
        :param id: the ID of the thread
        :param timeout: the max timeout for an HTTP request
        """
        super().__init__(target=self.process)
        self.session = requests.sessions.Session()
        self.session.headers = rHEADERS
        self.session.verify = False
        self.proxy: proxy.Proxy | None = None
        self.first_proxy: dict | None = None
        self.cycle_proxy()

        self.history = history
        self.batch: list[tuple[int, int]] = batch
        self.timeout = timeout
        self.next_combo = 0
        self.sleep = delay
        self.crafted: list[str] = []
        self.recipes: dict[str, list[str]] = {NULL_RECIPE_KEY: []}
        self.levels: dict[str, int] = {}
        self.new_recipes: list[str] = []
        self.cancel = False
        self.exception: Exception | None = None
        self.success = False
        self.ID = id

    def cycle_proxy(self):
        with LOCK:
            if self.proxy is not None:
                proxy.return_proxy(self.proxy, proxy.ProxyStatus.BAD)
            self.proxy = proxy.request_proxy()

        if self.proxy is None:
            raise FailThreadInterrupt("No proxy available")

        if self.proxy.ip is not "":
            self.session.proxies = {'https': self.proxy.parsed}

    def combine(self, one: str, two: str) -> dict[str, any]:
        """
        Constructs an HTTP GET request emulating combining the two elements,
        sends it to neal.fun, and returns the result.
        """
        if self.cancel:
            raise FailThreadInterrupt()

        params = {
            'first': one,
            'second': two,
        }

        try:
            response = self.session.get('https://neal.fun/api/infinite-craft/pair', params=params, timeout=self.timeout)
        except requests.exceptions.Timeout:
            # If a proxy timed out, cycle to the next one
            self.log(f"Proxy has timed out: {self.proxy} - "
                     f"Switching proxies...")
            self.cycle_proxy()
            return self.combine(one, two)

        try:
            return json.loads(response.content.decode('utf-8'))
        except JSONDecodeError:
            self.log(f"InfiniteCraft has temporarily IP-blocked this proxy: {self.proxy} - "
                     f"Switching proxies...")
            self.cycle_proxy()
            return self.combine(one, two)  # Retry the message with the cycled proxy

    def kill(self):
        self.cancel = True

    def join(self, timeout: float | None = None, ignore_exceptions=True) -> None:
        super().join(timeout)
        if self.session is not None:
            self.session.close()
        if len(self.new_recipes) != 0:
            self.log("FOUND NEW RECIPES")
        if not ignore_exceptions and self.exception is not None:
            raise self.exception

    def log(self, msg: str):
        print(f"[Thread #{self.ID}] [Progress: {to_percent(self.progress())}%] {msg}")

    def progress(self) -> float:
        return self.next_combo / len(self.batch)

    def dump_combos(self, dest: list[tuple[int, int]]):
        for i in range(self.next_combo, len(self.batch)):
            dest.append(self.batch[i])

    def process(self):
        """The function that runs during the thread. Automatically stops if self.cancel is true."""
        try:
            for i, combo in enumerate(self.batch):
                self.next_combo = i  # Update next combo
                if self.cancel:
                    proxy.return_proxy(self.proxy)
                    raise FailThreadInterrupt("Thread was killed.")

                e1 = self.history["elements"][combo[0]]
                e2 = self.history["elements"][combo[1]]
                recipe_key = e1 + ";" + e2

                result_json = self.combine(e1, e2)
                result_key = result_json["result"]

                if result_key == "Nothing":
                    self.recipes[NULL_RECIPE_KEY].append(recipe_key)
                    self.log(f"NULL RECIPE: {e1} + {e2}")
                    continue

                self.log(f"{e1} + {e2} = {result_key}")

                # Update recipes
                if result_key not in self.recipes:
                    self.recipes[result_key] = [recipe_key]
                elif recipe_key not in self.recipes[result_key]:
                    self.recipes[result_key].append(recipe_key)

                # Update our history
                if result_key not in self.crafted:
                    self.crafted.append(result_key)

                if result_key not in self.levels:
                    self.levels[result_key] = self.history["level"]

                # Keep track of new discoveries
                if result_json["isNew"]:
                    self.log(f"NEW DISCOVERY: {e1} + {e2} = {result_key}")
                    self.new_recipes.append(result_key)

                time.sleep(self.sleep)

            # we only get here if we complete everything
            self.success = True
        except Exception as e:
            self.log(f"Exception was raised: {e}")
            if type(e) is not FailThreadInterrupt:
                self.exception = e
        finally:
            self.session.close()
