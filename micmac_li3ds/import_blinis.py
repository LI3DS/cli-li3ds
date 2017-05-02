import os
import logging

from cliff.command import Command
from argparse import Namespace

from . import api as li3ds
from . import xmlutil


class ImportBlinis(Command):
    """ import a blinis file

        Create a sensor group and corresponding referentials and transfos.
    """

    log = logging.getLogger(__name__)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_parser(self, prog_name):
        self.log.debug(prog_name)
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--api-url', '-u',
            help='the li3ds API URL (optional)')
        parser.add_argument(
            '--api-key', '-k',
            help='the li3ds API key (optional)')
        parser.add_argument(
            '--no-proxy', action='store_true',
            help='disable all proxy settings')
        parser.add_argument(
            '--sensor-id', '-s',
            type=int,
            help='the sensor group id (optional)')
        parser.add_argument(
            '--sensor-name', '-n',
            help='the sensor group name (optional)')
        parser.add_argument(
            '--transfotree',
            help='the transfotree name (optional)')
        parser.add_argument(
            '--owner', '-o',
            help='the data owner (optional, default is unix username)')
        parser.add_argument(
            '--calibration-date', '-d',
            help='the calibration date (optional, default is the current '
                 'local date and time')
        parser.add_argument(
            '--validity-start',
            help='validity start date for transfos (optional, '
                 'default is valid since always)')
        parser.add_argument(
            '--validity-end',
            help='validity end date for transfos (optional, '
                 'default is valid until forever)')
        parser.add_argument(
            '--indent', type=int,
            help='number of spaces for pretty print indenting')
        parser.add_argument(
            'filenames', nargs='+',
            help='the list of blinis filenames')
        return parser

    def take_action(self, args):
        """
        Create or update a sensor group.
        """
        api = li3ds.Api(args.api_url, args.api_key, args.no_proxy,
                        self.log, args.indent)
        for filename in args.filename:
            self.log.info('Importing {}'.format(filename))
            import_blinis(api, args, filename)
        self.log.info('Success!\n')


def import_blinis(api, args, filename):
    args = Namespace(**vars(args))
    args.basename = os.path.basename(filename)
    args.transfotree = args.transfotree or args.basename
    args.sensor_name = args.sensor_name or args.basename

    root = xmlutil.root(filename, 'StructBlockCam')
    nodes = xmlutil.children(root, 'LiaisonsSHC/ParamOrientSHC')

    sensor = import_sensor_group(api, args, root)
    base_ref = import_base_referential(api, args, root, sensor)

    transfos = []
    for node in nodes:
        ref = import_referential(api, args, node, sensor)
        transfo = import_transform(api, args, node, base_ref, ref)
        transfos.append(transfo)

    import_transfotree(api, args, root, transfos)


def import_sensor_group(api, args, node):
    return api.get_or_create_sensor(
        name=args.sensor_name,
        sensor_type='group',
        sensor_id=args.sensor_id,
        description='imported from "{}"'.format(args.basename),
    )


def import_base_referential(api, args, node, sensor):
    description = 'base referential for sensor group {:d}, ' \
        'imported from "{}"'.format(sensor['id'], args.basename)
    return api.get_or_create_referential(
        name='base',
        sensor=sensor,
        description=description,
        root=True,
    )


def import_referential(api, args, node, sensor):
    description = 'referential for sensor group {:d}, ' \
                  'imported from "{}"'.format(
                      sensor['id'], args.basename)
    return api.get_or_create_referential(
        name=xmlutil.child(node, 'IdGrp').text.strip(),
        sensor=sensor,
        description=description,
    )


def import_transform(api, args, node, source, target):
    matrix = []
    p = xmlutil.child_floats_split(node, 'Vecteur')
    for i, l in enumerate(('Rot/L1', 'Rot/L2', 'Rot/L3')):
        matrix.extend(xmlutil.child_floats_split(node, l))
        matrix.append(p[i])

    name = '{}#{}'.format(args.transfotree, target['name'])
    return api.get_or_create_transfo(
        name, 'affine_mat4x3', source, target,
        description='imported from "{}"'.format(args.basename),
        parameters={'mat4x3': matrix},
        tdate=args.calibration_date,
        validity_start=args.validity_start,
        validity_end=args.validity_end,
    )


def import_transfotree(api, args, node, transfos):
    return api.get_or_create_transfotree(
        name=args.transfotree,
        transfos=transfos,
        owner=args.owner,
    )
