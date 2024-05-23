from collections.abc import Mapping, Callable

import pymongo
import logging

if "H_LIB" not in globals():
    H_LIB = None

    # Logging setup
    LOG = logging.getLogger("Librarian")
    LOG.setLevel(logging.INFO)

    CONNECTION_STRING = "mongodb://192.168.1.143:27017"
    DB = pymongo.MongoClient(CONNECTION_STRING, serverSelectionTimeoutMS=2000, connectTimeoutMS=1000, socketTimeoutMS=1000)
    GENERAL_BUNDLE = "all"

def query_data(element: str, bundle_type=GENERAL_BUNDLE) -> Mapping[str, any] | None:
    """
    Fetches the data associated with the given element and bundle type.
    :param element: the element to look up
    :param bundle_type: the type of the data to search for
    :return: the data stored with the element
    """
    return DB.get_database("crafts").get_collection(element).find_one({"type": bundle_type})


def store_data(element: str, data: dict, allow_missing_attributes=False) -> None:
    """
    Stores the given data in the database.
    This overwrites everything that was previously associated with this tag.
    :param element: the tag of the data
    :param data: the data to store
    :param allow_missing_attributes: boolean flag to control whether warnings are raised for missing attributes
    """
    collection = DB.get_database("crafts").get_collection(element)

    # Update the general dataset
    collection.find_one_and_replace({"type": GENERAL_BUNDLE}, data)

    # Update the pre-computed bundles
    for btype, attributes in get_bundle_types().items():

        matching_attributes = attributes.intersection(data.keys())
        missing_attributes = attributes.difference(data.keys())
        if not allow_missing_attributes and len(missing_attributes) > 0:  # Warn about missing required attributes
            LOG.warning(f"Attempting to store data for tag '{element}', but missing require data for Bundle Type '{btype}'")
        if len(matching_attributes) <= 0: # No matching attributes, skip to next bundle type
            continue

        bundle = collection.find_one({"type": btype})
        for attr in attributes:  # Update associated attributes
            if attr in matching_attributes:
                bundle[attr] = data[attr]
            else:
                bundle[attr] = "NULL"


    LOG.debug(f"Saved element {element} to database successfully.")


def update_data(element: str, data: dict) -> None:
    """
    Updates the data associated with the tag by adding on the data given.
    This does not overwrite what already existed unless explicitly specified.
    Note that this expects some data to already exist in the database.
    :param element: the tag of the data
    :param data: the data to store
    """
    collection = DB.get_database("crafts").get_collection(element)
    if collection is None:
        raise ValueError(f"Tried to update non-existent data for element '{element}'")

    # Update the general dataset
    collection.find_one_and_update({"type": GENERAL_BUNDLE}, data)

    # Update the pre-computed bundles
    for btype, attributes in get_bundle_types().items():

        matching_attributes = attributes.intersection(data.keys())
        # don't need to do the missing attribute check since we expect the data to already exist
        if len(matching_attributes) <= 0: # No matching attributes, skip to next bundle type
            continue

        bundle = collection.find_one({"type": btype})
        for attr in matching_attributes:  # Update associated attributes
            bundle[attr] = data[attr]

    LOG.debug(f"Saved element {element} to database successfully.")


def append_data_sublist(element: str, attribute: str, sublist: list) -> None:
    collection = DB.get_database("crafts").get_collection(element)
    if collection is None:
        raise ValueError(f"Tried to update non-existent data for element '{element}'")

    general_bundle = collection.find_one({"type": GENERAL_BUNDLE})
    if attribute not in general_bundle:
        raise ValueError(f"Tried to append to non-existent attribute '{attribute}' for element '{element}'")
    if type(general_bundle[attribute]) is not list:
        raise ValueError(f"Tried to append to non-list attribute '{attribute}' for element '{element}'")

    list_to_append_to: list = general_bundle[attribute]
    list_to_append_to.extend(sublist)

    # Update the pre-computed bundles
    for btype, attributes in get_bundle_types().items():
        if attribute not in attributes:
            continue

        bundle = collection.find_one({"type": btype})
        list_to_append_to = bundle[attribute]
        list_to_append_to.extend(sublist)

    LOG.debug(f"Appended to attribute '{attribute}' of element '{element}'")
    

# region Datatype Interaction

def get_bundle_types() -> dict[str, set[str]]:
    btypes = dict()
    for btype in DB.get_database("bundle_types").list_collection_names():
        btypes[btype] = set(DB.get_database("bundle_types").get_collection(btype).find_one().keys())
    return btypes

def declare_new_bundle_type(bundle_type: str, attributes: set[str]):
    """Declares a new bundle_type for use. Give a set of attributes for it to have."""
    if bundle_type in get_bundle_types():
        raise ValueError(f"Datatype \"{bundle_type}\" already exists")

    # Set up bundle type
    btype = DB.get_database("bundle_types").create_collection(bundle_type)
    btype.insert_one({attr: "" for attr in attributes})

    # Pre-compute new bundles
    for element in DB.get_database("crafts").list_collection_names():
        collection = DB.get_database("crafts").get_collection(element)
        general_data = collection.find_one({"type": GENERAL_BUNDLE})

        if len(attributes.difference(general_data.keys())) > 0:  # If it is missing an attribute required by new bundle type
            LOG.warning(f"Element '{element}' missing attributes for new bundle type '{bundle_type}'")

        filtered_data = {"type": bundle_type}
        for attr, value in general_data.items(): # For each attribute
            if attr in attributes:  # If it is a required attribute
                filtered_data[attr] = value  # Store it

        collection.insert_one(filtered_data)


def remove_bundle_type(bundle_type: str) -> bool:
    """Removes a bundle_type and all data of that type. Returns if bundle_type was removed successfully."""
    if bundle_type not in get_bundle_types():
        return False

    DB.get_database("bundle_types").drop_collection(bundle_type)
    for element in DB.get_database("crafts").list_collection_names():
        collection = DB.get_database("crafts").get_collection(element)
        collection.delete_one({"type": bundle_type})
    return True

# endregion
