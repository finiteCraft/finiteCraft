import time
from collections import deque
from copy import deepcopy
import librarian
import logging

from structures import *

log = logging.getLogger("Tree Generation")
logging.basicConfig()
log.setLevel(logging.DEBUG)
GIVEN_ELEMENTS: set[str] = {"Water", "Fire", "Wind", "Earth"}


def get_recipes_for(element: str) -> list[tuple[str, str]]:
    # return RECIPES[element]
    d = librarian.query_data(element, "search")
    if d is None:
        return []
    return d["crafted_by"]


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


def h_smallest_tree_bp(working_tree: dict[str: tuple[str, str] | None],
                                  leaves: deque[str],
                                  smallest: dict[str, tuple[str, str] | None]) -> dict[str, tuple[str, str] | None]:
    """
    Method BP (Basic Pruning)
    ---
    A basic smallest tree search that prunes branches that get larger than current smallest tree.
    """
    # PRUNING BLOCK
    if len(smallest) and len(working_tree) > len(smallest):
        log.debug(f"Pruned Branch! Breadcrumb count: {len(working_tree)}")
        leaves.clear()
        return smallest  # There's no way this tree is gonna be smaller, prune this branch
    # END PRUNING BLOCK

    if not len(leaves):  # Have we completed a tree?
        # yes, compare against current smallest
        if len(smallest) == 0 or compare_trees(working_tree, smallest) < 0:
            log.debug(f"Found new smallest tree: {working_tree}")
            return deepcopy(working_tree)
        return smallest

    leaf = leaves.popleft()

    # Is the element already a part of the tree?
    # AKA has it already been crafted?
    if leaf in working_tree:
        return h_smallest_tree_bp(working_tree, leaves, smallest)

    # Initialize leaf in tree
    working_tree[leaf] = None

    # Does this element need to be crafted?
    if leaf in GIVEN_ELEMENTS:
        # If not, just move on
        smallest = h_smallest_tree_bp(working_tree, leaves, smallest)
        working_tree.pop(leaf)  # Make sure to remove from the tree at the end
        return smallest

    # Otherwise, try all recipes for this item
    for recipe in get_recipes_for(leaf):  # For every recipe...
        working_tree[leaf] = (recipe[0], recipe[1])  # Load recipe
        # then queue any new leaves
        # (duplicates get filtered out above code)
        leaves.append(recipe[0])
        leaves.append(recipe[1])

        # Run the helper on the expanded tree.
        # leaves will automatically clear themselves from the queue
        smallest = h_smallest_tree_bp(working_tree, leaves, smallest)

    # Remove the leaf from tree
    working_tree.pop(leaf)
    return smallest

def h_smallest_tree_ld(working_tree: dict[str: tuple[str, str] | None],
                                  leaves: deque[str],
                                  smallest: dict[str, tuple[str, str] | None]) -> dict[str, tuple[str, str] | None]:
    """
    Method LD (Leaf Depth)
    ---
    More intelligent pruning that uses the max of the working tree and the depth
    of the element when pruning. This should avoid using elements that obviously
    have too great a depth.
    """
    # log.debug(f"Working Tree - {working_tree}")
    if not len(leaves):  # Have we completed a tree?
        # yes, compare against current smallest
        if len(smallest) == 0 or compare_trees(working_tree, smallest) < 0:
            log.info(f"Found new smallest tree: {working_tree}")
            return deepcopy(working_tree)
        return smallest

    leaf = leaves.popleft()
    leaf_depth = librarian.query_data(leaf, "search")["depth"]

    # PRUNING BLOCK
    # the +1 comes from the minimum number of breadcrumbs for a element of a given depth.
    if len(smallest) and max(len(working_tree), leaf_depth + 1) > len(smallest):
        if leaf_depth + 1 > len(smallest) >= len(working_tree):  # Notify when the change actually helped
            log.info("LD optimization utilized!")
        log.debug(f"Pruned Branch! Breadcrumb count: {len(working_tree)}")
        leaves.clear()
        return smallest  # There's no way this tree is gonna be smaller, prune this branch
    # END PRUNING BLOCK

    # Is the element already a part of the tree?
    # AKA has it already been crafted?
    if leaf in working_tree:
        return h_smallest_tree_ld(working_tree, leaves, smallest)

    # Initialize leaf in tree
    working_tree[leaf] = None

    # Does this element need to be crafted?
    if leaf in GIVEN_ELEMENTS:
        # If not, just move on
        smallest = h_smallest_tree_ld(working_tree, leaves, smallest)
        working_tree.pop(leaf)  # Make sure to remove from the tree at the end
        return smallest

    # Otherwise, try all recipes for this item
    recipes = get_recipes_for(leaf)
    for i, recipe in enumerate(recipes):  # For every recipe...
        working_tree[leaf] = (recipe[0], recipe[1])  # Load recipe
        log.debug(f"Using recipe {i + 1}/{len(recipes)} for {leaf} on tree {working_tree}")
        # then queue any new leaves
        # (duplicates get filtered out above code)
        leaves.append(recipe[0])
        leaves.append(recipe[1])

        # Run the helper on the expanded tree.
        # leaves will automatically clear themselves from the queue
        smallest = h_smallest_tree_ld(working_tree, leaves, smallest)

    # Remove the leaf from tree
    working_tree.pop(leaf)
    return smallest

dc1_root_depth = -1
def h_smallest_tree_dc1(working_tree: dict[str: tuple[str, str] | None],
                                  leaves: deque[str],
                                  smallest: dict[str, tuple[str, str] | None]) -> dict[str, tuple[str, str] | None]:
    """
    Method DC1 (Depth Cap 1)
    ---
    Prunes elements whose depth is greater than the target element.
    It may be possible that this doesn't return the optimal tree,
    but we are 99.99% confident that it will. Even if it doesn't,
    it will return a really good tree.
    """
    # log.debug(f"Working Tree - {working_tree}")
    if not len(leaves):  # Have we completed a tree?
        # yes, compare against current smallest
        if len(smallest) == 0 or compare_trees(working_tree, smallest) < 0:
            log.info(f"Found new smallest tree: {working_tree}")
            return deepcopy(working_tree)
        return smallest

    leaf = leaves.popleft()
    leaf_depth = librarian.query_data(leaf, "search")["depth"]

    # PRUNING BLOCK
    if len(working_tree) > 0 and leaf_depth >= dc1_root_depth:
        log.debug("DC1 optimization utilized")
        leaves.clear()
        return smallest  # There's no way this tree is gonna be smaller, prune this branch


    # the +1 comes from the minimum number of breadcrumbs for a element of a given depth.
    if len(smallest) and max(len(working_tree), leaf_depth + 1) > len(smallest):
        if leaf_depth + 1 > len(smallest) >= len(working_tree):  # Notify when the change actually helped
            log.debug("LD optimization utilized!")
        log.debug(f"Pruned Branch! Breadcrumb count: {len(working_tree)}")
        leaves.clear()
        return smallest  # There's no way this tree is gonna be smaller, prune this branch
    # END PRUNING BLOCK

    # Is the element already a part of the tree?
    # AKA has it already been crafted?
    if leaf in working_tree:
        return h_smallest_tree_dc1(working_tree, leaves, smallest)

    # Initialize leaf in tree
    working_tree[leaf] = None

    # Does this element need to be crafted?
    if leaf in GIVEN_ELEMENTS:
        # If not, just move on
        smallest = h_smallest_tree_dc1(working_tree, leaves, smallest)
        working_tree.pop(leaf)  # Make sure to remove from the tree at the end
        return smallest

    # Otherwise, try all recipes for this item
    recipes = get_recipes_for(leaf)
    for i, recipe in enumerate(recipes):  # For every recipe...
        working_tree[leaf] = (recipe[0], recipe[1])  # Load recipe
        log.debug(f"Using recipe {i + 1}/{len(recipes)} for {leaf} on tree {working_tree}")
        # then queue any new leaves
        # (duplicates get filtered out above code)
        leaves.append(recipe[0])
        leaves.append(recipe[1])

        # Run the helper on the expanded tree.
        # leaves will automatically clear themselves from the queue
        smallest = h_smallest_tree_dc1(working_tree, leaves, smallest)

    # Remove the leaf from tree
    working_tree.pop(leaf)
    return smallest


def h_smallest_tree_dc2(working_tree: dict[str: tuple[str, str] | None],
                                  leaves: deque[str],
                                  smallest: dict[str, tuple[str, str] | None]) -> dict[str, tuple[str, str] | None]:
    """
    Method DC2 (Depth Cap 2)
    ---
    Prunes elements whose depth is greater than the target element.
    It may be possible that this doesn't return the optimal tree,
    but we are 99.99% confident that it will. Even if it doesn't,
    it will return a really good tree.
    """
    # log.debug(f"Working Tree - {working_tree}")
    if not len(leaves):  # Have we completed a tree?
        # yes, compare against current smallest
        if len(smallest) == 0 or compare_trees(working_tree, smallest) < 0:
            log.info(f"Found new smallest tree: {working_tree}")
            return deepcopy(working_tree)
        return smallest

    leaf = leaves.popleft()
    leaf_depth = librarian.query_data(leaf, "search")["depth"]

    # PRUNING BLOCK
    # the +1 comes from the minimum number of breadcrumbs for a element of a given depth.
    if len(smallest) and max(len(working_tree), leaf_depth + 1) > len(smallest):
        if leaf_depth + 1 > len(smallest) >= len(working_tree):  # Notify when the change actually helped
            log.debug("LD optimization utilized!")
        log.debug(f"Pruned Branch! Breadcrumb count: {len(working_tree)}")
        leaves.clear()
        return smallest  # There's no way this tree is gonna be smaller, prune this branch
    # END PRUNING BLOCK

    # Is the element already a part of the tree?
    # AKA has it already been crafted?
    if leaf in working_tree:
        return h_smallest_tree_dc2(working_tree, leaves, smallest)

    # Initialize leaf in tree
    working_tree[leaf] = None

    # Does this element need to be crafted?
    if leaf in GIVEN_ELEMENTS:
        # If not, just move on
        smallest = h_smallest_tree_dc2(working_tree, leaves, smallest)
        working_tree.pop(leaf)  # Make sure to remove from the tree at the end
        return smallest

    # Otherwise, try all recipes for this item
    recipes = get_recipes_for(leaf)
    depth_thresh = leaf_depth + 0  # Option to change the depth_thresh
    for i, recipe in enumerate(recipes):  # For every recipe...
        ing1 = recipe[0]
        ing2 = recipe[1]
        if (librarian.query_data(ing1, "search")["depth"] >= depth_thresh or
            librarian.query_data(ing2, "search")["depth"] >= depth_thresh):
            log.debug(f"DC2 optimization utililzed! {leaf} = {ing1} + {ing2}")
            continue

        working_tree[leaf] = (ing1, ing2)  # Load recipe
        log.debug(f"Using recipe {i + 1}/{len(recipes)} for {leaf} on tree {working_tree}")
        # then queue any new leaves
        # (duplicates get filtered out above code)
        leaves.append(ing1)
        leaves.append(ing2)

        # Run the helper on the expanded tree.
        # leaves will automatically clear themselves from the queue
        smallest = h_smallest_tree_dc2(working_tree, leaves, smallest)

    # Remove the leaf from tree
    working_tree.pop(leaf)
    return smallest


def smallest_tree(target_element: str) -> dict[str, tuple[str, str]]:
    """
    Returns the smallest crafting tree for the given element.
    Takes into account the available recipes and what items are
    already made by the user.
    :param target_element: the items to craft
    :return: the optimal crafting tree
    """
    global dc1_root_depth

    log.info("Starting tree search")
    working_tree = {}
    leaves = deque()
    leaves.append(target_element)
    smallest = {}
    # dc1_root_depth = librarian.query_data(target_element, "search")["depth"]
    tree = h_smallest_tree_dc2(working_tree, leaves, smallest)
    log.info("Tree Search Complete")
    return tree


if __name__ == "__main__":
    librarian.init()

    start = time.time_ns()
    # time.sleep(0.5)
    print(basic_tree("Stone"))
    print(f"Basic took {time.time_ns() - start} ns")

    start = time.time_ns()
    # time.sleep(0.5)
    print(smallest_tree("Stone"))
    print(f"Smallest took {time.time_ns() - start} ns")
