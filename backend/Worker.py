import collections
import logging
import warnings

from backend.Proxy import Proxy
from backend.tools import *

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)
MAXIMUM_REQUESTS_PER_SECOND = 5  # The maximum requests per second. Higher values will cause proxies to be ratelimited.
NEW_PROXY_SLEEP = 10  # The amount of time for the proxy function to sleep after failing to find a new proxy


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

    def __init__(self, all_proxies: list, all_crafts: collections.deque, proxy: Proxy, worker_id: str | int,
                 log_level=logging.INFO, return_craft_reference: list = None, db: pymongo.MongoClient = None,
                 batch_size: int = 5) -> None:
        """
        Initialize the Worker.
        :param all_proxies: the list of all the available proxies
        :param all_crafts: the collections.deque of all available crafts that need to be performed
        :param proxy: The Proxy the worker should start with
        :param worker_id: the ID of the worker (for log messages)
        :param log_level: the log level to set the internal logger to.
        :param return_craft_reference: the reference to the list to put the completed crafts in. If None,
         data will be stored in self.crafts
        """
        if return_craft_reference is None:
            return_craft_reference = []
        self.kill = False  # Whether to force quit the worker. Set this externally
        self.thread = ImprovedThread(target=Worker.run, args=[self])
        self.all_proxies = all_proxies
        self.all_crafts = all_crafts
        self.proxy = proxy
        self.session = requests.Session()
        self.id = worker_id
        self.logger = logging.getLogger(f"Worker({self.id})")
        self.logger.setLevel(log_level)
        self.crafts = return_craft_reference
        self.batch_size = batch_size  # The maximum number of jobs to concurrently send.
        self.completed = 0  # Keep track of completed jobs
        self.db = db
        self.skipped = 0  # Keep track of skipped jobs

    def begin_working(self) -> None:
        """
        Start the Worker
        :return: None
        """
        self.thread = ImprovedThread(target=Worker.run, args=[self])
        self.thread.start()

    def finish_working(self) -> bool:
        """
        Wait for the Worker to finish. Currently unused
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

        s = time.time()
        grab_attempt = self.proxy.grab(self)
        if not grab_attempt:  # If we can't get a proxy, this worker can quit (too many workers relative to proxies)
            return

        batch_number = 1  # The current batch number

        # Main loop
        while len(self.all_crafts) > 0:
            batch_start = time.time()
            if self.kill:  # Check for killswitch
                return

            batch_crafts = []
            try:
                for _ in range(self.batch_size):
                    batch_crafts.append(self.all_crafts.popleft())
            except IndexError:
                self.logger.info("Craft deque is now empty! continuing from here")

            if not len(batch_crafts):  # It was empty from the start
                return

            self.logger.info(f"Now executing batch {batch_number} "
                             f"(Current execution time: {round(time.time() - s, 2)}s)")
            batch_threads = []
            for index, current_craft in enumerate(batch_crafts):
                self.logger.debug(f"Job {index + 1} of batch {batch_number} is starting with craft {current_craft}...")

                # Check if we can be lazy and skip the craft.
                #  (this function works even if there is no database so don't worry future me)
                check = check_craft_exists_db(current_craft, self.db, return_craft_data=True)
                if check is not False:
                    self.logger.debug(f"Skipping job {index + 1} of batch {batch_number}"

                                      f" because data is already present in database.")
                    self.skipped += 1
                    self.crafts.append([current_craft, check])
                    continue

                # Start the craft worker

                t = ImprovedThread(target=craft,
                                   args=[current_craft[0], current_craft[1], self.proxy, 10, self.session],
                                   name=f"{self.id}-Job{index + 1}")
                t.start()
                batch_threads.append(t)

            need_new_proxy = False
            failed_crafts = []  # The crafts that didn't work
            for index, thread in enumerate(batch_threads):
                if self.kill:
                    return  # Check for killswitch
                result: dict = thread.join()
                self.logger.debug(f"Job {index + 1} of batch {batch_number} returned value: {result}")
                if result["status"] == "success":
                    self.crafts.append([batch_crafts[index], result])  # Save the craft
                    if self.db is not None:  # If DB is enabled
                        add_raw_craft_to_db([batch_crafts[index], result], self.db)  # Save to DB
                    self.proxy.submit(True, result["time_elapsed"])
                # Submit metrics to the Proxy object
                elif result["type"] == "read":
                    self.proxy.submit(False, None, True, False)
                elif result["type"] == "connection":
                    self.proxy.submit(False, None, False, False)
                elif result["type"] == "ratelimit":
                    self.proxy.submit(False, None, True, False,
                                      retry_after=result["penalty"])

                if result["status"] != "success":
                    # Add the craft to failed_crafts if it failed
                    failed_crafts.append(batch_crafts[index])
                    need_new_proxy = True  # We have to find a new proxy 

            # Check for failed crafts
            if need_new_proxy:  # One (or more) crafts failed, and we have a new proxy
                self.logger.warning(f"{len(failed_crafts)}/{len(batch_crafts)} of batch"
                                    f" {batch_number} failed. (Current proxy: {str(self.proxy)})"
                                    f" Attempting to locate new proxy.")
                self.proxy.withdraw(self)  # Our proxy doesn't work! Get RID OF IT
                self.find_new_proxy()  # Get a new proxy. This function returns when it's found one

                # Add the ones we've seen that just failed back to the deque
                for item in failed_crafts:
                    self.all_crafts.append(item)

                continue  # Don't need to run rate limit code here - the penalty will take care of that

            time_total: float = time.time() - batch_start
            delta: float = (len(batch_threads) / MAXIMUM_REQUESTS_PER_SECOND) - time_total

            if delta > 0:
                # If we are too fast for the rate limit, sleep it off
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
