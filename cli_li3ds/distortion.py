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
    if len(disto_nodes) != 1:
        err = 'CalibDistortion XML Node does not have a single child'
        raise RuntimeError(err)

    disto_node = disto_nodes[0]
    type_ = disto_node.tag
    if type_ == 'ModUnif':
        type_ = xmlutil.child(disto_node, 'TypeModele').text.strip()
    fn, i = _distortion_data_reader(type_)
    return fn(disto_node, i)


def _register(*types):
    """
    To use as a decorator for registering distortion data reader functions.
    """
    def _wrapper(fn):
        for i, type_ in enumerate(types):
            _distortion_data_readers[type_] = (fn, i)
        return fn
    return _wrapper


def _distortion_data_reader(type_):
    """
    Get the distortion info reader function for the given type.

    :param type_: the type of model.
    """
    if type_ not in _distortion_data_readers:
        err = 'Error: type "{}" is unknown.'.format(type_)
        raise RuntimeError(err)
    return _distortion_data_readers[type_]


def _read_n_values(node, n, name):
    nodes_iter = itertools.islice(node.iter(name), 0, n)
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


def _read_parameters(node, nstates, nparams):
    states = _read_n_values(node, nstates, 'Etats')
    params = _read_n_values(node, nparams, 'Params')
    return states, params


@_register(
    'eModelePolyDeg2',
    'eModelePolyDeg3',
    'eModelePolyDeg4',
    'eModelePolyDeg5',
    'eModelePolyDeg6',
    'eModelePolyDeg7'
)
def poly_deg_data_reader(node, i):
    """
    Get the distortion parameters from the ModUnif/eModelePolyDegX XML node.

    :param node: the ``ModUnif`` XML node.
    """
    type_ = 'poly_{}'.format(i+2)
    nparams = [6, 14, 24, 36, 50, 66]
    states, params = _read_parameters(node, 3, nparams[i])
    parameters = {
        'S': states[0],
        'C': states[1:3],
        'p': params,
    }
    return type_, parameters


@_register('eModeleEbner')
def ebner_data_reader(node, i=0):
    """
    Get the distortion parameters
    from the ModUnif/eModeleEbner XML node.

    :param node: the ``ModUnif`` XML node.
    """
    states, params = _read_parameters(node, 1, 12)
    return 'poly_ebner', {'B': states[0], 'p': params}


@_register('eModeleDCBrown')
def d_c_brown_fisheye_10_5_5_data_reader(node, i=0):
    """
    Get the distortion parameters
    from the ModUnif/eModeleDCBrown XML node.

    :param node: the ``ModUnif`` XML node.
    """
    states, params = _read_parameters(node, 1, 14)
    return 'poly_brown', {'F': states[0], 'p': params}


@_register(
    'eModele_FishEye_10_5_5',
    'eModele_EquiSolid_FishEye_10_5_5'
)
def fisheye_10_5_5_data_reader(node, i):
    """
    Get the distortion parameters
    from the ModUnif/eModele_[EquiSolid_]FishEye_10_5_5 XML node.

    :param node: the ``ModUnif`` XML node.
    """
    types = ['fisheye_10_5_5', 'fisheye_10_5_5_equisolid']
    states, params = _read_parameters(node, 1, 24)
    parameters = {
        'F': states[0],
        'C': params[0:2],
        'R': params[2:7],
        'P': params[12:14],
        'l': params[22:24],
        }
    return types[i], parameters


@_register('ModRad')
def rad_data_reader(node, i=0):
    """
    Get the distortion parameters from the ModRad XML node.

    :param node: the ``ModRad`` XML node.
    """
    R = xmlutil.children_float(node, 'CoeffDist')
    C = xmlutil.child_floats_split(node, 'CDist')
    type_ = 'poly_radial_{}'.format(1+2*len(R))
    return type_, {'C': C, 'R': R}


@_register('ModPhgrStd')
def phgr_std_data_reader(node, i=0):
    """
    Get the distortion parameters from the ModPhgrStd XML node.

    :param node: the ``ModPhgrStd`` XML node.
    """
    type_, parameters = rad_data_reader(
        xmlutil.child(node, 'RadialePart'))
    parameters['P'] = xmlutil.child_floats(node, '[P1,P2]', 0)
    parameters['b'] = xmlutil.child_floats(node, '[b1,b2]', 0)
    return type_+'_Pb', parameters
