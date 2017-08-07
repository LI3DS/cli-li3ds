import logging
import pathlib
import re

from cliff.command import Command

from . import api


class ImportTrajectory(Command):
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
            '--server-name', '-n',
            default='sbet',
            help='name of foreign server to create (optional, default is "sbet")')
        parser.add_argument(
            '--database-schema', '-s',
            help='name of database schema into which foreign tables are created '
                 '(optional, default is "public")',
            default='public')
        parser.add_argument(
            '--srid', '-r',
            type=int, default=4326,
            help='SRID of trajectory coordinates (optional, default is 4326)')
        parser.add_argument(
            '--trajectory-dir', '-f',
            type=pathlib.Path, default='.',
            help='base directory to search for trajectories (optional, default is ".")')
        parser.add_argument(
            '--filename-pattern', '-p',
            help='file name pattern')
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
                'srid': parsed_args.srid,
            },
            'foreignpc/server': {
                'name': parsed_args.server_name,
            },
        }

        for trajectory_path in self.matching_filenames(parsed_args):
            self.log.info('Importing {}'.format(
                trajectory_path.relative_to(parsed_args.trajectory_dir)))
            self.handle_trajectory(objs, args, parsed_args.trajectory_dir, trajectory_path)

        objs.get_or_create()
        self.log.info('Success!\n')

    @staticmethod
    def matching_filenames(parsed_args):
        for filename in parsed_args.filename:
            for trajectory_path in parsed_args.trajectory_dir.rglob(filename):
                if parsed_args.filename_pattern:
                    match = re.match(parsed_args.filename_pattern, trajectory_path.name)
                else:
                    match = True
                if match:
                    yield trajectory_path

    @staticmethod
    def handle_trajectory(objs, args, trajectory_dir, trajectory_path):

        metadata = {
            'table': trajectory_path.name.split('.')[0],
            'trajectory': str(trajectory_path),
        }

        foreignpc_server = {
            'driver': 'fdwli3ds.Sbet',
            'options': {},
        }
        foreignpc_table = {
            'table': '{table}',
            'trajectory': '{trajectory}',
        }

        api.update_obj(args, metadata, foreignpc_server, 'foreignpc/server')
        api.update_obj(args, metadata, foreignpc_table, 'foreignpc/table')

        foreignpc_server = api.ForeignpcServer(foreignpc_server)
        foreignpc_table = create_foreignpc_table(foreignpc_table, foreignpc_server, trajectory_path)

        objs.add(foreignpc_table)


def create_foreignpc_table(foreignpc_table, foreignpc_server, trajectory_path):
    table = '{schema}.{table}'.format(**foreignpc_table)
    del foreignpc_table['schema']
    del foreignpc_table['table']

    options = {
        'sources': foreignpc_table['trajectory'],
        'patch_size': 100,
    }
    del foreignpc_table['trajectory']

    return api.ForeignpcTable(foreignpc_server, foreignpc_table, table=table, options=options)
