import itertools
import pprint

from autocrafter.tools import *


class CraftTree:
    def __init__(self, db_address):
        self.db = pymongo.MongoClient(db_address)
        self.current_depth_items = ["Earth", "Wind", "Fire", "Water"]
        self.missing_crafts_by_depth = {0: []}
        self.items_by_depth = {0: self.current_depth_items}
        self.new_items_by_depth = {0: []}

        remaining_database_collection_names = list(self.db.get_database("crafts").list_collection_names())

        depth = 1
        while True:
            print(f"depth={depth}")
            self.missing_crafts_by_depth[depth] = []
            self.items_by_depth[depth] = []
            self.new_items_by_depth[depth] = []
            for comb in itertools.combinations_with_replacement(self.current_depth_items, 2):
                result = check_craft_exists_db(comb, self.db, True)

                if result is False:  # The craft hasn't been processed, mark for processing
                    if not "Nothing" in comb:
                        # print("missing", comb)
                        self.missing_crafts_by_depth[depth].append(comb)

                else:
                    if result["result"] not in self.current_depth_items:
                        self.current_depth_items.append(result["result"])
                    self.items_by_depth[depth].append(result["result"])
                    if result["discovered"]:
                        self.new_items_by_depth[depth].append(result["result"])
            if not len(self.items_by_depth[depth]) or depth == 4:
                break
            depth += 1

        pprint.pprint(self.missing_crafts_by_depth)


c = CraftTree("mongodb://127.0.0.1:27017")
