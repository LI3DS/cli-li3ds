import requests


def create_object(typ, obj, api_url, api_key):
    url = api_url.rstrip('/') + '/{}s/'.format(typ)
    headers = {'X-API-KEY': api_key}
    resp = requests.post(url, json=obj, headers=headers)
    if resp.status_code == 201:
        objs = resp.json()
        return objs[0]
    err = 'Adding object failed (status code: {})'.format(
          resp.status_code)
    raise RuntimeError(err)


def get_object_by_id(typ, obj_id, api_url, api_key):
    url = api_url.rstrip('/') + '/{}s/{:d}/'.format(typ, obj_id)
    headers = {'X-API-KEY': api_key, 'Accept': 'application/json'}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        objs = resp.json()
        return objs[0]
    if resp.status_code == 404:
        return None
    err = 'Getting object failed (status code: {})'.format(
          resp.status_code)
    raise RuntimeError(err)


def get_object_by_name(typ, obj_name, api_url, api_key):
    url = api_url.rstrip('/') + '/{}s/'.format(typ)
    headers = {'X-API-KEY': api_key, 'Accept': 'application/json'}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        objs = resp.json()
        try:
            obj = next(o for o in objs if o['short_name'] == obj_name)
        except StopIteration:
            return None
        return obj
    err = 'Getting object failed (status code: {})'.format(
          resp.status_code)
    raise RuntimeError(err)


def get_objects(typ, api_url, api_key):
    url = api_url.rstrip('/') + '/{}s/'.format(typ)
    headers = {'X-API-KEY': api_key, 'Accept': 'application/json'}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        objs = resp.json()
        return objs
    err = 'Getting object failed (status code: {})'.format(
          resp.status_code)
    raise RuntimeError(err)


def get_sensor_referentials(sensor_id, api_url, api_key):
    referentials = get_objects('referential', api_url, api_key)
    sensor_base_referential = None
    sensor_referentials = []
    for referential in referentials:
        if referential['sensor'] != sensor_id:
            continue
        if referential['root'] is True:
            if sensor_base_referential:
                err = 'Multiple base referentials ' \
                      'found for sensor {:d}'.format(sensor_id)
                raise RuntimeError(err)
            sensor_base_referential = referential
        else:
            sensor_referentials.append(referential)
    if not sensor_base_referential:
        err = 'No base referential found for sensor {:d}'.format(sensor_id)
        raise RuntimeError(err)
    return sensor_base_referential, sensor_referentials
