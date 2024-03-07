import pymongo
import itertools

from autocrafter.Scheduler import Scheduler


def get_db_elements():
    db = pymongo.MongoClient("mongodb://127.0.0.1")
    cols = list(db["crafts"].list_collection_names())
    return cols


current_depth = 1

while True:

    pick_from = get_db_elements()
    combin = list(itertools.combinations_with_replacement(pick_from, 2))

    s = Scheduler(combin, proxies, name="Julian")
    s.run()

    o = parse_crafts_into_tree(s.output_crafts)
    o_value.append(o)