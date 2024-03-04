class CraftTreeNode:
    def __init__(self, tree, element: str):
        self.element = element
        self.ing1: CraftTreeNode | None = None
        self.ing2: CraftTreeNode | None = None
        self.tree = tree  # can't type cast it because SimpleCraftingTree gets declared afterward

    def load_recipe(self, recipe: tuple[str, str]) -> tuple[bool, bool]:
        """
        Loads the given recipe into this node, and updates the overarching tree.
        :param recipe: the recipe to load
        :return: whether the two ingredients are newly generated nodes
        """
        self.ing1, new1 = self.tree.register_element(recipe[0])
        self.ing2, new2 = self.tree.register_element(recipe[1])
        return new1, new2

    def is_expanded(self) -> bool:
        if self.ing1:
            return True
        return False


class SimpleCraftingTree:

    def __init__(self, target_element: str):
        self.target_element = target_element
        self.map: dict[str, CraftTreeNode] = {target_element: CraftTreeNode(self, target_element)}
        self.root = self.map[target_element]

    def register_element(self, element: str) -> tuple[CraftTreeNode, bool]:
        """
        Similar to get_node(), but will register the element if it doesn't
        already exist. Returns a reference to the node and whether the
        node was new or not
        :param element: the element to register in the tree
        :return: the node representing that element and whether the node was newly generated
        """
        new = False
        if element not in self.map:
            self.map[element] = CraftTreeNode(self, element)
            new = True
        return self.map[element], new

    def breadcrumbs(self):
        return self.map.keys()

    def get_node(self, element: str) -> CraftTreeNode | None:
        if element in self.map:
            return self.map[element]
        return None
