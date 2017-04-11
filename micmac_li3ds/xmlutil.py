import xml.etree.ElementTree

def root(file, name):
    tree = xml.etree.ElementTree.parse(file)
    root_node = tree.getroot()
    if root_node.tag != name:
        err = 'Error: root tag differs from "{}" in XML'.format(name)
        raise RuntimeError(err)
    return root_node

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

def child_float(parent, name):
    node = child(parent, name)
    try:
        return float(node.text)
    except ValueError:
        err = 'Error: {} tag ' \
          'includes non-parseable numbers in XML'.format(name)
        raise RuntimeError(err)

def child_bool(parent, name):
    node = child(parent, name)
    try:
        return bool(node.text)
    except ValueError:
        err = 'Error: {} tag ' \
          'includes non-parseable boolean in XML'.format(name)
        raise RuntimeError(err)

def child_floats(parent, name, names):
    node = child(parent,name)
    return list(map(lambda n : childFloat(node,n), names))
