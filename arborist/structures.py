from copy import deepcopy
from collections import deque


class CraftTreeNode:
    def __init__(self, craft: str):
        self.craft = craft
        self.ing1: CraftTreeNode | None = None
        self.ing2: CraftTreeNode | None = None

    def __deepcopy__(self, memodict={}):
        cpy = CraftTreeNode(self.craft)
        if self.ing1:
            cpy.ing1 = deepcopy(self.ing1)
            cpy.ing2 = deepcopy(self.ing2)
        return cpy

    def load_recipe(self, recipe: tuple[str, str]):
        self.ing1 = CraftTreeNode(recipe[0])
        self.ing2 = CraftTreeNode(recipe[1])


class CraftingTree:

    def __init__(self, target_craft: str):
        self.root = CraftTreeNode(target_craft)
        self.leaves = [self.root]
        self.breadcrumbs = set()
        self.breadcrumbs.add(target_craft)

    def __deepcopy__(self):
        cpy = CraftingTree(self.root.craft)
        cpy.root = deepcopy(self.root)
        cpy.leaves = []
        cpy.breadcrumbs = deepcopy(self.breadcrumbs)

        q: deque[CraftTreeNode] = deque()
        q.append(cpy.root)

        # Perform a levelorder traversal of tree to rediscover leaves
        while len(q):
            node = q.popleft()
            if not node.ing1:
                cpy.leaves.append(node)
            else:
                q.append(node.ing1)
                q.append(node.ing2)

        return cpy
