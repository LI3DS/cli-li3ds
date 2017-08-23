import os
import re
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
            '--sensor-prefix', default='',
            help='camera sensor name prefix (optional, default is no prefix)')
        parser.add_argument(
            '--referential-prefix', default='',
            help='referential name prefix (optional, default is no prefix)')
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
            '--filename-pattern', '-p',
            help='filename pattern, files whose names do not match the pattern are skipped, '
                 'also used to get the sensor name from the file name '
                 '(e.g. "AutoCal_Foc-4400_Cam-Head(?P<sensor_name>\d+).xml") '
                 '(optional, default is None)')
        parser.add_argument(
            'filename', nargs='+',
            help='the list of autocal files')
        return parser

    def take_action(self, parsed_args):
        """
        Create or update a camera sensor.
        """
        server = api.ApiServer(parsed_args, self.log)
        objs = api.ApiObjs(server)

        filename_pattern = parsed_args.filename_pattern

        args = {
            'referential': {
                'prefix': parsed_args.referential_prefix,
            },
            'sensor': {
                'name': parsed_args.sensor,
                'prefix': parsed_args.sensor_prefix,
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
            sensor_name = None
            if filename_pattern:
                match = re.match(filename_pattern, os.path.basename(filename))
                if not match:
                    self.log.info('Does not match pattern, skip')
                    continue
                if 'sensor_name' in match.groupdict():
                    sensor_name = match.group('sensor_name')
            self.handle_autocal(objs, args, filename, sensor_name)
            objs.get_or_create()
            self.log.info('Success!\n')

    @staticmethod
    def handle_autocal(objs, args, filename, sensor_name, node=None):
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
            'sensor_name': sensor_name,
        }
        camera_sensor = {'name': '{sensor_name}'} if sensor_name else {}
        camera_referential = {'name': '{sensor_name}'} if sensor_name else {}
        referential = {}
        transfotree = {}
        transfo = {}
        api.update_obj(args, metadata, camera_sensor, 'sensor')
        api.update_obj(args, metadata, camera_referential, 'referential')
        api.update_obj(args, metadata, referential, 'referential')
        api.update_obj(args, metadata, transfotree, 'transfotree')
        api.update_obj(args, metadata, transfo, 'transfo')

        xmlutil.child_check(node, 'KnownConv', 'eConvApero_DistM2C')

        camera_sensor = sensor_camera(camera_sensor, node)

        target = referential_raw(camera_sensor, referential)

        transfos = []

        orintglob = node.find('OrIntGlob')
        if orintglob:
            source = referential_distorted(camera_sensor, referential)
            orintglob = transfo_orintglob(source, target, transfo, orintglob)
            transfos.append(orintglob)
            target = source

        distos = reversed(xmlutil.children(node, 'CalibDistortion'))
        for i, disto in enumerate(distos):
            source = referential_undistorted(camera_sensor, referential, i)
            distortion = transfo_distortion(source, target, transfo, disto, i)
            transfos.append(distortion)
            target = source

        source = referential_camera(camera_sensor, camera_referential)
        pinhole = transfo_pinhole(source, target, transfo, node)
        transfos.append(pinhole)

        transfotree = api.Transfotree(transfos, transfotree)
        objs.add(transfotree)

        return camera_sensor, transfotree, source, target


def sensor_camera(sensor, node):
    if 'prefix' in sensor:
        sensor['name'] = sensor['prefix'] + sensor['name']
        del sensor['prefix']
    specs = {'image_size': xmlutil.child_floats_split(node, 'SzIm')}
    return api.Sensor(sensor, type='camera', specifications=specs)


def referential_distorted(sensor, referential):
    description = 'origin: top left corner of top left pixel, ' \
                  '+XY: raster pixel coordinates, ' \
                  '+Z: inverse depth (measured along the optical axis). ' \
                  '{description}'
    referential = dict(referential)
    if 'prefix' in referential:
        name = '{prefix}distorted'.format(**referential)
        del referential['prefix']
    return api.Referential(
        sensor, referential, name=name,
        description=description.format(**referential)
    )


def referential_raw(sensor, referential):
    description = 'origin: top left corner of top left pixel, ' \
                  '+XY: raster pixel coordinates, ' \
                  '+Z: inverse depth (measured along the optical axis). ' \
                  '{description}'
    referential = dict(referential)
    name = 'raw'
    if 'prefix' in referential:
        name = '{prefix}{name}'.format(prefix=referential['prefix'], name=name)
        del referential['prefix']
    return api.Referential(
        sensor, referential, name=name,
        description=description.format(**referential),
    )


def referential_undistorted(sensor, referential, i):
    description = 'origin: top left corner of top left pixel, ' \
                  '+XY: raster pixel coordinates, ' \
                  '+Z: inverse depth (measured along the optical axis). ' \
                  '{description}'
    referential = dict(referential)
    name = 'undistorted[{}]'.format(i)
    if 'prefix' in referential:
        name = '{prefix}{name}'.format(prefix=referential['prefix'], name=name)
        del referential['prefix']
    return api.Referential(
        sensor, referential, name=name,
        description=description.format(**referential),
    )


def referential_camera(sensor, referential):
    description = 'origin: camera position, ' \
                  '+X: right of the camera, ' \
                  '+Y: bottom of the camera, ' \
                  '+Z: optical axis (in front of the camera), ' \
                  '{description}'
    referential = dict(referential)
    if 'prefix' in referential:
        referential['name'] = '{prefix}{name}'.format(**referential)
        del referential['prefix']
    return api.Referential(
        sensor, referential,
        description=description.format(**referential),
    )


def transfo_pinhole(source, target, transfo, node):
    return api.Transfo(
        source, target, transfo,
        name='{name}#projection'.format(**transfo),
        type_name='projective_pinhole',
        func_signature=['focal', 'ppa'],
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
        func_signature=['mat3x2'],
        parameters=[{'mat3x2': [u[0], v[0], p[0], u[1], v[1], p[1]]}],
        reverse=xmlutil.child_bool(node, 'C2M'),
    )


def transfo_distortion(source, target, transfo, node, i):
    transfo_type, parameters, func_signature = distortion.read_info(node)
    return api.Transfo(
        source, target, transfo,
        name='{name}#distortion[{i}]'.format(i=i, **transfo),
        type_name=transfo_type,
        func_signature=func_signature,
        parameters=[parameters],
    )
