import collections
import logging
import typing
import warnings
from pymongo.errors import *
from crafterbackend.Proxy import Proxy
from crafterbackend.tools import *

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)
MAXIMUM_REQUESTS_PER_SECOND = 5  # The maximum requests per second. Higher values will cause proxies to be ratelimited.
NEW_PROXY_SLEEP = 10  # The amount of time for the proxy function to sleep after failing to find a new proxy
EMPTY_SLEEP = 1


class Worker:
    """
    A class that handles:

    Batch processing of crafts
    Auto rescheduling of proxies when they break

    Scheduler class will be able to add crafts to the Worker when it determines there is rebalancing required

    This class will NOT
    check for already computed crafts
    run error checking
    """

    def __init__(self, all_proxies: list, craft_func: typing.Generator, spare_crafts: collections.deque, proxy: Proxy,
                 lock: threading.Lock, worker_id: str | int, log_level=logging.INFO, db: pymongo.MongoClient = None,
                 batch_size: int = 5) -> None:
        """
        Initialize the Worker.
        :param all_proxies: the list of all the available proxies
        :param craft_func: the generator of crafts
        :param spare_crafts: the collections.deque for failed crafts to enter
        :param proxy: The Proxy the worker should start with
        :param worker_id: the ID of the worker (for log messages)
        :param log_level: the log level to set the internal logger to.
        """

        self.kill = False  # Whether to force quit the worker. Set this externally
        self.killable = True  # Whether the worker is currently killable
        self.thread = ImprovedThread(target=Worker.run, args=[self], daemon=True)
        self.all_proxies = all_proxies
        self.spare_crafts = spare_crafts
        self.craft_func = craft_func
        self.proxy = proxy
        self.lock = lock
        self.session = requests.Session()
        self.id = worker_id
        self.logger = logging.getLogger(f"Worker({self.id})")
        self.logger.setLevel(log_level)
        self.batch_size = batch_size  # The maximum number of jobs to concurrently send.
        self.completed = 0  # Keep track of completed jobs
        self.db = db
        self.skipped = 0  # Keep track of skipped jobs
        self.paused = False

    def begin_working(self) -> None:
        """
        Start the Worker
        :return: None
        """
        self.thread = ImprovedThread(target=Worker.run, args=[self], daemon=True)
        self.thread.start()

    def finish_working(self) -> bool:
        """
        Wait for the Worker to finish.
        :return: False if the Worker isn't running and True if the Worker was running, but finished
        """
        if self.thread.ident is None:
            return False  # Not started
        self.thread.join()
        return True

    def is_working(self) -> bool:
        """
        Check if the Worker is still alive.
        :return: Whether the Worker is running.
        """
        return self.thread.is_alive()

    def run(self) -> None:
        """
        Run the Worker.
        :return: None
        """
        self.completed = 0
        self.skipped = 0
        self.kill = False
        self.killable = True

        s = time.time()
        grab_attempt = self.proxy.grab(self)
        if not grab_attempt:  # If we can't get a proxy, this worker can quit (too many workers relative to proxies)
            self.logger.warning("Failed to allocate proxy on startup! There are TOO MANY Workers! "
                                "Please decrease the number of workers (-w)")
            return

        batch_number = 1  # The current batch number

        # Main loop
        while not self.kill:

            batch_start = time.time()

            batch_crafts = []
            self.logger.debug(f"Now allocating batch {batch_number} "
                              f"(Current execution time: {round(time.time() - s, 2)}s)")
            self.killable = False
            try:
                try:
                    for _ in range(self.batch_size):
                        batch_crafts.append(self.spare_crafts.popleft())
                except IndexError:
                    pass
                if len(batch_crafts) != self.batch_size:
                    with self.lock:
                        for _ in range(self.batch_size-len(batch_crafts)):
                            batch_crafts.append(next(self.craft_func))
            except StopIteration:
                if len(batch_crafts) == 0:
                    self.logger.debug(f"There are no more crafts! Waiting {EMPTY_SLEEP} second(s)...")
                    time.sleep(EMPTY_SLEEP)
                    continue
                else:
                    self.logger.debug(f"Grabbed remaining {len(batch_crafts)} "
                                      f"crafts from craft generator. Going to compute now...")

            if not len(batch_crafts):  # It was empty from the start
                return
            self.killable = True
            self.logger.debug(f"Now executing batch {batch_number} "
                              f"(Current execution time: {round(time.time() - s, 2)}s)")
            batch_threads = []
            batch_indices = []
            for index, current_craft in enumerate(batch_crafts):
                self.logger.debug(f"Job {index + 1} of batch {batch_number}"
                                  f" is starting with craft {current_craft[0]}...")

                # Check if we can be lazy and skip the craft.
                check = False
                while True:
                    try:
                        check = check_craft_exists_db(current_craft[0], self.db)
                    except (ServerSelectionTimeoutError, AutoReconnect):
                        self.logger.error("Failed to check craft existence! Retrying in 1 second...")
                        continue
                    break
                if check is not False:
                    self.logger.debug(f"Skipping job {index + 1} of batch {batch_number}"
                                      f" because data is already present in database. (craft={current_craft[0]})")
                    self.skipped += 1
                    continue

                self.logger.debug(f"I actually need to compute job {index+1} of batch {batch_number} "
                                  f"because there isn't any data. (craft={current_craft[0]})")

                # Initiate the craft request
                batch_indices.append(index)
                t = ImprovedThread(target=craft,
                                   args=[current_craft[0][0], current_craft[0][1], self.proxy, 10, self.session],
                                   name=f"{self.id}-Job{index + 1}", daemon=True)
                t.start()
                batch_threads.append(t)

            self.logger.debug(f"Finished spawning threads for batch {batch_number}. "
                              f"There are {len(batch_threads)} threads started.")


            need_new_proxy = False
            failed_crafts = []  # The crafts that didn't work
            proxy_submissions = []
            for index, thread in enumerate(batch_threads):
                if self.kill:
                    return  # Check for kill switch
                result: dict = thread.join()
                self.logger.debug(f"Job {index + 1} of batch {batch_number} {batch_crafts[index][0]}"
                                  f" returned value: {result}")
                if result["status"] == "success":
                    self.completed += 1
                    self.killable = False
                    while True:
                        try:
                            add_raw_craft_to_db([batch_crafts[batch_indices[index]], result], self.db)  # Save to DB
                        except (ServerSelectionTimeoutError, AutoReconnect):
                            self.logger.error("Failed to log craft to database! Retrying in 1 second...")
                            self.killable = True
                            continue
                        break
                    self.killable = True
                    proxy_submissions.append([True, result["time_elapsed"]])
                # Submit metrics to the Proxy object
                elif result["type"] == "read":
                    proxy_submissions.append([False, None, True, False])
                elif result["type"] == "connection":
                    proxy_submissions.append([False, None, False, False])
                elif result["type"] == "ratelimit":
                    proxy_submissions.append([False, None, True, False, result["penalty"]])

                if result["status"] != "success":
                    # Add the craft to failed_crafts if it failed
                    failed_crafts.append(batch_crafts[index])
                    need_new_proxy = True  # We have to find a new proxy 

            self.proxy.submit_many(proxy_submissions)

            # Check for failed crafts
            if need_new_proxy:  # One (or more) crafts failed, and we have to find a new proxy
                self.logger.warning(f"{len(failed_crafts)}/{len(batch_crafts)} of batch"
                                    f" {batch_number} failed. (Current proxy: {str(self.proxy)})"
                                    f" Attempting to locate new proxy.")
                self.proxy.withdraw(self)  # Our proxy doesn't work! Get RID OF IT
                self.find_new_proxy()  # Get a new proxy. This function returns when it's found one

                # Add the ones we've seen that just failed back to the deque
                for item in failed_crafts:
                    self.spare_crafts.append(item)

                continue  # Don't need to run rate limit code here - the penalty will take care of that

            time_total: float = time.time() - batch_start
            delta: float = (len(batch_threads) / MAXIMUM_REQUESTS_PER_SECOND) - time_total

            if delta > 0:
                # If we are too fast for the rate limit, sleep it off
                self.logger.debug(f"Sleeping for {round(delta, 2)} seconds to keep with ratelimit of"
                                  f" {MAXIMUM_REQUESTS_PER_SECOND} request(s) per second.")
                time.sleep(delta)

            batch_number += 1  # Forgot to put this :(

        self.logger.info(f"Finished processing of {self.completed} jobs. ({self.skipped} skipped)")
        self.proxy.withdraw(self)  # Give our proxy back

    def find_new_proxy(self) -> None:
        """
        Find a new proxy. This function will run until it finds a new proxy that

        (a) is unchecked, valid, or timed-out invalid
        (b) is unused

        This function doesn't return anything, it will instead set self.proxy.

        :return: None
        """
        grabbed = False  # Have we found a proxy yet?
        while not grabbed:
            for proxy in rank_proxies(self.all_proxies):  # Rank proxies so we start with the BEST ONES FIRST
                if proxy.disabled_until <= time.time():  # Ready to TRY AGAIN
                    self.logger.debug(f"Attempting to grab suitable proxy {str(proxy)}...")
                    attempt_to_grab = proxy.grab(self)  # Try to connect to the proxy

                    if attempt_to_grab:  # WE GOT EM BOIS
                        self.logger.info(f"Found new proxy: {str(proxy)}.")

                        # Update self.proxy
                        grabbed = True
                        self.proxy = proxy
                        break
                    else:  # Failed to connect to proxy
                        self.logger.debug(f"Failed to grab proxy {str(proxy)}")

            if grabbed:  # Hotfix
                break

            # We haven't found a proxy yet, just WAIT for NEW_PROXY_SLEEP seconds
            self.logger.error(
                f"Unable to find available, functional proxy! Retrying in {NEW_PROXY_SLEEP} seconds...")
            time.sleep(NEW_PROXY_SLEEP)  # Keep on fruiting for a proxy ig

    def __str__(self) -> str:
        """
        Represent the Worker as a string
        :return:
        """
        return self.id

    def __repr__(self) -> str:
        """
        Represent the Worker.
        :return:
        """
        return (f"Worker({self.id}): proxy: {self.proxy}, completed: {self.completed} skipped: {self.skipped},"
                f" running: {self.is_working()}, batch_size: {self.batch_size}")
