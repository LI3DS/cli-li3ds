import os
import getpass
import logging
import json

from cliff.command import Command

from . import api
from . import distortion
from . import xmlutil


class ImportAutocal(Command):
    """ import an autocal file
    """

    log = logging.getLogger(__name__)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api = None
        self.sensor_id = None
        self.sensor_name = None
        self.owner = None
        self.tdate = None
        self.validity_start = None
        self.validity_end = None
        self.filename = None
        self.basename = None
        self.indent = None

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
            '--sensor-id', '-s',
            type=int,
            help='the camera sensor id (optional)')
        parser.add_argument(
            '--sensor-name', '-n',
            help='the camera sensor name (optional)')
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
            'filename',
            help='the autocal file')
        return parser

    def take_action(self, parsed_args):
        """
        Create or update a camera sensor.
        """

        self.api = api.Api(parsed_args.api_url, parsed_args.api_key)
        self.sensor_id = parsed_args.sensor_id
        self.sensor_name = parsed_args.sensor_name
        self.filename = parsed_args.filename
        self.basename = os.path.basename(self.filename)
        self.owner = parsed_args.owner or getpass.getuser()
        self.tdate = parsed_args.calibration_date
        self.validity_start = parsed_args.validity_start
        self.validity_end = parsed_args.validity_end
        self.indent = parsed_args.indent
        if self.api.staging:
            self.log.info("Staging mode (no api url/key provided).")

        root = xmlutil.root(self.filename, 'ExportAPERO')
        node = xmlutil.child(root, 'CalibrationInternConique')

        sensor = self.get_or_create_camera_sensor(node)

        # get or create euclidean, idealImage and rawImage referentials
        ref_eu = self.get_or_create_eu_referential(node, sensor)
        ref_ii = self.get_or_create_ii_referential(node, sensor)
        ref_ri = self.get_or_create_ri_referential(node, sensor)

        # get or create pinhole and distortion transforms
        pinh = self.get_or_create_pinh_transform(node, ref_eu, ref_ii)
        dist = self.get_or_create_dist_transform(node, ref_ii, ref_ri)

        transfotree = self.get_or_create_transfotree(node, [pinh, dist])

        self.log.info('Success!')

    def get_or_create_camera_sensor(self, node):
        image_size = xmlutil.child_floats_split(node,'SzIm')
        description = 'camera sensor, imported from "{}"'.format(
                self.basename)
        sensor = {
            'id': self.sensor_id,
            'name': self.sensor_name or self.basename,
            'description': description,
            'type': 'camera',
            'brand': '',
            'model': '',
            'serial_number': '',
            'specifications': {
                'image_size': image_size,
            },
        }
        return self.get_or_create('sensor', sensor)

    def get_or_create_ri_referential(self, node, sensor):
        description = 'origin: top left corner of top left pixel, ' \
                      '+XY: raster pixel coordinates, ' \
                      '+Z: inverse depth (measured along the optical axis), ' \
                      'imported from "{}"'.format(self.basename)
        referential = {
            'description': description,
            'name': 'rawImage',
            'root': True,
            'sensor': sensor['id'],
            'srid': 0,
        }
        return self.get_or_create('referential', referential)

    def get_or_create_ii_referential(self, node, sensor):
        description = 'origin: top left corner of top left pixel, ' \
                      '+XY: raster pixel coordinates, ' \
                      '+Z: inverse depth (measured along the optical axis), ' \
                      'imported from "{}"'.format(self.basename)
        referential = {
            'description': description,
            'name': 'idealImage',
            'root': False,
            'sensor': sensor['id'],
            'srid': 0,
        }
        return self.get_or_create('referential', referential)

    def get_or_create_eu_referential(self, node, sensor):
        description = 'origin: camera position, ' \
                      '+X: right of the camera, ' \
                      '+Y: bottom of the camera, ' \
                      '+Z: optical axis (in front of the camera), ' \
                      'imported from "{}"'.format(self.basename)
        referential = {
            'description': description,
            'name': 'euclidean',
            'root': False,
            'sensor': sensor['id'],
            'srid': 0,
        }
        return self.get_or_create('referential', referential)

    def get_or_create_pinh_transform(self, node, ref_eu, ref_ii):
        transfo = {
            'name': 'projection',
            'parameters': {
                'focal': xmlutil.child_float(node, 'F'),
                'ppa': xmlutil.child_floats_split(node, 'PP'),
            },
            'tdate': self.tdate,
            'validity_start': self.validity_start,
            'validity_end': self.validity_end,
            'transfo_type': 'pinhole',
        }
        return self.get_or_create_transfo(transfo, ref_eu, ref_ii)

    def get_or_create_dist_transform(self, node, ref_ii, ref_ri):
        calib_distortion_node = xmlutil.child(node, 'CalibDistortion')
        mod_unif_node = xmlutil.child(calib_distortion_node, 'ModUnif')
        typ, states, params = distortion.read_info(mod_unif_node)

        transfo = {
            'name': 'distortion',
            'parameters': {
                'states': states,
                'params': params,
            },
            'tdate': self.tdate,
            'validity_start': self.validity_start,
            'validity_end': self.validity_end,
            'transfo_type': typ,
        }
        return self.get_or_create_transfo(transfo, ref_ii, ref_ri)

    def get_or_create_transfotree(self, node, transfos):
        transfotree = {
            'name': self.basename,
            'owner': self.owner,
            'isdefault': True,
            'sensor_connections': False,
            'transfos': [t['id'] for t in transfos],
        }
        return self.get_or_create('transfotree', transfotree)

    def get_or_create(self, typ, obj):
        obj, info = self.api.get_or_create_object(typ, obj)
        self.log.info('{} {}({}) "{}"'.format(info, typ, obj['id'], obj['name']))
        self.log.debug(json.dumps(obj, indent=self.indent))
        return obj

    def get_or_create_transfo(self, transfo, source, target):
        transfo_type = {
            'name': transfo['transfo_type'],
            'func_signature': list(transfo['parameters'].keys()),
        }
        transfo_type = self.get_or_create('transfos/type', transfo_type)
        transfo['transfo_type'] = transfo_type['id']
        transfo['source'] = source['id']
        transfo['target'] = target['id']
        transfo['description'] = '"{}" transformation, imported from "{}"' \
            .format(transfo_type['name'], self.basename)
        return self.get_or_create('transfo', transfo)

