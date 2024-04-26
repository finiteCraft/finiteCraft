import collections
import logging
from typing import Generator
from crafterbackend.Proxy import Proxy
from crafterbackend.Worker import Worker
from crafterbackend.tools import *


class Scheduler:
    def __init__(self, crafts: Generator[tuple[str, str], int, int], job_size: int, proxies: list[Proxy],
                 mongo_connection_string: str = None, name: str = "Julian", max_workers: int = 5,
                 log_level: int = logging.INFO) -> None:
        """
        Initialize a Scheduler.
        :param crafts: The crafts that have to be completed as a Generator
        :param proxies: the proxies we can use to do the job
        :param name: The name of the Scheduler
        :param log_level: the log level of the internal logger
        """

        self.proxies = proxies

        self.spare_crafts = collections.deque(maxlen=job_size)
        self.craft_func = crafts
        self.initial_craft_size = job_size
        self.workers = []
        self.max_workers = max_workers
        self.kill = False
        self.name = name
        self.logger = logging.getLogger(f"Scheduler({name})")
        self.logger.setLevel(log_level)
        self.progress = {"status": "not started"}  # Progress metrics for other scripts
        self.saving_to_db = type(mongo_connection_string) is str
        self.db = pymongo.MongoClient(mongo_connection_string, serverSelectionTimeoutMS=5000)
        self.all_workers = []
        self.lock = threading.Lock()

    def run(self) -> None:
        """
        Run the scheduler.
        :return: None
        """

        self.workers = []
        self.all_workers = []
        spare_crafts = collections.deque(maxlen=self.initial_craft_size)
        # Prepare the Tyler-Workers
        if self.initial_craft_size == 0:
            return
        rank = rank_proxies(self.proxies)
        for worker_id in range(self.max_workers):
            new_worker = Worker(self.proxies, self.craft_func, spare_crafts, rank[worker_id], self.lock,
                                f"Tyler-{worker_id}", db=self.db, log_level=self.logger.level)
            self.workers.append(new_worker)
            self.all_workers.append(new_worker)

        start_time = time.time()
        # Start the Tyler-Workers
        for w in self.workers:
            w.begin_working()

        # Main loop
        completed = 0
        skipped = 0
        while not self.kill:
            # Calculate how many total jobs have been completed by the workers (for progress bar)
            completed = 0
            skipped = 0
            for w in self.workers:
                completed += w.completed
                skipped += w.skipped

            # Calculate completed percentage and ETA
            complete_percentage = 100 * (completed + skipped) / self.initial_craft_size

            if complete_percentage:
                current_time = time.time() - start_time
                total_time = (100 / complete_percentage) * current_time
                remaining_time = round(total_time - current_time, 2)

            else:
                remaining_time = "inf"

            # Log the information
            self.logger.info(f"Current overall progress: "
                             f"{completed + skipped}/{self.initial_craft_size} ({round(complete_percentage, 2)}%,"
                             f" ETA: {remaining_time}s, completed: {completed}, skipped: {skipped})")
            # Update internal progress
            self.progress = {"status": "running", "jobs_completed": self._generate_self_running(),
                             "completed": completed, "skipped": skipped, "total_amount": self.initial_craft_size,
                             "percentage_done": complete_percentage, "workers_alive": len(self.workers),
                             "eta": remaining_time}
            if completed + skipped == self.initial_craft_size:  # All crafts are done!
                self.logger.info("All crafts are now complete! Sending kill to workers...")
                for w in self.workers:
                    w.kill = True
                    w.finish_working()
                break
            try:
                time.sleep(1)  # Reduced CPU usage by 78% on my computer
            except KeyboardInterrupt:
                self.logger.info("Caught KeyboardInterrupt! Shutting down...")
                for w in self.workers:
                    w.kill = True
                    w.finish_working()
                    break
        self.logger.info(f"Completed {self.initial_craft_size} crafts in {round(time.time() - start_time, 2)}s "
                         f"(completed={completed}, skipped={skipped})")
        if not self.kill:
            self.progress["status"] = "finished"  # We're done!
            del self.progress["eta"]
            del self.progress["workers_alive"]
        else:  # We were killed for some reason
            self.progress["status"] = "killed"

    def _generate_self_running(self) -> dict:
        """
        Generate a dictionary of the amount of work each worker has done. Meant for self.progress
        :return: the dictionary representing the amount of work done.
        """
        jobs_division = {}
        for w in self.all_workers:
            jobs_division[w.id] = {"completed": w.completed, "skipped": w.skipped}

        return jobs_division
