import logging
import pathlib
import re
import datetime
import pytz

from cliff.command import Command

from . import api
from .foreignpc import create_foreignpc_table, create_foreignpc_view, create_datasource


class ImportSbet(Command):
    """ import one or sbet files
    """

    driver = 'fdwli3ds.Sbet'
    log = logging.getLogger(__name__)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_parser(self, prog_name):
        self.log.debug(prog_name)
        parser = super().get_parser(prog_name)
        api.add_arguments(parser)
        parser.add_argument(
            '--project', '-c',
            help='project name (required)', required=True)
        parser.add_argument(
            '--database-schema', '-s',
            help='name of database schema into which foreign tables are created '
                 '(optional, default is "public")',
            default='public')
        parser.add_argument(
            '--chdir', '-f',
            type=pathlib.Path, default='.',
            help='base directory to search for data files (optional, default is ".")')
        parser.add_argument(
            '--filename-pattern', '-p',
            help='file name pattern')
        parser.add_argument(
            '--server-name', '-n',
            default='sbet',
            help='name of foreign server to create (optional, default is "sbet")')
        parser.add_argument(
            '--srid-input', '-r',
            type=int, default=4326,
            help='SRID of input trajectories (optional, default is 4326)')
        parser.add_argument(
            '--srid-output', '-t',
            type=int, default=2154,
            help='SRID of output trajectories (in the li3ds datastore) '
                 '(optional, default is 2154)')
        parser.add_argument(
            'filename', nargs='+',
            help='sbet file names, may be Unix-style patterns (e.g. *.sbet)')
        return parser

    def take_action(self, parsed_args):
        server = api.ApiServer(parsed_args, self.log)
        objs = api.ApiObjs(server)

        args = {
            'foreignpc/table': {
                'schema': parsed_args.database_schema,
                'srid': parsed_args.srid_input,
            },
            'foreignpc/server': {
                'name': parsed_args.server_name,
            },
            'foreignpc/view': {
                'schema': parsed_args.database_schema,
                'srid': parsed_args.srid_output,
            },
            'project': {
                'name': parsed_args.project,
            },
            'datasource': {
                'schema': parsed_args.database_schema,
            },
            'referential_ins': {
                'srid': parsed_args.srid_input,
            },
            'referential_world': {
                'srid': parsed_args.srid_output,
            },
            'transfo': {
                'schema': parsed_args.database_schema,
            },
        }

        for data_path in self.matching_filenames(parsed_args):
            self.log.info('Importing {}'.format(
                data_path.relative_to(parsed_args.chdir)))
            name, session_time, section_name = self.parse_path(data_path)
            self.handle_sbet(objs, args, data_path, name, session_time, section_name)

        objs.get_or_create()
        self.log.info('Success!\n')

    @staticmethod
    def matching_filenames(parsed_args):
        for filename in parsed_args.filename:
            for data_path in parsed_args.chdir.rglob(filename):
                if parsed_args.filename_pattern:
                    match = re.match(parsed_args.filename_pattern, data_path.name)
                else:
                    match = True
                if match:
                    yield data_path

    @classmethod
    def handle_sbet(cls, objs, args, data_path, name, session_time, section_name):

        metadata = {
            'basename': data_path.name,
            'table': name,
            'filepath': str(data_path),
            'session_time': session_time,
            'section_name': '/' + section_name if section_name else ''
        }

        foreignpc_server = {
            'driver': cls.driver,
            'options': {},
        }
        foreignpc_table = {
            'table': '{table}',
            'filepath': '{filepath}',
        }
        foreignpc_view = {
            'view': '{table}_view',
            'sbet': True,
        }
        sensor = {
            'type': 'ins',
            'name': 'ins',
        }
        referential_ins = {
            'name': 'ins',
        }
        referential_world = {
            'name': 'world',
        }
        platform = {
            'name': 'Stereopolis II',
        }
        project = {}
        session = {
            'name': '{session_time:%y%m%d}{section_name}',
        }
        datasource = {}
        transfo = {
            'name': '{table}_view',
            'view': '{table}_view',
        }
        transfotree = {}

        api.update_obj(args, metadata, foreignpc_server, 'foreignpc/server')
        api.update_obj(args, metadata, foreignpc_table, 'foreignpc/table')
        api.update_obj(args, metadata, foreignpc_view, 'foreignpc/view')

        api.update_obj(args, metadata, sensor, 'sensor')
        api.update_obj(args, metadata, referential_ins, 'referential_ins')
        api.update_obj(args, metadata, referential_world, 'referential_world')
        api.update_obj(args, metadata, platform, 'platform')
        api.update_obj(args, metadata, project, 'project')
        api.update_obj(args, metadata, session, 'session')
        api.update_obj(args, metadata, datasource, 'datasource')
        api.update_obj(args, metadata, transfo, 'transfo')
        api.update_obj(args, metadata, transfotree, 'transfotree')

        foreignpc_server = api.ForeignpcServer(foreignpc_server)
        foreignpc_table = create_foreignpc_table(foreignpc_table, foreignpc_server, cls.driver)
        foreignpc_view = create_foreignpc_view(foreignpc_view, foreignpc_table)
        objs.add(foreignpc_view)

        sensor = api.Sensor(sensor)
        project = api.Project(project)
        platform = api.Platform(platform)
        session = api.Session(project, platform, session)
        referential_ins = api.Referential(sensor, referential_ins)
        referential_world = api.Referential(sensor, referential_world)

        datasource = create_datasource(datasource, session, referential_ins, name, 'trajectory')
        objs.add(datasource)

        # create two transforms:
        # - the forward transform: world_to_ins
        # - the backward transform: ins_to_world
        transfo_world_to_ins = cls.create_transfo(
            dict(transfo), referential_ins, referential_world, True)
        transfo_ins_to_world = cls.create_transfo(
            dict(transfo), referential_ins, referential_world, False)
        transfotree_world_to_ins = api.Transfotree([transfo_world_to_ins], sensor, transfotree)
        transfotree_ins_to_world = api.Transfotree([transfo_ins_to_world], sensor, transfotree)
        objs.add(transfotree_world_to_ins, transfotree_ins_to_world)

    @staticmethod
    def parse_path(trajectory_path):
        # example: LANDINS_20170516_075157_PP.popout.out
        name = trajectory_path.name.split('.')[0]
        parts = name.split('_')
        if len(parts) < 4:
            err = 'Error: trajectory path structure is unknown'
            raise RuntimeError(err)
        session_time = datetime.datetime.strptime(parts[1], '%Y%m%d')
        session_time = pytz.UTC.localize(session_time)
        section_name = None
        return name, session_time, section_name

    @staticmethod
    def create_transfo(transfo, referential_ins, referential_world, forward):
        transfo['parameters_column'] = '{schema}.{view}.points'.format(**transfo)
        del transfo['schema']
        del transfo['view']
        if forward:
            # world -> ins
            source, target = referential_world, referential_ins
            quat = ['qw', '-qx', '-qy', '-qz']
            vec3 = ['-x', '-y', '-z']
        else:
            # ins -> world
            source, target = referential_ins, referential_world
            quat = ['qw', 'qx', 'qy', 'qz']
            vec3 = ['x', 'y', 'z']
        return api.Transfo(source, target, transfo,
                           type_name='affine_quat',
                           parameters=[{'quat': quat, 'vec3': vec3, '_time': 'time'}])
