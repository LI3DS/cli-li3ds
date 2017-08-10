import logging
import pathlib
import re

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

    @staticmethod
    def handle_pointcloud(objs, args, data_path, driver):

        metadata = {
            'table': data_path.name.split('.')[0],
            'filepath': str(data_path),
        }

        foreignpc_server = {
            'driver': driver,
            'options': {},
        }
        foreignpc_table = {
            'table': '{table}',
            'filepath': '{filepath}',
        }

        foreignpc_view = {
            'view': '{table}_view'
        }

        api.update_obj(args, metadata, foreignpc_server, 'foreignpc/server')
        api.update_obj(args, metadata, foreignpc_table, 'foreignpc/table')
        api.update_obj(args, metadata, foreignpc_view, 'foreignpc/view')

        foreignpc_server = api.ForeignpcServer(foreignpc_server)
        foreignpc_table = create_foreignpc_table(foreignpc_table, foreignpc_server, driver)
        view_name = '{schema}.{view}'.format(**foreignpc_view)
        del foreignpc_view['schema']
        del foreignpc_view['view']
        foreignpc_view = api.ForeignpcView(foreignpc_table, foreignpc_view, view=view_name)

        objs.add(foreignpc_view)


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


class ImportEpt(ImportPc):

    def __init__(self, *args, **kwargs):
        self.driver = 'fdwli3ds.EchoPulse'
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
        }

        fullpath = parsed_args.chdir / parsed_args.directory
        self.log.info('Importing {}'.format(parsed_args.directory.stem))
        self.handle_pointcloud(objs, args, fullpath, self.driver)

        objs.get_or_create()
        self.log.info('Success!\n')


class ImportTrajectory(ImportPc):

    def __init__(self, *args, **kwargs):
        self.driver = 'fdwli3ds.Sbet'
        super().__init__(*args, **kwargs)

    def get_parser(self, prog_name):
        self.log.debug(prog_name)
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--server-name', '-n',
            default='sbet',
            help='name of foreign server to create (optional, default is "sbet")')
        parser.add_argument(
            '--srid', '-r',
            type=int, default=4326,
            help='SRID of trajectory coordinates (optional, default is 4326)')
        parser.add_argument(
            'filename', nargs='+',
            help='data file names, may be Unix-style patterns (e.g. *.sbet)')
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
        }

        for data_path in self.matching_filenames(parsed_args):
            self.log.info('Importing {}'.format(
                data_path.relative_to(parsed_args.chdir)))
            self.handle_pointcloud(objs, args, data_path, self.driver)

        objs.get_or_create()
        self.log.info('Success!\n')
