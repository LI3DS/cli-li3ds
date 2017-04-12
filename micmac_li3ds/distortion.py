import itertools

from . import xmlutil

_distortion_data_readers = {}


def read_info(calib_disto_node):
    """
    Read the distortion info from the ``CalibDistortion`` XML node.
    Return a tuple of two elements: (type of model, dict parameters).

    :param disto_node: the ``CalibDistortion`` XML node.
    """
    disto_nodes = xmlutil.children(calib_disto_node, '*')
    assert(len(disto_nodes) == 1)
    disto_node = disto_nodes[0]
    typ = disto_node.tag
    if typ == 'ModUnif':
        typ = xmlutil.child(disto_node, 'TypeModele').text.strip()
    return _distortion_data_reader(typ)(disto_node)


def _register(*types):
    """
    To use as a decorator for registering distortion data reader functions.
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


def _read_parameters(mod_unif_node, nstates, nparams):
    return {
        'states': _read_n_values(mod_unif_node, nstates, 'Etats'),
        'params': _read_n_values(mod_unif_node, nparams, 'Params'),
    }


@_register('eModele_FishEye_10_5_5')
def fisheye_10_5_5_data_reader(disto_node):
    """
    Get the distortion parameters
    from the ModUnif/eModele_FishEye_10_5_5 XML node.

    :param mod_unif_node: the ``ModUnif`` XML node.
    """
    return 'fisheye_10_5_5', _read_parameters(disto_node, 1, 24)


@_register('eModele_EquiSolid_FishEye_10_5_5')
def fisheye_10_5_5_equisolid_data_reader(disto_node):
    """
    Get the distortion parameters
    from the ModUnif/eModele_EquiSolid_FishEye_10_5_5 XML node.

    :param mod_unif_node: the ``ModUnif`` XML node.
    """
    return 'fisheye_10_5_5_equisolid', _read_parameters(disto_node, 1, 24)


@_register('eModelePolyDeg2')
def poly_2_data_reader(mod_unif_node):
    """
    Get the distortion parameters from the ModUnif/eModelePolyDeg2 XML node.

    :param mod_unif_node: the ``ModUnif`` XML node.
    """
    return 'poly_2', _read_parameters(mod_unif_node, 3, 6)


@_register('eModelePolyDeg3')
def poly_3_data_reader(disto_node):
    """
    Get the distortion parameters from the ModUnif/eModelePolyDeg3 XML node.

    :param mod_unif_node: the ``ModUnif`` XML node.
    """
    return 'poly_3', _read_parameters(disto_node, 3, 14)


@_register('eModelePolyDeg4')
def poly_4_data_reader(disto_node):
    """
    Get the distortion parameters from the ModUnif/eModelePolyDeg4 XML node.

    :param mod_unif_node: the ``ModUnif`` XML node.
    """
    return 'poly_4', _read_parameters(disto_node, 3, 24)


@_register('eModelePolyDeg5')
def poly_5_data_reader(disto_node):
    """
    Get the distortion parameters from the ModUnif/eModelePolyDeg5 XML node.

    :param disto_node: the ``ModUnif`` XML node.
    """
    return 'poly_5', _read_parameters(disto_node, 3, 36)


@_register('ModRad')
def poly_radial_data_reader(disto_node):
    """
    Get the distortion parameters from the ModRad XML node.

    :param disto_node: the ``ModRad`` XML node.
    """
    coef = xmlutil.children_float(disto_node, 'CoeffDist')
    typ = 'poly_radial_{}'.format(1+2*len(coef))
    return typ, {
        'pps': xmlutil.child_floats_split(disto_node, 'CDist'),
        'coef': coef,
    }


@_register('ModPhgrStd')
def poly_radial_p1p2_data_reader(disto_node):
    """
    Get the distortion parameters from the ModPhgrStd XML node.

    :param disto_node: the ``ModPhgrStd`` XML node.
    """
    typ, parameters = poly_radial_data_reader(
        xmlutil.child(disto_node, 'RadialePart'))
    parameters['p'] = xmlutil.child_floats(disto_node, '[P1,P2]')
    return typ+'_p1p2', parameters
