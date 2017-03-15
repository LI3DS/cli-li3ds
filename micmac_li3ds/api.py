import requests


def create_referential(ref_name, sensor_id, api_url, api_key):
    """
    Create a referential in the li3ds database.
    """
    referential = {
        'description': '',
        'name': ref_name,
        'root': True,
        'sensor': sensor_id,
        'srid': 0,
    }
    referentials_url = api_url.rstrip('/') + '/referentials/'
    headers = {'X-API-KEY': api_key}
    resp = requests.post(
        referentials_url, json=referential, headers=headers)
    if resp.status_code != 201:
        err = 'Adding referential failed (status code: {})'.format(
              resp.status_code)
        raise RuntimeError(err)
    return resp


def get_sensor(sensor_id, api_url, api_key):
    """
    Get the sensor whose id is sensor_id from the li3ds database.
    """
    sensor_url = api_url.rstrip('/') + '/sensors/{:d}/'.format(sensor_id)
    headers = {'X-API-KEY': api_key, 'Accept': 'application/json'}
    resp = requests.get(sensor_url, headers=headers)
    if resp.status_code == 200:
        sensors = resp.json()
        return sensors[0]
    if resp.status_code == 404:
        return None
    err = 'Getting sensor failed (status code: {})'.format(
          resp.status_code)
    raise RuntimeError(err)
