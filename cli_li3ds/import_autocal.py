import os
import logging

from cliff.command import Command

from . import api
from . import xmlutil
from . import distortion


class ImportAutocal(Command):
    """ import an autocal file
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
                    'name': parsed_args.transfotree,
                    'owner': parsed_args.owner,
            },
        }
        for filename in parsed_args.filename:
            self.log.info('Importing {}'.format(filename))
            self.handle_autocal(objs, args, filename)
            objs.get_or_create()
            self.log.info('Success!\n')

    @staticmethod
    def handle_autocal(objs, args, filename, node=None):
        if node:
            file_interne = node.findtext('FileInterne')
            if file_interne:
                dirname = os.path.dirname(filename)
                filename = file_interne.strip()
                if xmlutil.findtext(node, 'RelativeNameFI') == 'true':
                    filename = os.path.join(dirname, filename)
                node = None
            else:
                node = xmlutil.child(node, 'Interne')

        if not node:
            root = xmlutil.root(filename, 'ExportAPERO')
            node = xmlutil.child(root, 'CalibrationInternConique')

        metadata = {
            'basename': os.path.basename(filename),
        }
        sensor = {'type': 'camera'}
        referential = {}
        transfotree = {}
        transfo = {}
        api.update_obj(args, metadata, sensor, 'sensor')
        api.update_obj(args, metadata, referential, 'referential')
        api.update_obj(args, metadata, transfotree, 'transfotree')
        api.update_obj(args, metadata, transfo, 'transfo')

        xmlutil.child_check(node, 'KnownConv', 'eConvApero_DistM2C')

        sensor = sensor_camera(sensor, node)

        target = referential_raw(sensor, referential)
        transfos = []

        orintglob = node.find('OrIntGlob')
        if orintglob:
            source = referential_distorted(sensor, referential)
            orintglob = transfo_orintglob(source, target, transfo, orintglob)
            transfos.append(orintglob)
            target = source

        distos = reversed(xmlutil.children(node, 'CalibDistortion'))
        for i, disto in enumerate(distos):
            source = referential_undistorted(sensor, referential, i)
            distortion = transfo_distortion(source, target, transfo, disto, i)
            transfos.append(distortion)
            target = source

        source = referential_camera(sensor, referential)
        pinhole = transfo_pinhole(source, target, transfo, node)
        transfos.append(pinhole)

        transfotree = api.Transfotree(transfos, sensor, transfotree)
        objs.add(transfotree)

        return sensor, transfotree, source, target


def sensor_camera(sensor, node):
    specs = {'image_size': xmlutil.child_floats_split(node, 'SzIm')}
    return api.Sensor(sensor, type='camera', specifications=specs)


def referential_distorted(sensor, referential):
    description = 'origin: top left corner of top left pixel, ' \
                  '+XY: raster pixel coordinates, ' \
                  '+Z: inverse depth (measured along the optical axis). ' \
                  '{description}'
    return api.Referential(
        sensor, referential,
        name='distorted',
        description=description.format(**referential)
    )


def referential_raw(sensor, referential):
    description = 'origin: top left corner of top left pixel, ' \
                  '+XY: raster pixel coordinates, ' \
                  '+Z: inverse depth (measured along the optical axis). ' \
                  '{description}'
    return api.Referential(
        sensor, referential,
        name='raw',
        description=description.format(**referential),
    )


def referential_undistorted(sensor, referential, i):
    description = 'origin: top left corner of top left pixel, ' \
                  '+XY: raster pixel coordinates, ' \
                  '+Z: inverse depth (measured along the optical axis). ' \
                  '{description}'
    return api.Referential(
        sensor, referential,
        name='undistorted[{}]'.format(i),
        description=description.format(**referential),
    )


def referential_camera(sensor, referential):
    description = 'origin: camera position, ' \
                  '+X: right of the camera, ' \
                  '+Y: bottom of the camera, ' \
                  '+Z: optical axis (in front of the camera), ' \
                  '{description}'
    return api.Referential(
        sensor, referential,
        name='camera',
        description=description.format(**referential),
    )


def transfo_pinhole(source, target, transfo, node):
    return api.Transfo(
        source, target, transfo,
        name='{name}#projection'.format(**transfo),
        type_name='projective_pinhole',
        parameters=[{
            'focal': xmlutil.child_float(node, 'F'),
            'ppa': xmlutil.child_floats_split(node, 'PP'),
        }],
    )


def transfo_orintglob(source, target, transfo, node):
    affinity = xmlutil.child(node, 'Affinite')
    p = xmlutil.child_floats_split(affinity, 'I00')
    u = xmlutil.child_floats_split(affinity, 'V10')
    v = xmlutil.child_floats_split(affinity, 'V01')
    return api.Transfo(
        source, target, transfo,
        name='{name}#orintglob'.format(**transfo),
        type_name='affine_mat3x2',
        parameters=[{'mat3x2': [u[0], v[0], p[0], u[1], v[1], p[1]]}],
        reverse=xmlutil.child_bool(node, 'C2M'),
    )


def transfo_distortion(source, target, transfo, node, i):
    transfo_type, parameters = distortion.read_info(node)
    return api.Transfo(
        source, target, transfo,
        name='{name}#distortion[{i}]'.format(i=i, **transfo),
        type_name=transfo_type,
        parameters=[parameters],
    )
