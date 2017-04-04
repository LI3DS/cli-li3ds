def child(parent, name):
    child_node = parent.find(name)
    if child_node is None:
        err = 'Error: no tag "{}" in XML'.format(name)
        raise RuntimeError(err)
    return child_node


def children(parent, name):
    child_nodes = parent.findall(name)
    if not child_nodes:
        err = 'Error: no tag "{}" in XML'.format(name)
        raise RuntimeError(err)
    return child_nodes
