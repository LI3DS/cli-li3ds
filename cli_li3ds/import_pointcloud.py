import logging
import pathlib
import re
import datetime
import pytz

from cliff.command import Command

from . import api


class ImportPc(Command):
    """ import one or several trajectories
    """

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
        return parser

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
    def handle_pointcloud(cls, objs, args, data_path, name, session_time, section_name):

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
            'sbet': cls.sbet,
        }
        sensor = {
            'type': cls.sensor_type,
            'name': cls.sensor_name,
        }
        referential = {
            'name': cls.referential_name,
        }
        platform = {
            'name': 'Stereopolis II',
        }
        project = {}
        session = {
                'name': '{session_time:%y%m%d}{section_name}',
        }
        datasource = {}

        api.update_obj(args, metadata, foreignpc_server, 'foreignpc/server')
        api.update_obj(args, metadata, foreignpc_table, 'foreignpc/table')
        api.update_obj(args, metadata, foreignpc_view, 'foreignpc/view')

        api.update_obj(args, metadata, sensor, 'sensor')
        api.update_obj(args, metadata, referential, 'referential')
        api.update_obj(args, metadata, platform, 'platform')
        api.update_obj(args, metadata, project, 'project')
        api.update_obj(args, metadata, session, 'session')
        api.update_obj(args, metadata, datasource, 'datasource')

        foreignpc_server = api.ForeignpcServer(foreignpc_server)
        foreignpc_table = create_foreignpc_table(foreignpc_table, foreignpc_server, cls.driver)
        foreignpc_view = create_foreignpc_view(foreignpc_view, foreignpc_table)
        objs.add(foreignpc_view)

        sensor = api.Sensor(sensor, specifications={})
        project = api.Project(project)
        platform = api.Platform(platform)
        session = api.Session(project, platform, session)
        referential = api.Referential(sensor, referential)
        datasource = create_datasource(datasource, session, referential, name, cls.datasource_type)
        objs.add(datasource)


def create_foreignpc_table(foreignpc_table, foreignpc_server, driver):
    table = '{schema}.{table}'.format(**foreignpc_table)
    del foreignpc_table['schema']
    del foreignpc_table['table']

    if driver == 'fdwli3ds.Sbet':
        options = {
            'sources': foreignpc_table['filepath'],
            'patch_size': 100,
        }
    elif driver == 'fdwli3ds.EchoPulse':
        options = {
            'directory': foreignpc_table['filepath'],
            'patch_size': 100,
        }

    del foreignpc_table['filepath']

    return api.ForeignpcTable(foreignpc_server, foreignpc_table, table=table, options=options)


def create_foreignpc_view(foreignpc_view, foreignpc_table):
    view = '{schema}.{view}'.format(**foreignpc_view)
    del foreignpc_view['schema']
    del foreignpc_view['view']
    return api.ForeignpcView(foreignpc_table, foreignpc_view, view=view)


def create_datasource(datasource, session, referential, name, type_):
    uri = 'column:{}.{}_view.points'.format(datasource['schema'], name)
    del datasource['schema']
    return api.Datasource(session, referential, datasource, type=type_, uri=uri)


class ImportEpt(ImportPc):

    driver = 'fdwli3ds.EchoPulse'
    sensor_name = 'lidar'
    sensor_type = 'lidar'
    referential_name = 'LASER'
    datasource_type = 'pointcloud'
    sbet = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_parser(self, prog_name):
        self.log.debug(prog_name)
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--server-name', '-n',
            default='echopulse',
            help='name of foreign server to create (optional, default is "echopulse")')
        parser.add_argument(
            '--srid', '-r',
            type=int, default=0,
            help='SRID of lidar coordinates (optional, default is 0)')
        parser.add_argument(
            'directory',
            type=pathlib.Path,
            help='data directory containing ept files')
        return parser

    def take_action(self, parsed_args):
        server = api.ApiServer(parsed_args, self.log)
        objs = api.ApiObjs(server)

        args = {
            'foreignpc/table': {
                'schema': parsed_args.database_schema,
                'srid': parsed_args.srid,
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
        self.handle_pointcloud(objs, args, fullpath, name, session_time, section_name)

        objs.get_or_create()
        self.log.info('Success!\n')

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


class ImportTrajectory(ImportPc):

    driver = 'fdwli3ds.Sbet'
    sensor_name = 'ins'
    sensor_type = 'ins'
    referential_name = 'INS'
    datasource_type = 'trajectory'
    sbet = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_parser(self, prog_name):
        self.log.debug(prog_name)
        parser = super().get_parser(prog_name)
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
            help='trajectory file names, may be Unix-style patterns (e.g. *.sbet)')
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
        }

        for data_path in self.matching_filenames(parsed_args):
            self.log.info('Importing {}'.format(
                data_path.relative_to(parsed_args.chdir)))
            name, session_time, section_name = self.parse_path(data_path)
            self.handle_pointcloud(objs, args, data_path, name, session_time, section_name)

        objs.get_or_create()
        self.log.info('Success!\n')

    @staticmethod
    def parse_path(trajectory_path):
        # example: LANDINS_20170516_075157_PP.popout.out
        name = trajectory_path.name.split('.')[0]
        parts = name.split('_')
        if len(parts) < 4:
            err = 'Error: trajectory path structure is unknown'
            raise RuntimeError(err)
        session_time = datetime.datetime.strptime(parts[1], '%Y%m%d')
        session_time = pytz.UTC.localize(session_time)
        section_name = None
        return name, session_time, section_name
