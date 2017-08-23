import logging
import pathlib
import datetime
import pytz

from cliff.command import Command

from . import api
from .foreignpc import create_foreignpc_table, create_foreignpc_view, create_datasource


class ImportEpt(Command):
    """ import an ept-formatted pointcloud
    """

    driver = 'fdwli3ds.EchoPulse'
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
            default='echopulse',
            help='name of foreign server to create (optional, default is "echopulse")')
        parser.add_argument(
            '--srid', '-r',
            type=int, default=0,
            help='SRID of lidar coordinates (optional, default is 0)')
        parser.add_argument(
            '--time-offset', '-x',
            type=float, default=0,
            help='time offset in seconds (optional, default is 0)')
        parser.add_argument(
            'directory',
            type=pathlib.Path,
            help='directory containing ept files')
        return parser

    def take_action(self, parsed_args):
        server = api.ApiServer(parsed_args, self.log)
        objs = api.ApiObjs(server)

        args = {
            'foreignpc/table': {
                'schema': parsed_args.database_schema,
                'srid': parsed_args.srid,
                'time_offset': parsed_args.time_offset,
            },
            'foreignpc/server': {
                'name': parsed_args.server_name,
            },
            'foreignpc/view': {
                'schema': parsed_args.database_schema,
            },
            'project': {
                'name': parsed_args.project,
            },
            'datasource': {
                'schema': parsed_args.database_schema,
            },
        }

        fullpath = parsed_args.chdir / parsed_args.directory
        name, session_time, section_name = self.parse_path(parsed_args.directory)
        self.log.info('Importing {}'.format(parsed_args.directory.stem))
        self.handle_ept(objs, args, fullpath, name, session_time, section_name)

        objs.get_or_create()
        self.log.info('Success!\n')

    @classmethod
    def handle_ept(cls, objs, args, data_path, name, session_time, section_name):

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
            'sbet': False,
        }
        sensor = {
            'type': 'lidar',
            'name': 'lidar',
        }
        referential_spherical = {
            'name': 'lidar spherical',
        }
        referential_cartesian = {
            'name': 'lidar cartesian',
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
            'name': 'lidar',
        }
        transfotree = {}

        api.update_obj(args, metadata, foreignpc_server, 'foreignpc/server')
        api.update_obj(args, metadata, foreignpc_table, 'foreignpc/table')
        api.update_obj(args, metadata, foreignpc_view, 'foreignpc/view')

        api.update_obj(args, metadata, sensor, 'sensor')
        api.update_obj(args, metadata, referential_spherical, 'referential')
        api.update_obj(args, metadata, referential_cartesian, 'referential')
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
        referential_spherical = api.Referential(sensor, referential_spherical)
        referential_cartesian = api.Referential(sensor, referential_cartesian)

        datasource = create_datasource(datasource, session, referential_spherical, name,
                                       'pointcloud')
        objs.add(datasource)

        transfo = api.Transfo(referential_spherical, referential_cartesian, transfo,
                              type_name='spherical_to_cartesian', parameters=[],
                              func_signature=[])
        transfotree = api.Transfotree([transfo], sensor, transfotree)
        objs.add(transfotree)

    @staticmethod
    def parse_path(ept_path):
        # example: LaVillette_1705160610_00.ept
        name = ept_path.name.split('.')[0]
        parts = name.split('_')
        if len(parts) < 3:
            err = 'Error: ept path structure is unknown'
            raise RuntimeError(err)
        session_time = datetime.datetime.strptime(parts[1], '%y%m%d%H%M')
        session_time = pytz.UTC.localize(session_time)
        section_name = parts[2]
        return name, session_time, section_name
