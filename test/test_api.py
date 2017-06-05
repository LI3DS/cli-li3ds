import pytest

from micmac_li3ds import api


@pytest.fixture
def apiobj(scope='module'):
    obj = api.ApiObj(
        'transfo',
        keys=('id', 'name', 'parameters'),
        obj={'name': 'transfo'},
        parameters=[{'k1': 'v1', 'k2': 'v2'}]
    )

    source_ref = api.ApiObj(
        'referential',
        keys=('name',),
        obj={'name': 'source_ref'}
    )
    source_ref.objs = {
        'sensor': api.ApiObj(
            'sensor',
            keys=('name',),
            obj={'name': 'sensor'}
        )
    }

    target_ref = api.ApiObj(
        'referential',
        keys=('name',),
        obj={'name': 'target_ref'}
    )
    target_ref.objs = {
        'sensor': api.ApiObj(
            'sensor',
            keys=('name',),
            obj={'name': 'sensor'}
        )
    }

    obj.objs = {
        'source': source_ref,
        'target': target_ref,
    }
    return obj


def test_apiobj(apiobj):
    assert apiobj.type_ == 'transfo'
    assert apiobj.obj['name'] == 'transfo'
    assert apiobj.obj['parameters'] == [{'k1': 'v1', 'k2': 'v2'}]


def test_eq_same_id(apiobj):
    assert apiobj == apiobj


def test_eq_different_type():
    obj1 = api.ApiObj('sensor', keys=('name',), name='foo')
    obj2 = api.ApiObj('referential', keys=('name',), name='foo')
    assert obj1 != obj2


def test_eq_simple():
    sensor1 = api.ApiObj('sensor', keys=('name',), name='sensor')
    sensor2 = api.ApiObj('sensor', keys=('name',), name='sensor')
    assert sensor1 == sensor2


def test_eq_complex():
    keys = ('name',)

    # create transfo tree 1
    sen1 = api.ApiObj('sensor', keys=keys, name='sen')
    tra1 = api.ApiObj('transfo', keys=keys, name='tra')
    src1 = api.ApiObj('referential', keys=keys, name='src')
    src1.objs = {'sensor': sen1}
    tgt1 = api.ApiObj('referential', keys=keys, name='tgt')
    tgt1.objs = {'sensor': sen1}
    tra1.objs = {'source': src1, 'target': tgt1}
    ttr1 = api.ApiObj('transfotree', keys=keys, name='ttr')
    ttr1.arrays['transfos'] = [tra1]

    # create transfo tree 2
    sen2 = api.ApiObj('sensor', keys=keys, name='sen')
    tra2 = api.ApiObj('transfo', keys=keys, name='tra')
    src2 = api.ApiObj('referential', keys=keys, name='src')
    src2.objs = {'sensor': sen2}
    tgt2 = api.ApiObj('referential', keys=keys, name='tgt')
    tgt2.objs = {'sensor': sen2}
    tra2.objs = {'source': src2, 'target': tgt2}
    ttr2 = api.ApiObj('transfotree', keys=keys, name='ttr')
    ttr2.arrays['transfos'] = [tra2]

    assert ttr1 == ttr2


def test_lookup(apiobj):
    referential = api.ApiObj(
        'referential',
        keys=('name',),
        name='target_ref'
    )

    res = apiobj.lookup(referential)
    assert res is None

    referential.objs = {
        'sensor': api.ApiObj(
            'sensor',
            keys=('name',),
            name='sensor'
        )
    }

    res = apiobj.lookup(referential)
    assert res is not None
    assert res.type_ == 'referential'
    assert res.obj['name'] == 'target_ref'
    assert res.objs['sensor'].obj['name'] == 'sensor'


def test_lookup_deeper(apiobj):
    sensor = api.ApiObj(
        'sensor',
        keys=('name',),
        name='sensor'
    )
    res = apiobj.lookup(sensor)
    assert res is not None
    assert res.type_ == 'sensor'
    assert res.obj['name'] == 'sensor'
