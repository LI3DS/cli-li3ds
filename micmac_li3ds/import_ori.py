import os
import logging

from cliff.command import Command

from . import api
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
        api.add_arguments(parser)
        parser.add_argument(
            '--sensor-id', '-i',
            type=int,
            help='the camera sensor id (optional)')
        parser.add_argument(
            '--sensor', '-s',
            help='the camera sensor name (optional)')
        parser.add_argument(
            '--transfotree',
            help='the transfotree name (optional)')
        parser.add_argument(
            '--intrinsic-transfotree',
            help='the intrinsic transfotree name (optional)')
        parser.add_argument(
            '--transfo', '-t',
            help='the transfo basename (optional)')
        parser.add_argument(
            '--calibration', '-d',
            help='the calibration datetime (optional')
        parser.add_argument(
            '--validity-start',
            help='validity start date for transfos (optional, '
                 'default is valid since always)')
        parser.add_argument(
            '--validity-end',
            help='validity end date for transfos (optional, '
                 'default is valid until forever)')
        parser.add_argument(
            'filename', nargs='+',
            help='the list of Ori Micmac filenames')
        return parser

    def take_action(self, parsed_args):
        """
        Create or update a sensor group.
        """
        server = api.ApiServer(parsed_args, self.log)

        args = {
            'sensor': {
                'name': parsed_args.sensor,
                'id': parsed_args.sensor_id,
            },
            'transfo': {
                'name': parsed_args.transfo,
                'tdate': parsed_args.calibration,
                'validity_start': parsed_args.validity_start,
                'validity_end': parsed_args.validity_end,
            },
            'transfotree': {
                    'name': parsed_args.intrinsic_transfotree,
                    'owner': parsed_args.owner,
            },
            'transfotree_all': {
                    'name': parsed_args.transfotree,
                    'owner': parsed_args.owner,
            },
        }
        for filename in parsed_args.filename:
            self.log.info('Importing {}'.format(filename))
            ApiObjs(args, filename).get_or_create(server)
            self.log.info('Success!\n')


class ApiObjs(api.ApiObjs):
    def __init__(self, args, filename):
        metadata = {
            'basename': os.path.basename(filename),
        }
        referential = {}
        transfo = {}
        transfotree = {}
        transfotree_all = {}
        api.update_obj(args, metadata, referential, 'referential')
        api.update_obj(args, metadata, transfo, 'transfo')
        api.update_obj(args, metadata, transfotree, 'transfotree')
        api.update_obj(args, metadata, transfotree_all, 'transfotree_all')

        root = xmlutil.root(filename, 'ExportAPERO')
        node = xmlutil.child(root, 'OrientationConique')
        xmlutil.child_check(node, 'ConvOri/KnownConv', 'eConvApero_DistM2C')
        xmlutil.child_check(node, 'TypeProj', 'eProjStenope')

        intrinsics = import_autocal.ApiObjs(args, filename, node)
        self.sensor = intrinsics.sensor
        self.transfotree_int = intrinsics.transfotree

        self.world = api.Referential(self.sensor, referential, name='world')
        self.image = api.Referential(self.sensor, referential, name='image')

        self.pose = transfo_pose(self.world, intrinsics.camera, transfo, node)
        self.orint = transfo_orint(intrinsics.image, self.image, transfo, node)
        self.transfos = [self.orint, self.pose]
        self.transfos.extend(self.transfotree_int.arrays['transfos'])
        self.transfotree = api.Transfotree(self.transfos, transfotree_all)
        super().__init__()


def transfo_pose(source, target, transfo, node):
    xmlutil.child_check(node, 'Externe/KnownConv', 'eConvApero_DistM2C')
    p = xmlutil.child_floats_split(node, 'Externe/Centre')
    rot = xmlutil.child(node, 'Externe/ParamRotation/CodageMatr')
    matrix = []
    for i, l in enumerate(('L1', 'L2', 'L3')):
        matrix.extend(xmlutil.child_floats_split(rot, l))
        matrix.append(p[i])
    return api.Transfo(
        source, target, transfo,
        name='{name}#Externe'.format(**transfo),
        type_name='affine_mat4x3',
        parameters={'mat4x3': matrix},
    )


def transfo_orint(source, target, transfo, node):
    p = xmlutil.child_floats_split(node, 'OrIntImaM2C/I00')
    u = xmlutil.child_floats_split(node, 'OrIntImaM2C/V10')
    v = xmlutil.child_floats_split(node, 'OrIntImaM2C/V01')
    return api.Transfo(
        source, target, transfo,
        name='{name}#OrIntImaM2C'.format(**transfo),
        type_name='affine_mat3x2',
        parameters={'mat3x2': [u[0], v[0], p[0], u[1], v[1], p[1]]},
    )
