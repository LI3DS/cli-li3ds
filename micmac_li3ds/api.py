import requests
import os

os.environ['NO_PROXY'] = 'localhost'


class Api(object):

    def __init__(self, api_url, api_key):
        self.api_url = api_url.rstrip('/')
        self.headers = {
            'Accept': 'application/json',
            'X-API-KEY': api_key
            }

    def create_object(self, typ, obj):
        url = self.api_url + '/{}s/'.format(typ)
        resp = requests.post(url, json=obj, headers=self.headers)
        if resp.status_code == 201:
            objs = resp.json()
            return objs[0]
        err = 'Adding object failed (status code: {})'.format(
              resp.status_code)
        raise RuntimeError(err)

    def get_object_by_id(self, typ, obj_id):
        url = self.api_url + '/{}s/{:d}/'.format(typ, obj_id)
        resp = requests.get(url, headers=self.headers)
        if resp.status_code == 200:
            objs = resp.json()
            return objs[0]
        if resp.status_code == 404:
            return None
        err = 'Getting object failed (status code: {})'.format(
              resp.status_code)
        raise RuntimeError(err)

    def get_object_by_name(self, typ, obj_name):
        url = self.api_url + '/{}s/'.format(typ)
        resp = requests.get(url, headers=self.headers)
        if resp.status_code == 200:
            objs = resp.json()
            try:
                obj = next(o for o in objs if o['name'] == obj_name)
            except StopIteration:
                return None
            return obj
        err = 'Getting object failed (status code: {})'.format(
              resp.status_code)
        raise RuntimeError(err)

    def get_objects(self, typ):
        url = self.api_url + '/{}s/'.format(typ)
        resp = requests.get(url, headers=self.headers)
        if resp.status_code == 200:
            objs = resp.json()
            return objs
        err = 'Getting object failed (status code: {})'.format(
              resp.status_code)
        raise RuntimeError(err)

    def get_sensor_referentials(self, sensor_id):
        referentials = self.get_objects('referential')
        sensor_referentials = [None]
        for referential in referentials:
            if referential['sensor'] != sensor_id:
                continue
            if referential['root'] is True:
                if sensor_referentials[0]:
                    err = 'Multiple base referentials ' \
                          'found for sensor {:d}'.format(sensor_id)
                    raise RuntimeError(err)
                sensor_referentials[0] = referential
            else:
                sensor_referentials.append(referential)
        if sensor_referentials[0] is None:
            err = 'No base referential found for sensor {:d}'.format(sensor_id)
            raise RuntimeError(err)
        return sensor_referentials
