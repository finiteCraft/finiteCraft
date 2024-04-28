DATATYPES: dict[str, set[str]] = {
    "testtype": {"one", "two"}
}

class Nibble:
    """
    Wrapper class for the data stored in the database.
    Each Nibble keeps track of its tag (just a cosmetic label)
    and its datatype, which it uses to validate any attempts
    to access its data.
    """
    def __init__(self, tag: str, datatype: str):
        if datatype not in DATATYPES:
            raise ValueError(f"Datatype \"{datatype}\" does not exist")
        self.tag = tag
        self.datatype = datatype
        self.data = {attr: 0 for attr in DATATYPES[datatype]}

    def __getitem__(self, item: str):
        if item not in DATATYPES[self.datatype]:
            raise KeyError(f"Datatype \"{self.datatype}\" has no attribute \"{item}\"")

        return self.data[item]

    def __setitem__(self, key: str, value):
        if key not in DATATYPES[self.datatype]:
            raise KeyError(f"Datatype \"{self.datatype}\" has no attribute \"{key}\"")

        self.data[key] = value

    def __str__(self) -> str:
        return f"Nibble[Tag='{self.tag}', Datatype={self.datatype}]"

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
    def __init__(self, hsh: int, datatype: str, nibbles: dict[str, Nibble]):
        self.hsh = hsh
        self.datatype = datatype
        self.nibbles = nibbles
        self.updated = False

    def __str__(self) -> str:
        return f"Chunk[Hash={self.hsh}, Datatype={self.datatype}, Updated={self.updated}]"



if __name__ == "__main__":
    nib = Nibble("My nibble", "testtype")

    print(nib["one"])
    nib["two"] = "lol"
    print(nib["two"])
    print(nib)
