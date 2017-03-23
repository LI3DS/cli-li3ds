def child(parent, name):
    child_node = parent.find(name)
    if child_node is None:
        err = 'Error: no {} tag in autocal file'.format(name)
        raise RuntimeError(err)
    return child_node
