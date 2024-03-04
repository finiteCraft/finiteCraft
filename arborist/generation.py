from structures import *
from collections import deque
from copy import deepcopy

# This is a placeholder for now.
# Real recipes should be loaded from file
RECIPES: dict[str, list[tuple[str, str]]] = {}

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

        recipe = RECIPES[node.element][0]  # Just choosing first-found recipe
        new1, new2 = node.load_recipe(recipe)
        if new1:
            leaves.append(node.ing1)
        if new2:
            leaves.append(node.ing2)

    return tree

