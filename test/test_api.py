import pytest

from cli_li3ds import api


def create_obj_class(t):
    class _ApiObj(api.ApiObj):
        key = ('name',)
        type_ = t

    return _ApiObj


@pytest.fixture
def apiobj(scope='module'):
    cls = create_obj_class('test')
    obj = cls(keys=('name', 'parameters'), obj={'name': 'foo'}, parameters=[{'k1': 'v1'}])
    return obj


@pytest.fixture
def transfo(scope='module'):
    sensor = api.Sensor(name='sensor')
    source = api.Referential(name='source', sensor=sensor)
    target = api.Referential(name='target', sensor=sensor)
    return api.Transfo(name='transfo', source=source, target=target)


def test_apiobj(apiobj):
    assert apiobj.type_ == 'test'
    assert apiobj.obj['name'] == 'foo'
    assert apiobj.obj['parameters'] == [{'k1': 'v1'}]


def test_eq_same_id(apiobj):
    assert apiobj == apiobj


def test_eq_different_type():
    cls1 = create_obj_class('sensor')
    obj1 = cls1(keys=('name',), name='foo')
    cls2 = create_obj_class('referential')
    obj2 = cls2(keys=('name',), name='foo')
    assert obj1 != obj2


def test_eq_simple():
    Sensor = create_obj_class('sensor')
    sensor1 = Sensor(keys=('name',), name='foo')
    sensor2 = Sensor(keys=('name',), name='foo')
    assert sensor1 == sensor2


def test_eq_complex():

    # create transfo tree 1
    sen1 = api.Sensor(name='sen')
    src1 = api.Referential(name='src', sensor=sen1)
    tgt1 = api.Referential(name='dst', sensor=sen1)
    tra1 = api.Transfo(name='tra', source=src1, target=tgt1)
    ttr1 = api.Transfotree(transfos=[tra1], name='ttr')

    # create transfo tree 2
    sen2 = api.Sensor(name='sen')
    src2 = api.Referential(name='src', sensor=sen2)
    tgt2 = api.Referential(name='dst', sensor=sen2)
    tra2 = api.Transfo(name='tra', source=src2, target=tgt2)
    ttr2 = api.Transfotree(transfos=[tra2], name='ttr')

    assert ttr1 == ttr2


def test_lookup(transfo):
    sensor = api.Sensor(name='sensor')
    referential = api.Referential(name='target', sensor=sensor)

    res = transfo.lookup(referential)
    assert res is not None
    assert res.type_ == 'referential'
    assert res.obj['name'] == 'target'
    assert res.objs['sensor'].obj['name'] == 'sensor'


def test_lookup_deeper(transfo):
    sensor = api.Sensor(name='sensor')
    res = transfo.lookup(sensor)
    assert res is not None
    assert res.type_ == 'sensor'
    assert res.obj['name'] == 'sensor'
