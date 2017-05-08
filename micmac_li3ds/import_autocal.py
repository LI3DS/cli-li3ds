import os
import logging

from cliff.command import Command
from argparse import Namespace

from . import api as Api
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
        Api.add_arguments(parser)
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
            help='the list of autocal filename')
        return parser

    def take_action(self, parsed_args):
        """
        Create or update a camera sensor.
        """
        api = Api.Api(parsed_args, self.log)

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
                    'name': parsed_args.transfotree,
                    'owner': parsed_args.owner,
            },
        }
        for filename in parsed_args.filename:
            self.log.info('Importing {}'.format(filename))
            ApiObjs(args, filename).get_or_create(api)
            self.log.info('Success!\n')


class ApiObjs(Api.ApiObjs):
    def __init__(self, args, filename, transfotree=None, node=None):
        metadata = {
            'basename': os.path.basename(filename),
        }
        sensor = {'type': 'camera'}
        referential = {}
        transfotree = {}
        transfo = {}
        Api.update_obj(args, metadata, sensor, 'sensor')
        Api.update_obj(args, metadata, referential, 'referential')
        Api.update_obj(args, metadata, transfotree, 'transfotree')
        Api.update_obj(args, metadata, transfo, 'transfo')

        if not node:
            root = xmlutil.root(filename, 'ExportAPERO')
            node = xmlutil.child(root, 'CalibrationInternConique')

        xmlutil.child_check(node, 'KnownConv', 'eConvApero_DistM2C')

        self.sensor = Sensor(sensor, node)
        target = Referential.raw(self.sensor, referential)
        self.referentials = [target]
        self.transfos = []

        orintglob = node.find('OrIntGlob')
        if orintglob:
            source = Referential.distorted(self.sensor, referential)
            orintglob = Transfo.orintglob(source, target, transfo, orintglob)
            self.referentials.append(source)
            self.transfos.append(orintglob)
            target = source

        distos = reversed(xmlutil.children(node, 'CalibDistortion'))
        for i, disto in enumerate(distos):
            source = Referential.undistorted(self.sensor, referential, i)
            distortion = Transfo.distortion(source, target, transfo, disto, i)
            self.referentials.append(source)
            self.transfos.append(distortion)
            target = source

        source = Referential.camera(self.sensor, referential)
        pinhole = Transfo.pinhole(source, target, transfo, node)
        self.referentials.append(source)
        self.transfos.append(pinhole)

        self.transfotree = Api.Transfotree(self.transfos, transfotree)
        super().__init__()


class Sensor(Api.Sensor):
    def __init__(self, sensor, node):
        specs = {'image_size': xmlutil.child_floats_split(node, 'SzIm')}
        super().__init__(sensor, type='camera', specifications=specs)


class Referential:
    def distorted(sensor, referential):
        description = 'origin: top left corner of top left pixel, ' \
                      '+XY: raster pixel coordinates, ' \
                      '+Z: inverse depth (measured along the optical axis). ' \
                      '{description}'
        return Api.Referential(
            sensor, referential,
            name='distorted',
            description=description.format(**referential),
            root=True,
        )

    def raw(sensor, referential):
        description = 'origin: top left corner of top left pixel, ' \
                      '+XY: raster pixel coordinates, ' \
                      '+Z: inverse depth (measured along the optical axis). ' \
                      '{description}'
        return Api.Referential(
            sensor, referential,
            name='raw',
            description=description.format(**referential),
        )

    def undistorted(sensor, referential, i):
        description = 'origin: top left corner of top left pixel, ' \
                      '+XY: raster pixel coordinates, ' \
                      '+Z: inverse depth (measured along the optical axis). ' \
                      '{description}'
        return Api.Referential(
            sensor, referential,
            name='undistorted[{}]'.format(i),
            description=description.format(**referential),
        )

    def camera(sensor, referential):
        description = 'origin: camera position, ' \
                      '+X: right of the camera, ' \
                      '+Y: bottom of the camera, ' \
                      '+Z: optical axis (in front of the camera), ' \
                      '{description}'
        return Api.Referential(
            sensor, referential,
            name='camera',
            description=description.format(**referential),
        )


class Transfo:
    def pinhole(source, target, transfo, node):
        return Api.Transfo(
            source, target, transfo,
            name='{name}#projection'.format(**transfo),
            type_name='projective_pinhole',
            parameters={
                'focal': xmlutil.child_float(node, 'F'),
                'ppa': xmlutil.child_floats_split(node, 'PP'),
            },
        )

    def orintglob(source, target, transfo, node):
        affinity = xmlutil.child(node, 'Affinite')
        p = xmlutil.child_floats_split(affinity, 'I00')
        u = xmlutil.child_floats_split(affinity, 'V10')
        v = xmlutil.child_floats_split(affinity, 'V01')
        return Api.Transfo(
            source, target, transfo,
            name='{name}#orintglob'.format(**transfo),
            type_name='affine_mat3x2',
            parameters={'mat3x2': [u[0], v[0], p[0], u[1], v[1], p[1]]},
            reverse=xmlutil.child_bool(node, 'C2M'),
        )

    def distortion(source, target, transfo, node, i):
        transfo_type, parameters = distortion.read_info(node)
        return Api.Transfo(
            source, target, transfo,
            name='{name}#distortion[{i}]'.format(**transfo, i=i),
            type_name=transfo_type,
            parameters=parameters,
        )
