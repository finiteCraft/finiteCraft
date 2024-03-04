from structures import *
from collections import deque
from copy import deepcopy

# This is a placeholder for now.
# Real recipes should be loaded from file
RECIPES: dict[str, tuple[str, str]] = {}

def generate_all_trees(target_craft: str) -> list[CraftingTree]:
    """
    Generates all possible crafting trees that lead to target craft.

    This is horribly inefficient, and creates tons of duplicate data.
    I'm considering editing the CraftingTree data structure to be able
    to hold the various possibly recipes inside of it. It would require
    a complete redesign of the whole data structure, but I think it's
    gonna benefit us in the long run with both time/space saved and
    ease of use. It might even help us when we start getting to optimization.
    :param target_craft:
    :return:
    """
    completed_trees: list[CraftingTree] = []
    q: deque[CraftingTree] = deque()
    q.append(CraftingTree(target_craft))

    while len(q) > 0:
        tree = q.popleft()
        changed = False

        for i in range(len(tree.leaves)):
            node = tree.leaves[i]
            if node.craft in "Water;Fire;Earth;Wind":
                i += 1
                continue

            changed = True
            for recipe in RECIPES[node.craft]:
                nt = deepcopy(tree)  # Create a copy of the tree
                nt_node = nt.leaves[i]
                nt_node.load_recipe(recipe)  # expand the selected node downwards
                # Update the leaves of the new tree
                nt.leaves.pop(i)
                nt.leaves.append(nt_node.ing1)
                nt.leaves.append(nt_node.ing2)

                q.append(nt)  # Add the new tree onto the deque

            i += 1

        if changed:
            del tree  # don't need to carry this around
        else:
            completed_trees.append(tree)  # tree is finished

    return completed_trees

