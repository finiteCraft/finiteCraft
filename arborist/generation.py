import math
import time

from structures import *
from collections import deque
from copy import deepcopy
import pymongo

# This is a placeholder for now.
# Real recipes should be loaded from database
RECIPES: dict[str, list[tuple[str, str]]] = {
    "Lake": [
        ("Water", "Water")
    ],
    "Smoke": [
        ("Fire", "Wind")
    ],
    "Volcano": [
        ("Fire", "Lake"),
        ("Fire", "Fire"),
        ("Fire", "Smoke"),
    ],
    "Lava": [
        ("Fire", "Earth"),
        ("Water", "Volcano"),
        ("Fire", "Volcano"),
        ("Earth", "Volcano"),
    ]
}
GIVEN_ELEMENTS: set[str] = {"Water", "Fire", "Wind", "Earth"}

DB = pymongo.MongoClient("mongodb://127.0.0.1")
def get_recipes_for(element: str) -> list[tuple[str, str]]:
    # return [ ( o["craft"][0], o["craft"][1] ) for o in DB["crafts"][element].find_all({"type": "crafted_by"}) ]
    return RECIPES[element]

def basic_tree(target_element: str) -> SimpleCraftingTree:
    """
    Generates a naive crafting tree for the target element
    by choosing the first-available recipe at every opportunity.
    :param target_element: the element to craft
    :return: the crafting tree
    """
    tree = SimpleCraftingTree(target_element)

    leaves: deque[CraftTreeNode] = deque()
    leaves.append(tree.root)
    while len(leaves):
        node = leaves.popleft()

        if node.element in GIVEN_ELEMENTS:
            continue  # don't bother with elements that are assumed to be given

        recipe = get_recipes_for(node.element)[0]  # Just choosing first-found recipe
        new1, new2 = node.load_recipe(recipe)
        if new1:
            leaves.append(node.ing1)
        if new2:
            leaves.append(node.ing2)

    return tree


def compare_trees(tree1: dict[str, tuple[str, str] | None], tree2: dict[str, tuple[str, str] | None]) -> int:
    """Compares the trees based on breadcrumb count, then craft count."""
    bdiff = len(tree1) - len(tree2)
    if bdiff > 0:
        return 1
    if bdiff < 0:
        return -1

    # Breadcrumb count is equal, go to craft count
    for element in tree1:
        if tree1[element] is None:
            bdiff -= 1
    for element in tree2:
        if tree2[element] is None:
            bdiff += 1

    if bdiff > 0:
        return 1
    if bdiff < 0:
        return -1
    return 0


def smallest_tree_naive_helper(working_tree: SimpleCraftingTree,
                               leaves: deque[CraftTreeNode],
                               smallest: dict[str, tuple[str, str]]) -> dict[str, tuple[str, str] | None]:

    if len(smallest) and len(leaves) > len(smallest):
        return smallest  # There's no way this tree is gonna be smaller, prune this branch

    if not len(leaves):  # Have we completed a tree?
        # yes, compare against current smallest
        if len(smallest) == 0 or compare_trees(working_tree.to_dict(), smallest) < 0:
            return working_tree.to_dict()
        return smallest

    leaf = leaves.popleft()

    # Does this element need to be crafted?
    if leaf.element in GIVEN_ELEMENTS:
        # If not, just move on
        smallest = smallest_tree_naive_helper(working_tree, leaves, smallest)
        leaves.appendleft(leaf)
        return smallest

    # Otherwise, try all recipes for this item
    for recipe in get_recipes_for(leaf.element):  # For every recipe
        new1, new2 = leaf.load_recipe(recipe)  # load the recipe

        # Queue any new leaves
        if new1:
            leaves.append(leaf.ing1)
        if new2:
            leaves.append(leaf.ing2)

        # Run the helper on the expanded tree
        smallest = smallest_tree_naive_helper(working_tree, leaves, smallest)

        # Undo loading the recipe
        if new2:
            working_tree.remove(leaf.ing2.element)
            leaves.pop()  # Remember to remove from leaf deque
        if new1:
            working_tree.remove(leaf.ing1.element)
            leaves.pop()  # Remember to remove from leaf deque
        leaf.ing1 = None
        leaf.ing2 = None

    leaves.appendleft(leaf)
    return smallest


def smallest_tree_naive(target_element: str) -> dict[str, tuple[str, str]]:
    working_tree = SimpleCraftingTree(target_element)
    leaves = deque()
    leaves.append(working_tree.root)
    smallest = {}
    return smallest_tree_naive_helper(working_tree, leaves, smallest)


if __name__ == "__main__":
    start = time.time_ns()
    print(smallest_tree_naive("Lava"))
    print(f"Smallest(Naive) took {time.time_ns() - start} ns")

    start = time.time_ns()
    print(basic_tree("Lava"))
    print(f"Basic took {time.time_ns() - start} ns")

