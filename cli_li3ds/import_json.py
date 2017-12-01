import logging
import json
import pathlib

from cliff.command import Command

from . import api


class ImportJson(Command):
    """ import one or several JSON files
    """

    log = logging.getLogger(__name__)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_parser(self, prog_name):
        self.log.debug(prog_name)
        parser = super().get_parser(prog_name)
        api.add_arguments(parser)
        parser.add_argument(
            '--json-dir', '-f', default='.',
            help='base directory to search for json files (optional, default is ".")')
        parser.add_argument(
            '--uri', default='{uri}',
            help='uri pattern for datasources (optional, default is pass through "{uri}")')
        parser.add_argument(
            'filename', nargs='+',
            help='JSON file names, may be Unix-style patterns (e.g. *.json)')
        return parser

    def take_action(self, parsed_args):
        server = api.ApiServer(parsed_args, self.log)
        json_dir = pathlib.Path(parsed_args.json_dir)
        uri = parsed_args.uri

        objs = api.ApiObjs(server)

        for filename in parsed_args.filename:
            for json_path in json_dir.rglob(filename):
                self.log.info('Importing {}'.format(json_path.relative_to(json_dir)))
                sensors = self.handle_json(objs, json_path, uri, api.Sensor)
                referentials = self.handle_json(objs, json_path, uri, api.Referential, sensors)
                ttypes = self.handle_json(objs, json_path, uri, api.TransfoType, referentials)
                transfos = self.handle_json(objs, json_path, uri, api.Transfo, referentials, ttypes)
                transfotrees = self.handle_json(objs, json_path, uri, api.Transfotree, transfos)
                platforms = self.handle_json(objs, json_path, uri, api.Platform)
                self.handle_json(objs, json_path, uri, api.Config, platforms, transfotrees)
                projects = self.handle_json(objs, json_path, uri, api.Project)
                sessions = self.handle_json(objs, json_path, uri, api.Session, projects, platforms)
                self.handle_json(objs, json_path, uri, api.Datasource, sessions, referentials)

        objs.get_or_create()
        self.log.info('Success!\n')

    @classmethod
    def handle_json(cls, objs, json_path, uri, class_, deps1=None, deps2=None):
        with json_path.open(encoding="iso-8859-1") as f:
            content = json.load(f)
        obj_map = {}
        for elem in content[class_.type_]:
            if elem:  # skip empty objects
                obj_id = elem.pop('id', None)
                if class_.type_ == "referential":
                    obj = class_(deps1[elem.pop('sensor')], elem)
                elif class_.type_ == "transfos/type":
                    obj = class_(elem)
                    elem2 = elem.copy()
                    elem2['name'] += '_inverse'
                    elem2.pop('id', None)
                    obj2 = class_(elem2)
                    objs.add(obj2)
                    obj.inv = obj2
                elif class_.type_ == "transfo":
                    source = deps1[elem.pop('source')]
                    target = deps1[elem.pop('target')]
                    transfo_type = deps2[elem.pop('transfo_type')]
                    obj = class_(source, target, elem, transfo_type=transfo_type)
                    elem2 = elem.copy()
                    elem2['name'] += '_inverse'
                    obj2 = class_(target, source, elem2, transfo_type=transfo_type.inv)
                    objs.add(obj2)
                    obj.inv = obj2
                elif class_.type_ == "session":
                    obj = class_(deps1[elem.pop('project')], deps2[elem.pop('platform')], elem)
                elif class_.type_ == "transfotree":
                    transfos = [deps1[t] for t in elem.pop('transfos')]
                    transfos.extend([t.inv for t in transfos if t.inv])
                    obj = class_(transfos, elem)
                elif class_.type_ == "platforms/{id}/config":
                    tt = [deps2[t] for t in elem.pop('transfo_trees')]
                    obj = class_(deps1[elem.pop('platform')], tt, elem)
                elif class_.type_ == "datasource":
                    elem['uri'] = uri.format(**elem)
                    obj = class_(deps1[elem.pop('session')], deps2[elem.pop('referential')], elem)
                else:
                    obj = class_(elem)
                obj_map[obj_id] = obj
                objs.add(obj)
        return obj_map
