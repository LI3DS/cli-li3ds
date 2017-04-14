import xml.etree.ElementTree


def root(filename, name):
    tree = xml.etree.ElementTree.parse(filename)
    root_node = tree.getroot()
    if root_node.tag != name:
        err = 'Error: root tag differs from "{}" in XML file "{}"' \
            .format(name, filename)
        raise RuntimeError(err)
    return root_node


def child(parent, name, default=None):
    child_node = parent.find(name)
    if default is None and child_node is None:
        err = 'Error: no tag "{}" in XML tag "{}"'.format(name, parent.tag)
        raise RuntimeError(err)
    return child_node


def children(parent, name):
    child_nodes = parent.findall(name)
    if not child_nodes:
        err = 'Error: no tag "{}" in XML tag "{}"'.format(name, parent.tag)
        raise RuntimeError(err)
    return child_nodes


def child_check(parent, name, value):
    node = child(parent, name)
    if node.text.strip() != value:
        err = 'Error: "{}" tag does not have the expected value "{}" ' \
          'in XML tag "{}"'.format(name, value, parent.tag)
        raise RuntimeError(err)


def child_float(parent, name, default=None):
    node = child(parent, name, default)
    if node is None:
        return default
    try:
        return float(node.text)
    except ValueError:
        err = 'Error: "{}" tag includes non-parseable numbers ' \
          'in XML tag "{}"'.format(name, parent.tag)
        raise RuntimeError(err)


def children_float(parent, name):
    nodes = children(parent, name)
    try:
        return [float(node.text) for node in nodes]
    except ValueError:
        err = 'Error: "{}" tag includes non-parseable numbers ' \
          'in XML tag "{}"'.format(name, parent.tag)
        raise RuntimeError(err)


def child_int(parent, name, default=None):
    node = child(parent, name, default)
    if node is None:
        return default
    try:
        return int(node.text)
    except ValueError:
        err = 'Error: "{}" tag includes a non-parseable integer ' \
          'in XML tag "{}"'.format(name, parent.tag)
        raise RuntimeError(err)


def child_bool(parent, name, default=None):
    node = child(parent, name, default)
    if node is None:
        return default
    try:
        return bool(node.text)
    except ValueError:
        err = 'Error: "{}" tag includes non-parseable boolean ' \
          'in XML tag "{}"'.format(name, parent.tag)
        raise RuntimeError(err)


def child_floats(parent, name, default=None):
    beg = name.find('[')
    end = name.rfind(']')
    if beg is -1 or end is -1:
        err = 'Error: "{}" tag has no []-enclosed tag list'.format(name)
        raise RuntimeError(err)
    prefix = name[0:beg]
    names = name[beg+1:end].split(',')
    suffix = name[end+1:len(name)]
    return [child_float(parent, prefix+n+suffix, default) for n in names]


def child_floats_split(parent, name):
    node = child(parent, name)
    try:
        return [float(v) for v in node.text.split()]
    except ValueError:
        err = 'Error: "{}" tag includes non-parseable numbers ' \
          'in XML tag "{}"'.format(name, parent.tag)
        raise RuntimeError(err)
