import requests
import dateutil.parser
import json
import getpass
import time
from functools import wraps


MAX_REQUEST_ATTEMPTS = 10


def add_arguments(parser):
    group = parser.add_argument_group(
        'API arguments',
        'API connection settings, dry run in staging mode if not provided')
    group.add_argument(
        '--api-url', '-u',
        help='the li3ds API URL (optional)')
    group.add_argument(
        '--api-key', '-k',
        help='the li3ds API key (required if --api-url is provided)')
    group.add_argument(
        '--no-proxy', action='store_true',
        help='disable all proxy settings')
    parser.add_argument(
       '--indent', type=int,
       help='number of spaces for pretty print indenting')
    parser.add_argument(
       '--owner', '-o',
       help='the data owner (optional, default is unix username)')


def handle_connection_errors(f):
    @wraps(f)
    def wrapper(api, session, *args):
        for attempt in range(1, MAX_REQUEST_ATTEMPTS + 1):
            try:
                rv = f(api, session, *args)
            except requests.exceptions.ConnectionError as e:
                warn = 'Connection error, try again... (attempt #{})'.format(attempt)
                api.log.warning(warn)
                time.sleep(0.1 * attempt)
                continue
            except:
                raise
            break
        else:
            raise RuntimeError('Too many connection errors')
        return rv
    return wrapper


class ApiServer(object):

    def __init__(self, args, log):
        self.api_url = args.api_url
        self.headers = None
        self.proxies = None
        self.staging = None
        self.log = log
        self.indent = args.indent

        if args.api_url:
            if not args.api_key:
                err = 'Error: no api key provided'
                raise ValueError(err)
            self.api_url = args.api_url.rstrip('/')
            self.headers = {
                'Accept': 'application/json',
                'X-API-KEY': args.api_key
            }
            self.proxies = {'http': None} if args.no_proxy else None
        else:
            self.log.info('! Staging mode (use -u/-k options '
                          'to provide an api url and key)')
            self.staging = {
                'transfo': [],
                'transfos/type': [],
                'transfotree': [],
                'referential': [],
                'sensor': [],
                'platform': [],
                'project': [],
                'session': [],
                'datasource': [],
                'platforms/{id}/config': [],
                'foreignpc/server': [],
                'foreignpc/table': [],
                'foreignpc/view': [],
            }

    @handle_connection_errors
    def create_object(self, session, typ, obj, parent):
        if self.staging:
            obj['id'] = len(self.staging[typ])
            self.staging[typ].append(obj)
            return obj

        url = self.api_url + '/{}s/'.format(typ.format(**parent))
        resp = session.post(
            url, json=obj, headers=self.headers, proxies=self.proxies)
        if resp.status_code == 201:
            objs = resp.json()
            return objs[0]
        if resp.status_code == 404:
            return None
        err = 'Adding object failed (status code: {})'.format(
              resp.status_code)
        raise RuntimeError(err)

    @handle_connection_errors
    def get_object_by_id(self, session, typ, obj_id, parent):
        if self.staging:
            objs = self.staging[typ]
            return objs[obj_id] if obj_id < len(objs) else None

        url = self.api_url + '/{}s/{:d}/'.format(typ.format(**parent), obj_id)
        resp = session.get(url, headers=self.headers, proxies=self.proxies)
        if resp.status_code == 200:
            objs = resp.json()
            return objs[0]
        if resp.status_code == 404:
            return None
        err = 'Getting object failed (status code: {})'.format(
              resp.status_code)
        raise RuntimeError(err)

    @handle_connection_errors
    def get_object_by_name(self, session, typ, obj_name, parent):
        if self.staging:
            objs = self.staging[typ]
            obj = [obj for obj in objs if obj.name == obj_name]
            return obj[0] if obj else None

        url = self.api_url + '/{}s/'.format(typ.format(**parent))
        resp = session.get(url, headers=self.headers, proxies=self.proxies)
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

    @handle_connection_errors
    def get_object_by_dict(self, session, typ, dict_, parent):
        if self.staging:
            objs = self.staging[typ]
            obj = [o for o in objs if all(
                    o[k] == v for k, v in dict_.items() if k in o)]
            return obj[0] if obj else None

        url = self.api_url + '/{}s/'.format(typ.format(**parent))
        resp = session.get(url, headers=self.headers, proxies=self.proxies, params=dict_)
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

    @handle_connection_errors
    def get_objects(self, session, typ, parent):
        if self.staging:
            return self.staging[typ]

        url = self.api_url + '/{}s/'.format(typ.format(**parent))
        resp = session.get(url, headers=self.headers, proxies=self.proxies)
        if resp.status_code == 200:
            objs = resp.json()
            return objs
        err = 'Getting object failed (status code: {})'.format(
              resp.status_code)
        raise RuntimeError(err)

    def get_or_create_object(self, session, typ, obj, key, parent):
        if 'id' in obj:
            # look up by id, raise an error upon lookup failure
            # or value mismatch for specified keys
            got = self.get_object_by_id(session, typ, obj['id'], parent)
            if not got:
                err = 'Error: {} with id {:d} not in db'.format(typ, obj['id'])
                raise RuntimeError(err)

            all_keys = set(obj.keys()).intersection(got.keys())
            all_keys.discard('description')
            for key in all_keys:
                if obj[key] != got[key]:
                    err = 'Error: "{}" mismatch in {} with id {:d} ' \
                          '("{}" vs "{}")' \
                          .format(key, typ, obj['id'], obj[key], got[key])
                    raise RuntimeError(err)

            return got, '='

        if not all(k in obj for k in key):
            err = 'Error: {} objects should specify ' \
                  'either their (id) or ({}) {}' \
                  .format(typ, ','.join(key), obj)
            raise RuntimeError(err)

        # look up by dict, and raise an error upon mismatch
        dict_ = {k: obj[k] for k in key}
        got = self.get_object_by_dict(session, typ, dict_, parent)
        if got:
            # raise an error upon value mismatch for specified keys
            all_keys = set(obj.keys()).intersection(got.keys())
            all_keys.discard('description')
            for key in all_keys:
                if obj[key] != got[key]:
                    display_name = obj.get('name', got.get('id'))
                    err = 'Error: "{}" mismatch in {} "{}" ' \
                          '("{}" vs "{}")' \
                          .format(key, typ, display_name, obj[key], got[key])
                    raise RuntimeError(err)

            return got, '?'

        # no successfull lookup by id or by name, create a new object
        got = self.create_object(session, typ, obj, parent)
        return got, '+'

    def get_or_create(self, session, apiobj):
        self.log.debug('')
        if not self.staging:
            self.log.debug('-->' + json.dumps(apiobj.obj, indent=self.indent))
        obj, code = self.get_or_create_object(
            session, apiobj.type_, apiobj.obj, apiobj.key, apiobj.parent.obj)
        if not obj:
            # If obj is None it means that creating the object into the database failed because of
            # a database integrity error ("duplicate key violation"). This may happen if a
            # concurrent transaction sneaked in and inserted the object. So we just give
            # get_or_create_object another chance.
            obj, code = self.get_or_create_object(
                session, apiobj.type_, apiobj.obj, apiobj.key, apiobj.parent.obj)
        self.log.debug('<--' + json.dumps(apiobj.obj, indent=self.indent))
        info = '{} ({}) {} [{}] {}'.format(
            code, apiobj.obj.get('id', '?'), apiobj.type_.format(**apiobj.parent.obj),
            ', '.join(str(apiobj.obj[k]) for k in apiobj.key if k in apiobj.obj),
            obj.get('uri', '') if obj else '')
        self.log.info(info)
        return obj


class ApiObjs:

    def __init__(self, api):
        self.api = api
        self.objs = []

    def add(self, *objs):
        for obj in objs:
            assert(isinstance(obj, ApiObj))
            self.objs.append(obj)

    def get_or_create(self):
        with requests.Session() as session:
            for obj in self.objs:
                obj.get_or_create(session, self.api)

    def lookup(self, obj):
        '''
        Depth-first search of obj within the collection.
        '''
        for o in self.objs:
            if o == obj:
                return o
            o = o.lookup(obj)
            if o:
                return o
        return None


class ApiObj:
    key = ()
    type_ = None

    def __init__(self, keys, obj=None, **kwarg):
        self.published = False
        self.keys = keys
        self.obj = {}
        self.objs = {}
        self.arrays = {}
        self.parent = noobj
        if obj:
            self.update(**obj)
        self.update(**kwarg)

    def get_or_create(self, session, api):
        if self.published:
            return self

        for key in self.objs:
            if self.objs[key]:
                self.obj[key] = self.objs[key].get_or_create(session, api).obj['id']

        for key in self.arrays:
            ids = [obj.get_or_create(session, api).obj['id'] for obj in self.arrays[key]
                   if obj is not noobj]
            self.obj[key] = sorted(ids)

        obj = api.get_or_create(session, self)
        self.obj = obj
        self.published = True
        return self

    def update(self, **kwarg):
        obj = ApiObj.normalize_obj(kwarg)
        for key in obj:
            if key not in self.keys:
                err = 'Error: {} is invalid in {}'.format(key, self.type_)
                raise RuntimeError(err)
        self.obj.update(obj)
        return self

    def normalize_obj(obj):
        if isinstance(obj, dict):
            return {k: ApiObj.normalize_obj(v) for k, v in obj.items()
                    if v is not None}
        return {} if obj is None else obj

    def lookup(self, obj):
        '''
        Depth-first search of obj within the object.
        '''
        for _, o in self.objs.items():
            if o == obj:
                return o
            o = o.lookup(obj)
            if o:
                return o
        for _, array in self.arrays.items():
            for o in array:
                if o == obj:
                    return o
                o = o.lookup(obj)
                if o:
                    return o
        return None

    def __eq__(self, other):
        '''
        Two ApiObj instances are equal if their "primary key" properties are equal.
        '''
        if id(self) == id(other):
            return True

        if self.type_ != other.type_:
            return False

        for id_ in self.key:
            if id_ in self.obj and id_ in other.obj:
                if self.obj[id_] != other.obj[id_]:
                    return False
                continue

            if id_ in self.objs and id_ in other.objs:
                if self.objs[id_] != other.objs[id_]:
                    return False
                continue

            if id_ in self.arrays and id_ in other.arrays:
                if len(self.arrays[id_]) != len(other.arrays[id_]):
                    return False
                for i in range(len(self.arrays[id_])):
                    if self.arrays[id_][i] != other.arrays[id_][i]:
                        return False
                continue

            return False

        return True

    def __bool__(self):
        return True


class _NoObj(ApiObj):
    type_ = 'noobj'

    def __init__(self):
        self.obj = {}
        pass

    def get_or_create(self, session, api):
        return self

    def __bool__(self):
        return False


noobj = _NoObj()


class Sensor(ApiObj):
    type_ = 'sensor'
    key = ('name',)

    def __init__(self, obj=None, **kwarg):
        keys = ('id', 'name', 'type', 'description', 'model',
                'serial_number', 'specifications')
        super().__init__(keys, obj, **kwarg)
        self.obj.setdefault('serial_number', '')


class Referential(ApiObj):
    type_ = 'referential'
    key = ('name', 'sensor')

    def __init__(self, sensor, obj=None, **kwarg):
        keys = ('id', 'name', 'description', 'srid')
        super().__init__(keys, obj, **kwarg)
        self.objs = {'sensor': sensor}


class TransfoType(ApiObj):
    type_ = 'transfos/type'
    key = ('name',)

    def __init__(self, obj=None, **kwarg):
        keys = ('id', 'name', 'description', 'func_signature')
        super().__init__(keys, obj, **kwarg)


class Transfo(ApiObj):
    type_ = 'transfo'
    key = ('name', 'source', 'target')

    def __init__(self, source, target, obj=None, reverse=False,
                 transfo_type=noobj, type_id=None, type_name=None,
                 type_description=None, func_signature=None, **kwarg):
        if func_signature and transfo_type:
            transfo_type.obj = transfo_type.obj.copy()
            transfo_type.obj['func_signature'] = func_signature

        keys = ('id', 'name', 'description', 'parameters', 'parameters_column',
                'tdate', 'validity_start', 'validity_end')
        if reverse:
            source, target = target, source
        super().__init__(keys, obj, **kwarg)

        if transfo_type is noobj:
            assert(func_signature is not None)
            if '_time' not in func_signature:
                func_signature.append('_time')
            transfo_type = TransfoType(
                id=type_id,
                name=type_name,
                description=type_description,
                func_signature=func_signature
            )
        self.objs = {
            'source': source,
            'target': target,
            'transfo_type': transfo_type
        }

    def get_or_create(self, session, api):
        if not self.published:
            parameters = self.obj.get('parameters')
            parameters_column = self.obj.get('parameters_column')
            if parameters and not parameters_column:

                if len(parameters) > 1:
                    try:
                        parameters.sort(key=lambda elt: elt['_time'])
                    except KeyError as e:
                        err = 'Error: _time missing in transfo parameters'
                        raise RuntimeError(err)

                for parameter in parameters:
                    if '_time' in parameter:
                        parameter['_time'] = isoformat(parameter['_time'])

                validity_start = self.obj.get('validity_start')
                if not validity_start and '_time' in parameters[0]:
                    self.obj['validity_start'] = parameters[0]['_time']

                validity_end = self.obj.get('validity_end')
                if not validity_end and '_time' in parameters[-1]:
                    self.obj['validity_end'] = parameters[-1]['_time']

        return super().get_or_create(session, api)


class Transfotree(ApiObj):
    type_ = 'transfotree'
    key = ('name', 'transfos')

    def __init__(self, transfos, obj=None, **kwarg):
        keys = ('id', 'name', 'owner')
        super().__init__(keys, obj, **kwarg)
        self.obj.setdefault('owner', getpass.getuser())
        self.arrays = {'transfos': transfos}


class Project(ApiObj):
    type_ = 'project'
    key = ('name',)

    def __init__(self, obj=None, **kwarg):
        keys = ('id', 'name', 'extent', 'timezone', 'specifications')
        super().__init__(keys, obj, **kwarg)
        self.obj.setdefault('timezone', 'Europe/Paris')


class Platform(ApiObj):
    type_ = 'platform'
    key = ('name',)

    def __init__(self, obj=None, **kwarg):
        keys = ('id', 'name', 'description', 'start_time', 'end_time')
        super().__init__(keys, obj, **kwarg)


class Session(ApiObj):
    type_ = 'session'
    key = ('name', 'project', 'platform')

    def __init__(self, project, platform, obj=None, **kwarg):
        keys = ('id', 'name', 'start_time', 'end_time', 'specifications')
        super().__init__(keys, obj, **kwarg)
        self.objs = {'project': project, 'platform': platform}


class Datasource(ApiObj):
    type_ = 'datasource'
    key = ('uri', 'session', 'referential')

    def __init__(self, session, referential, obj=None, **kwarg):
        keys = ('id', 'type', 'uri', 'bounds', 'capture_start', 'capture_end',
                'specifications', 'extent')
        super().__init__(keys, obj, **kwarg)
        self.objs = {'session': session, 'referential': referential}

    def update(self, **kwarg):
        uri = kwarg.get('uri')
        if uri:
            kwarg['uri'] = uri.strip()
        super().update(**kwarg)


class Config(ApiObj):
    type_ = 'platforms/{id}/config'
    key = ('name',)

    def __init__(self, platform, transfotrees, obj=None, **kwarg):
        keys = ('id', 'name', 'description', 'root', 'srid')
        super().__init__(keys, obj, **kwarg)
        self.objs = {'platform': platform}
        self.arrays = {'transfo_trees': transfotrees}
        self.obj.setdefault('owner', getpass.getuser())
        self.parent = platform


class ForeignpcServer(ApiObj):
    type_ = 'foreignpc/server'
    key = ('name',)

    def __init__(self, obj=None, **kwarg):
        keys = ('id', 'name', 'driver', 'options')
        super().__init__(keys, obj, **kwarg)


class ForeignpcTable(ApiObj):
    type_ = 'foreignpc/table'
    key = ('table',)

    def __init__(self, server, obj=None, **kwarg):
        keys = ('table', 'srid', 'options')
        super().__init__(keys, obj, **kwarg)
        self.objs = {'server': server}


class ForeignpcView(ApiObj):
    type_ = 'foreignpc/view'
    key = ('view',)

    def __init__(self, table, obj=None, **kwarg):
        keys = ('view', 'sbet', 'srid')
        super().__init__(keys, obj, **kwarg)
        self.objs = {'table': table}


def update_obj(args, metadata, obj, type_):
    noname = ('datasource', 'foreignpc/table', 'foreignpc/view')
    nodesc = ('datasource', 'transfotree', 'project', 'session',
              'foreignpc/server', 'foreignpc/table', 'foreignpc/view')
    if all(not type_.startswith(s) for s in noname):
        obj.setdefault('name', '{basename}')
    if all(not type_.startswith(s) for s in nodesc):
        obj.setdefault('description', 'Imported from "{basename}"')
    if args and type_ in args:
        obj.update({k: v for k, v in args[type_].items() if v is not None})
    metadata_no_none = {k: v for k, v in metadata.items() if v is not None}
    for key in list(obj.keys()):
        if obj[key] and isinstance(obj[key], str):
            try:
                obj[key] = obj[key].format(**metadata_no_none)
            except KeyError as e:
                # obj[key] contain replacements fields that have no
                # corresponding keys in metadata_no_none, raise an
                # error if key is not in the original metadata,
                # otherwise just delete the key from the object
                # and continue
                if e.args[0] not in metadata:
                    err = 'metadata {} not available for {}/{}="{}"'
                    raise KeyError(err.format(e.args[0], type_, key, obj[key]))
                del obj[key]


def isoformat(date):
    if isinstance(date, str):
        date = dateutil.parser.parse(date)
    return date.isoformat() if date else None
