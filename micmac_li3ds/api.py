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

    def get_object_by_dict(self, typ, dict):
        url = self.api_url + '/{}s/'.format(typ)
        resp = requests.get(url, headers=self.headers)
        if resp.status_code == 200:
            objs = resp.json()
            try:
                obj = next(o for o in objs if
                    all(o[k] == v for k, v in dict.items() if k in o))
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



    def get_or_create_object(self, typ, obj, keys, log):

        log.debug('getting or creating {} "{}"'.format(typ, obj))

        if 'id' in obj:
            # look up by id
            # raise an error upon lookup failure or value mismatch for specified keys
            got = self.get_object_by_id(typ, obj['id'])
            if not got:
                err = 'Error: {} with id {:d} not in db'.format(typ, obj['id'])
                raise RuntimeError(err)

            obj_keys = set(obj.keys())
            got_keys = set(got.keys())
            keys = obj_keys.intersection(got_keys)

            for key in keys:
                if obj[key] != got[key]:
                    err = 'Error: "{}" mismatch in {} with id {:d} ("{}" vs "{}")'.format(
                        key, typ, obj['id'], obj[key], got[key])
                    raise RuntimeError(err)

            log.info('{} "{}" found in database with id {:d}.'
                .format(typ, got['name'], got['id']))
            return got

        if not 'name' in obj:
            err = 'Error: objects should specify either their name or id {}'.format(obj)
            raise RuntimeError(err)

        # look up by dict, and raise an error upon mismatch
        keys.append('name')
        dict = {}
        for k in keys:
            dict[k] = obj[k]
        got = self.get_object_by_dict(typ, dict)
        if got:
            # raise an error upon value mismatch for specified keys
            obj_keys = set(obj.keys())
            got_keys = set(got.keys())
            all_keys = obj_keys.intersection(got_keys)

            for key in all_keys:
                if obj[key] != got[key]:
                    err = 'Error: "{}" mismatch in {} "{}" ("{}" vs "{}")'.format(
                        key, typ, obj['name'], obj[key], got[key])
                    raise RuntimeError(err)

            log.info('{} "{}" found in database by ({}) with id {:d}.'.format(
                typ, got['name'], ",".join(keys), got['id']))
            return got

        # no successfull lookup by id or by name, create a new object
        got = self.create_object(typ, obj)
        log.info('{} "{}" created with id {:d}.'.format(typ, got['name'], got['id']))
        return got
