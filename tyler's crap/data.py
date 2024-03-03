import os.path
import json

HISTORY_FILE = "history.json"
HISTORY: dict[str, int | list[any] | dict[str, int]] = {}
RECIPE_FILE = "recipes.json"
RECIPES: dict[str, list[str]] = {}
NULL_RECIPE_KEY = "%NULL%"
BATCH_FILE = "batch_data.json"
BATCH_DATA: list[tuple[int, int]] = []

def load():
    global HISTORY
    global RECIPES
    global BATCH_DATA
    # Load history from JSON file
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as fp:
            HISTORY = json.load(fp)

    # Load recipes from JSON file
    if os.path.exists(RECIPE_FILE):
        with open(RECIPE_FILE, "r") as fp:
            RECIPES = json.load(fp)
        if NULL_RECIPE_KEY not in RECIPES:
            RECIPES[NULL_RECIPE_KEY] = []

    # Load thread data from JSON file
    if os.path.exists(BATCH_FILE):
        with open(BATCH_FILE, "r") as fp:
            BATCH_DATA = json.load(fp)

def dump():
    # Save data after each level
    with open(HISTORY_FILE, "w") as fp:
        json.dump(HISTORY, fp, indent=4)
    with open(RECIPE_FILE, "w") as fp:
        json.dump(RECIPES, fp, indent=4)
    with open(BATCH_FILE, "w") as fp:
        json.dump(BATCH_DATA, fp, indent=4)
