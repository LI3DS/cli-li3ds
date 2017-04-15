import requests
import os
import json

os.environ['NO_PROXY'] = 'localhost'


class Api(object):

    def __init__(self, api_url, api_key, log, indent):
        self.api_url = None
        self.headers = None
        self.staging = None
        self.log = log
        self.indent = indent
        self.ids = {
            'transfo': ['source', 'target'],
            'transfos/type': [],
            'transfotree': ['transfos'],
            'referential': ['sensor'],
            'sensor': [],
        }

        if api_url:
            if not api_key:
                err = 'Error: no api key provided'
                raise ValueError(err)
            self.api_url = api_url.rstrip('/')
            self.headers = {
                'Accept': 'application/json',
                'X-API-KEY': api_key
                }
        else:
            self.staging = {
                'transfo': [],
                'transfos/type': [],
                'transfotree': [],
                'referential': [],
                'sensor': [],
            }

    def create_object(self, typ, obj):
        if self.staging:
            obj['id'] = len(self.staging[typ])
            self.staging[typ].append(obj)
            return obj

        url = self.api_url + '/{}s/'.format(typ)
        resp = requests.post(url, json=obj, headers=self.headers)
        if resp.status_code == 201:
            objs = resp.json()
            return objs[0]
        err = 'Adding object failed (status code: {})'.format(
              resp.status_code)
        raise RuntimeError(err)

    def get_object_by_id(self, typ, obj_id):
        if self.staging:
            objs = self.staging[typ]
            return objs[obj_id] if obj_id < len(objs) else None

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
        if self.staging:
            objs = self.staging[typ]
            obj = [obj for obj in objs if obj.name == obj_name]
            return obj[0] if obj else None

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

    def get_object_by_dict(self, typ, dict_):
        if self.staging:
            objs = self.staging[typ]
            obj = [o for o in objs if all(
                    o[k] == v for k, v in dict_.items() if k in o)]
            return obj[0] if obj else None

        url = self.api_url + '/{}s/'.format(typ)
        resp = requests.get(url, headers=self.headers)
        if resp.status_code == 200:
            objs = resp.json()
            try:
                obj = next(o for o in objs if all(
                    o[k] == v for k, v in dict_.items() if k in o))
            except StopIteration:
                return None
            return obj
        err = 'Getting object failed (status code: {})'.format(
              resp.status_code)
        raise RuntimeError(err)

    def get_objects(self, typ):
        if self.staging:
            return self.staging[typ]

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

    def get_or_create_object(self, typ, obj):
        obj = {k: v for k, v in obj.items() if v is not None}
        if 'id' in obj:
            # look up by id, raise an error upon lookup failure
            # or value mismatch for specified keys
            got = self.get_object_by_id(typ, obj['id'])
            if not got:
                err = 'Error: {} with id {:d} not in db'.format(typ, obj['id'])
                raise RuntimeError(err)

            all_keys = set(obj.keys()).intersection(got.keys())
            for key in all_keys:
                if obj[key] != got[key]:
                    err = 'Error: "{}" mismatch in {} with id {:d} ' \
                          '("{}" vs "{}")' \
                          .format(key, typ, obj['id'], obj[key], got[key])
                    raise RuntimeError(err)

            return got, '='

        if 'name' not in obj:
            err = 'Error: objects should specify ' \
                  'either their name or id {}'.format(obj)
            raise RuntimeError(err)

        # look up by dict, and raise an error upon mismatch
        dict_ = {k: obj[k] for k in self.ids[typ]}
        dict_['name'] = obj['name']
        got = self.get_object_by_dict(typ, dict_)
        if got:
            # raise an error upon value mismatch for specified keys
            all_keys = set(obj.keys()).intersection(got.keys())
            for key in all_keys:
                if obj[key] != got[key]:
                    err = 'Error: "{}" mismatch in {} "{}" ' \
                          '("{}" vs "{}")' \
                          .format(key, typ, obj['name'], obj[key], got[key])
                    raise RuntimeError(err)

            return got, '?'

        # no successfull lookup by id or by name, create a new object
        got = self.create_object(typ, obj)
        return got, '+'

    def get_or_create_log(self, typ, obj):
        obj, code = self.get_or_create_object(typ, obj)
        info = '{} ({}) {} [{}] "{}"'.format(
            code, obj['id'], typ,
            '->'.join([str(obj[k]) for k in self.ids[typ]]),
            obj['name'])
        self.log.info(info)
        self.log.debug(json.dumps(obj, indent=self.indent))
        return obj

    def get_or_create_transfo(self, transfo, type_, source, target):
        transfo_type = {
            'name': type_,
            'func_signature': list(transfo['parameters'].keys()),
        }
        transfo_type = self.get_or_create_log('transfos/type', transfo_type)
        transfo['transfo_type'] = transfo_type['id']
        transfo['source'] = source['id']
        transfo['target'] = target['id']
        return self.get_or_create_log('transfo', transfo)
