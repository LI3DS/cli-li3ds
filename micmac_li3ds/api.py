import requests


def _create_object(obj, url, api_key):
    headers = {'X-API-KEY': api_key}
    resp = requests.post(url, json=obj, headers=headers)
    if resp.status_code == 201:
        obj = resp.json()
        return obj[0]
    err = 'Adding object failed (status code: {})'.format(
          resp.status_code)
    raise RuntimeError(err)


def _get_object_by_id(obj_id, url, api_key):
    url = url + '/{:d}/'.format(obj_id)
    headers = {'X-API-KEY': api_key, 'Accept': 'application/json'}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        obj = resp.json()
        return obj[0]
    if resp.status_code == 404:
        return None
    err = 'Getting object failed (status code: {})'.format(
          resp.status_code)
    raise RuntimeError(err)


def get_referential(referential_id, api_url, api_key):
    """
    Get a referential by its id.
    """
    url = api_url.rstrip('/') + '/referentials'
    return _get_object_by_id(referential_id, url, api_key)


def create_referential(referential, api_url, api_key):
    """
    Create a referential.
    """
    url = api_url.rstrip('/') + '/referentials/'
    return _create_object(referential, url, api_key)


def get_sensor(sensor_id, api_url, api_key):
    """
    Get a sensor by its id.
    """
    url = api_url.rstrip('/') + '/sensors'
    return _get_object_by_id(sensor_id, url, api_key)


def create_sensor(sensor, api_url, api_key):
    """
    Create a sensor.
    """
    url = api_url.rstrip('/') + '/sensors/'
    return _create_object(sensor, url, api_key)


def get_transfo(transfo_id, api_url, api_key):
    """
    Get a transfo by its id.
    """
    url = api_url.rstrip('/') + '/transfos'
    return _get_object_by_id(transfo_id, url, api_key)


def create_transfo(transfo, api_url, api_key):
    """
    Create a transfo.
    """
    url = api_url.rstrip('/') + '/transfos/'
    return _create_object(transfo, url, api_key)


def get_transfotree(transfotree_id, api_url, api_key):
    """
    Get a transfotree by its id.
    """
    url = api_url.rstrip('/') + '/transfotrees'
    return _get_object_by_id(transfotree_id, url, api_key)


def create_transfotree(transfotree, api_url, api_key):
    """
    Create a transfotree.
    """
    url = api_url.rstrip('/') + '/transfotrees/'
    return _create_object(transfotree, url, api_key)
