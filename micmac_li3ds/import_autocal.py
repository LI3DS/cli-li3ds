import os
import logging

from cliff.command import Command
from argparse import Namespace

from . import api as li3ds
from . import distortion
from . import xmlutil


class ImportAutocal(Command):
    """ import an autocal file
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
            help='the camera sensor id (optional)')
        parser.add_argument(
            '--sensor-name', '-n',
            help='the camera sensor name (optional)')
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
            help='the list of autocal filenames')
        return parser

    def take_action(self, args):
        """
        Create or update a camera sensor.
        """
        api = li3ds.Api(args.api_url, args.api_key, args.no_proxy,
                        self.log, args.indent)
        for filename in args.filenames:
            self.log.info('Importing {}'.format(filename))
            import_intrinsics(api, args, filename)
        self.log.info('Success!\n')


def import_intrinsics(api, args, filename, transfotree=None, node=None):
    args = Namespace(**vars(args))
    args.basename = os.path.basename(filename)
    args.transfotree = transfotree or args.transfotree or args.basename
    args.sensor_name = args.sensor_name or args.basename

    if not node:
        root = xmlutil.root(filename, 'ExportAPERO')
        node = xmlutil.child(root, 'CalibrationInternConique')

    xmlutil.child_check(node, 'KnownConv', 'eConvApero_DistM2C')

    sensor = import_sensor(api, args, node)
    ref_ri = import_raw_image_referential(api, args, node, sensor)
    transfos = []

    target = ref_ri
    orintglob = node.find('OrIntGlob')
    if orintglob:
        source = import_orintglob_referential(
            api, args, orintglob, sensor)
        distortion = import_orintglob_transform(
            api, args, orintglob, source, target)
        target = source
        transfos.append(distortion)

    disto_nodes = reversed(xmlutil.children(node, 'CalibDistortion'))
    for i, disto_node in enumerate(disto_nodes):
        source = import_distortion_referential(
            api, args, disto_node, sensor, i)
        distortion = import_distortion_transform(
            api, args, disto_node, source, target, i)
        target = source
        transfos.append(distortion)

    ref_eu = import_euclidean_referential(api, args, node, sensor)
    pinhole = import_pinhole_transform(api, args, node, ref_eu, target)
    transfos.append(pinhole)

    transfotree = import_transfotree(api, args, node, transfos)

    return sensor, ref_ri, ref_eu, transfotree


def import_sensor(api, args, node):
    return api.get_or_create_sensor(
        name=args.sensor_name,
        sensor_type='camera',
        sensor_id=args.sensor_id,
        description='imported from "{}"'.format(args.basename),
        specs={'image_size': xmlutil.child_floats_split(node, 'SzIm')},
    )


def import_raw_image_referential(api, args, node, sensor):
    description = 'origin: top left corner of top left pixel, ' \
                  '+XY: raster pixel coordinates, ' \
                  '+Z: inverse depth (measured along the optical axis), ' \
                  'imported from "{}"'.format(args.basename)
    return api.get_or_create_referential(
        name='distorted',
        sensor=sensor,
        description=description,
        root=True,
    )


def import_orintglob_referential(api, args, node, sensor):
    description = 'origin: top left corner of top left pixel, ' \
                  '+XY: raster pixel coordinates, ' \
                  '+Z: inverse depth (measured along the optical axis), ' \
                  'imported from "{}"'.format(args.basename)
    return api.get_or_create_referential(
        name='raw',
        sensor=sensor,
        description=description,
    )


def import_distortion_referential(api, args, node, sensor, i):
    description = 'origin: top left corner of top left pixel, ' \
                  '+XY: raster pixel coordinates, ' \
                  '+Z: inverse depth (measured along the optical axis), ' \
                  'imported from "{}"'.format(args.basename)
    return api.get_or_create_referential(
        name='undistorted[{}]'.format(i),
        sensor=sensor,
        description=description,
    )


def import_euclidean_referential(api, args, node, sensor):
    description = 'origin: camera position, ' \
                  '+X: right of the camera, ' \
                  '+Y: bottom of the camera, ' \
                  '+Z: optical axis (in front of the camera), ' \
                  'imported from "{}"'.format(args.basename)
    return api.get_or_create_referential(
        name='camera',
        sensor=sensor,
        description=description,
    )


def import_pinhole_transform(api, args, node, source, target):
    name = '{}#FPP'.format(args.transfotree)
    return api.get_or_create_transfo(
        name, 'projective_pinhole', source, target,
        description='imported from "{}"'.format(args.basename),
        parameters={
            'focal': xmlutil.child_float(node, 'F'),
            'ppa': xmlutil.child_floats_split(node, 'PP'),
        },
        tdate=args.calibration_date,
        validity_start=args.validity_start,
        validity_end=args.validity_end,
    )


def import_orintglob_transform(api, args, node, source, target):
    affinity = xmlutil.child(node, 'Affinite')
    p = xmlutil.child_floats_split(affinity, 'I00')
    u = xmlutil.child_floats_split(affinity, 'V10')
    v = xmlutil.child_floats_split(affinity, 'V01')
    name = '{}#OrIntGlob'.format(args.transfotree)
    return api.get_or_create_transfo(
        name, 'affine_mat3x2', source, target,
        description='imported from "{}"'.format(args.basename),
        parameters={'mat3x2': [u[0], v[0], p[0], u[1], v[1], p[1]]},
        tdate=args.calibration_date,
        validity_start=args.validity_start,
        validity_end=args.validity_end,
        reverse=xmlutil.child_bool(node, 'C2M'),
    )


def import_distortion_transform(api, args, node, source, target, i):
    transfo_type, parameters = distortion.read_info(node)
    name = '{}#CalibDistortion[{}]'.format(args.transfotree, i)
    return api.get_or_create_transfo(
        name, transfo_type, source, target,
        description='imported from "{}"'.format(args.basename),
        parameters=parameters,
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
