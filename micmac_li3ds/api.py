import requests


def create_object(typ, obj, api_url, api_key):
    url = api_url.rstrip('/') + '/{}s/'.format(typ)
    headers = {'X-API-KEY': api_key}
    resp = requests.post(url, json=obj, headers=headers)
    if resp.status_code == 201:
        obj = resp.json()
        return obj[0]
    err = 'Adding object failed (status code: {})'.format(
          resp.status_code)
    raise RuntimeError(err)


def get_object_by_id(typ, obj_id, api_url, api_key):
    url = api_url.rstrip('/') + '/{}s/{:d}/'.format(typ, obj_id)
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
