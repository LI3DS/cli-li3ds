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


def child_int(parent, name):
    node = child(parent, name)
    try:
        return int(node.text)
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


def child_floats(parent, name):
    beg = name.find('[')
    end = name.rfind(']')
    if beg is -1 or end is -1:
        err = 'Error: {} has no []-enclosed tag list'.format(name)
        raise RuntimeError(err)
    prefix = name[0:beg]
    names = name[beg+1:end].split(',')
    suffix = name[end+1:len(name)]
    return list(map(lambda n: child_float(parent, prefix+n+suffix), names))
