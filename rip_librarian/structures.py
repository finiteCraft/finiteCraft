BUNDLE_TYPES: dict[str, set[str]] = {
    "testtype": {"one", "two"}
}

GENERAL_BUNDLE = "all"

class Nibble:
    """
    Wrapper class for the data stored in the database.
    Each Nibble keeps track of its tag (just a cosmetic label)
    and its datatype, which it uses to validate any attempts
    to access its data.
    """
    def __init__(self, tag: str, bundle_type: str):
        if bundle_type != "all" and bundle_type not in BUNDLE_TYPES:
            raise ValueError(f"Bundle type \"{bundle_type}\" does not exist")
        self.tag = tag
        self.bundle_type = bundle_type
        if bundle_type == "all":
            self.data = dict()
        else:
            self.data = {attr: 0 for attr in BUNDLE_TYPES[bundle_type]}

    def __getitem__(self, item: str):
        if self.bundle_type != "all" and item not in BUNDLE_TYPES[self.bundle_type]:
            raise KeyError(f"Datatype \"{self.bundle_type}\" has no attribute \"{item}\"")

        return self.data[item]

    def __setitem__(self, key: str, value):
        if self.bundle_type != "all" and key not in BUNDLE_TYPES[self.bundle_type]:
            raise KeyError(f"Datatype \"{self.bundle_type}\" has no attribute \"{key}\"")

        self.data[key] = value

    def __str__(self) -> str:
        return f"Nibble[Tag='{self.tag}', Datatype={self.bundle_type}]"

    def to_json(self) -> dict:
        return self.data.copy()


def dict_to_nibble(data: dict, tag: str, datatype: str) -> Nibble:
    nib = Nibble(tag, datatype)

    for key, value in data.items():
        nib[key] = value

    return nib


class Chunk:
    """
    A grouping of Nibbles that gets stored in the database.
    Each chunk has an associated hash and datatype, and
    has a flag to keep track of whether it has been updated.
    """
    def __init__(self, hsh: int, bundle_type: str, nibbles: dict[str, Nibble]):
        self.hsh = hsh
        self.bundle_type = bundle_type
        self.nibbles = nibbles
        self.updated = False

    def __str__(self) -> str:
        return f"Chunk[Hash={self.hsh}, Datatype={self.bundle_type}, Updated={self.updated}]"



if __name__ == "__main__":
    nib = Nibble("My nibble", "testtype")

    print(nib["one"])
    nib["two"] = "lol"
    print(nib["two"])
    print(nib)
