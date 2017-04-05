import itertools

from . import util

_distortion_data_readers = {}


def read_info(mod_unif_node):
    """
    Read the distortion info from the ``ModUnif`` XML node. Return a tuple
    of three elements: (type of model, list of states, list of params).

    :param mod_unif_node: the ``ModUnif`` XML node.
    """
    type_modele_node = util.child(mod_unif_node, 'TypeModele')
    typ = type_modele_node.text
    states, params = _distortion_data_reader(typ)(mod_unif_node)
    return typ, states, params


def _register(*types):
    """
    To use as a decocator for registering distortion data reader functions.
    """
    def _wrapper(fn):
        for typ in types:
            _distortion_data_readers[typ] = fn
        return fn
    return _wrapper


def _distortion_data_reader(typ):
    """
    Get the distortion info reader function for the given type.

    :param typ: the type of model.
    """
    if typ not in _distortion_data_readers:
        err = 'Error: type "{}" is unknown.'.format(typ)
        raise RuntimeError(err)
    return _distortion_data_readers[typ]


def _read_n_values(mod_unif_node, n, name):
    nodes_iter = itertools.islice(mod_unif_node.iter(name), 0, n)
    try:
        values_iter = map(lambda n: float(n.text), nodes_iter)
    except ValueError:
        err = 'Error: tags "{}" include non-parseable numbers.'.format(name)
        raise RuntimeError(err)
    values = list(values_iter)
    if len(values) != n:
        err = 'Error: expected {:d} {}, got {:d}.'.format(n, name, len(values))
        raise RuntimeError(err)
    return values


def _read_n_states(mod_unif_node, n):
    return _read_n_values(mod_unif_node, n, 'Etats')


def _read_n_params(mod_unif_node, n):
    return _read_n_values(mod_unif_node, n, 'Params')


@_register('eModele_FishEye_10_5_5', 'eModele_EquiSolid_FishEye_10_5_5')
def fisheye_data_reader(mod_unif_node):
    """
    Get the distortion states and params from the ModUnif XML node. Return a
    tuple of 2 elements: the list of states and the list of params.

    :param mod_unif_node: the ``ModUnif`` XML node.
    """
    states = _read_n_states(mod_unif_node, 1)
    params = _read_n_params(mod_unif_node, 24)
    return states, params


@_register('eModelePolyDeg2')
def polydeg2_data_reader(mod_unif_node):
    """
    Get the distortion states and params from the ModUnif XML node. Return a
    tuple of 2 elements: the list of states and the list of params.

    :param mod_unif_node: the ``ModUnif`` XML node.
    """
    states = _read_n_states(mod_unif_node, 3)
    params = _read_n_params(mod_unif_node, 6)
    return states, params


@_register('eModelePolyDeg3')
def polydeg3_data_reader(mod_unif_node):
    """
    Get the distortion states and params from the ModUnif XML node. Return a
    tuple of 2 elements: the list of states and the list of params.

    :param mod_unif_node: the ``ModUnif`` XML node.
    """
    states = _read_n_states(mod_unif_node, 3)
    params = _read_n_params(mod_unif_node, 14)
    return states, params


@_register('eModelePolyDeg4')
def polydeg4_data_reader(mod_unif_node):
    """
    Get the distortion states and params from the ModUnif XML node. Return a
    tuple of 2 elements: the list of states and the list of params.

    :param mod_unif_node: the ``ModUnif`` XML node.
    """
    states = _read_n_states(mod_unif_node, 3)
    params = _read_n_params(mod_unif_node, 24)
    return states, params


@_register('eModelePolyDeg5')
def polydeg5_data_reader(mod_unif_node):
    """
    Get the distortion states and params from the ModUnif XML node. Return a
    tuple of 2 elements: the list of states and the list of params.

    :param mod_unif_node: the ``ModUnif`` XML node.
    """
    states = _read_n_states(mod_unif_node, 3)
    params = _read_n_params(mod_unif_node, 36)
    return states, params
