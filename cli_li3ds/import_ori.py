import os
import logging

from cliff.command import Command

from . import api
from . import xmlutil
from .import_autocal import ImportAutocal


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
        objs = api.ApiObjs(server)

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
            self.handle_ori(objs, args, filename)
            objs.get_or_create()
            self.log.info('Success!\n')

    @staticmethod
    def handle_ori(objs, args, filename):
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

        intrinsics = ImportAutocal.handle_autocal(objs, args, filename, None, node)
        sensor, transfotree, camera_ref, image_ref = intrinsics

        world = api.Referential(sensor, referential, name='world')
        image = api.Referential(sensor, referential, name='image')

        pose = transfo_pose(world, camera_ref, transfo, node)
        orint = transfo_orint(image_ref, image, transfo, node)
        transfos = [orint, pose]

        transfos.extend(transfotree.arrays['transfos'])

        objs.add(api.Transfotree(transfos, sensor, transfotree_all))


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
        parameters=[{'mat4x3': matrix}],
    )


def transfo_orint(source, target, transfo, node):
    p = xmlutil.child_floats_split(node, 'OrIntImaM2C/I00')
    u = xmlutil.child_floats_split(node, 'OrIntImaM2C/V10')
    v = xmlutil.child_floats_split(node, 'OrIntImaM2C/V01')
    return api.Transfo(
        source, target, transfo,
        name='{name}#OrIntImaM2C'.format(**transfo),
        type_name='affine_mat3x2',
        parameters=[{'mat3x2': [u[0], v[0], p[0], u[1], v[1], p[1]]}],
    )
