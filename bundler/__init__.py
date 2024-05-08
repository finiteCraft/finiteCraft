import pymongo

if "H_BUNDLER" not in globals():
    H_BUNDLER = None
    CONNECTION_STRING = "mongodb://192.168.1.143:27017"
    DB = pymongo.MongoClient(CONNECTION_STRING, serverSelectionTimeoutMS=2000, connectTimeoutMS=1000, socketTimeoutMS=1000)

def get_all_element_data(element: str):
    return DB.get_database("crafts").get_collection(element)
