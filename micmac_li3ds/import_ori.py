import os
import logging

from cliff.command import Command
from argparse import Namespace

from . import api as li3ds
from . import xmlutil
from . import import_autocal


class ImportOri(Command):
    """ import a Micmac Orientation file

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
            '--intrinsic-transfotree',
            help='the intrinsic transfotree name (optional)')
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
            help='the list of Ori Micmac filenames')
        return parser

    def take_action(self, args):
        """
        Create or update a sensor group.
        """
        api = li3ds.Api(args.api_url, args.api_key, args.no_proxy,
                        self.log, args.indent)
        for filename in args.filenames:
            self.log.info('Importing {}'.format(filename))
            import_orientation(api, args, filename)
        self.log.info('Success!\n')


def import_orientation(api, args, filename):
    args = Namespace(**vars(args))
    args.basename = os.path.basename(filename)
    args.transfotree = args.transfotree or args.basename

    root = xmlutil.root(filename, 'ExportAPERO')
    node = xmlutil.child(root, 'OrientationConique')
    xmlutil.child_check(node, 'ConvOri/KnownConv', 'eConvApero_DistM2C')
    xmlutil.child_check(node, 'TypeProj', 'eProjStenope')

    sensor, ref_ri, ref_eu, transfotree = import_intrinsics(
        api, args, filename, node)

    ref_wo = import_world_referential(api, args, node, sensor)
    ref_oi = import_orint_referential(api, args, node, sensor)

    pose = import_pose_transform(api, args, node, ref_wo, ref_eu)
    orint = import_orint_transform(api, args, node, ref_ri, ref_oi)
    transfotree = import_transfotree(
        api, args, node, transfotree, [orint, pose])

    return transfotree


def import_intrinsics(api, args, filename, node):
    file_interne = node.findtext('FileInterne')
    if file_interne:
        dirname = os.path.dirname(filename)
        filename = file_interne.strip()
        if xmlutil.child(node, 'RelativeNameFI').text.strip() == 'true':
            filename = os.path.join(dirname, filename)
        tt = args.intrinsic_transfotree or os.path.basename(filename)
        return import_autocal.import_intrinsics(api, args, filename, tt)
    else:
        node = xmlutil.child(node, 'Interne')
        filename = '{}#Interne'.format(args.basename)
        tt = args.intrinsic_transfotree or filename
        return import_autocal.import_intrinsics(api, args, filename, tt, node)


def import_world_referential(api, args, node, sensor):
    return api.get_or_create_referential(
        name='world',
        sensor=sensor,
        description='imported from "{}"'.format(args.basename),
    )


def import_orint_referential(api, args, node, sensor):
    return api.get_or_create_referential(
        name='image',
        sensor=sensor,
        description='imported from "{}"'.format(args.basename),
    )


def import_pose_transform(api, args, node, source, target):
    xmlutil.child_check(node, 'Externe/KnownConv', 'eConvApero_DistM2C')
    p = xmlutil.child_floats_split(node, 'Externe/Centre')
    rot = xmlutil.child(node, 'Externe/ParamRotation/CodageMatr')
    matrix = []
    for i, l in enumerate(('L1', 'L2', 'L3')):
        matrix.extend(xmlutil.child_floats_split(rot, l))
        matrix.append(p[i])
    name = '{}#Externe'.format(args.transfotree)
    return api.get_or_create_transfo(
        name, 'affine_mat4x3', source, target,
        description='imported from "{}"'.format(args.basename),
        parameters={'mat4x3': matrix},
        tdate=args.calibration_date,
        validity_start=args.validity_start,
        validity_end=args.validity_end,
    )


def import_orint_transform(api, args, node, source, target):
    p = xmlutil.child_floats_split(node, 'OrIntImaM2C/I00')
    u = xmlutil.child_floats_split(node, 'OrIntImaM2C/V10')
    v = xmlutil.child_floats_split(node, 'OrIntImaM2C/V01')
    name = '{}#OrIntImaM2C'.format(args.transfotree)
    return api.get_or_create_transfo(
        name, 'affine_mat3x2', source, target,
        description='imported from "{}"'.format(args.basename),
        parameters={'mat3x2': [u[0], v[0], p[0], u[1], v[1], p[1]]},
        tdate=args.calibration_date,
        validity_start=args.validity_start,
        validity_end=args.validity_end,
    )


def import_transfotree(api, args, node, basetree, transfos):
    return api.get_or_create_transfotree(
        name=args.transfotree,
        transfos=transfos,
        owner=args.owner,
        basetree=basetree,
    )
