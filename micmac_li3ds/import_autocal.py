import os
import logging

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

        self.sensor_id = parsed_args.sensor_id
        self.sensor_name = parsed_args.sensor_name
        self.filename = parsed_args.filename
        self.basename = os.path.basename(self.filename)
        self.owner = parsed_args.owner
        self.tdate = parsed_args.calibration_date
        self.validity_start = parsed_args.validity_start
        self.validity_end = parsed_args.validity_end
        self.indent = parsed_args.indent
        self.api = api.Api(
            parsed_args.api_url, parsed_args.api_key, self.log, self.indent)

        root = xmlutil.root(self.filename, 'ExportAPERO')
        node = xmlutil.child(root, 'CalibrationInternConique')
        xmlutil.child_check(node, 'KnownConv', 'eConvApero_DistM2C')

        sensor = self.get_or_create_camera_sensor(node)
        target = self.get_or_create_raw_image_referential(node, sensor)
        transfos = []

        orintglob_node = node.find('OrIntGlob')
        if orintglob_node:
            source = self.get_or_create_orintglob_referential(
                orintglob_node, sensor)
            distortion = self.get_or_create_orintglob_transform(
                orintglob_node, source, target)
            target = source
            transfos.append(distortion)

        disto_nodes = reversed(xmlutil.children(node, 'CalibDistortion'))
        for i, disto_node in enumerate(disto_nodes):
            source = self.get_or_create_distortion_referential(
                disto_node, sensor, i)
            distortion = self.get_or_create_distortion_transform(
                disto_node, source, target, i)
            target = source
            transfos.append(distortion)

        source = self.get_or_create_euclidean_referential(node, sensor)
        pinhole = self.get_or_create_pinhole_transform(node, source, target)
        transfos.append(pinhole)

        self.get_or_create_transfotree(node, transfos)

        self.log.info('Success!')

    def get_or_create_camera_sensor(self, node):
        return self.api.get_or_create_sensor(
            name=self.sensor_name or self.basename,
            sensor_type='camera',
            sensor_id=self.sensor_id,
            description='imported from "{}"'.format(self.basename),
            specs={'image_size': xmlutil.child_floats_split(node, 'SzIm')},
        )

    def get_or_create_raw_image_referential(self, node, sensor):
        description = 'origin: top left corner of top left pixel, ' \
                      '+XY: raster pixel coordinates, ' \
                      '+Z: inverse depth (measured along the optical axis), ' \
                      'imported from "{}"'.format(self.basename)
        return self.api.get_or_create_referential(
            name='rawImage',
            sensor=sensor,
            description=description,
            root=True,
        )

    def get_or_create_orintglob_referential(self, node, sensor):
        description = 'origin: top left corner of top left pixel, ' \
                      '+XY: raster pixel coordinates, ' \
                      '+Z: inverse depth (measured along the optical axis), ' \
                      'imported from "{}"'.format(self.basename)
        return self.api.get_or_create_referential(
            name='orIntImage',
            sensor=sensor,
            description=description,
        )

    def get_or_create_distortion_referential(self, node, sensor, i):
        description = 'origin: top left corner of top left pixel, ' \
                      '+XY: raster pixel coordinates, ' \
                      '+Z: inverse depth (measured along the optical axis), ' \
                      'imported from "{}"'.format(self.basename)
        return self.api.get_or_create_referential(
            name='undistorted_{}'.format(i+1),
            sensor=sensor,
            description=description,
        )

    def get_or_create_euclidean_referential(self, node, sensor):
        description = 'origin: camera position, ' \
                      '+X: right of the camera, ' \
                      '+Y: bottom of the camera, ' \
                      '+Z: optical axis (in front of the camera), ' \
                      'imported from "{}"'.format(self.basename)
        return self.api.get_or_create_referential(
            name='euclidean',
            sensor=sensor,
            description=description,
        )

    def get_or_create_pinhole_transform(self, node, source, target):
        return self.api.get_or_create_transfo(
            'projection', 'pinhole', source, target,
            description='imported from "{}"'.format(self.basename),
            parameters={
                'focal': xmlutil.child_float(node, 'F'),
                'ppa': xmlutil.child_floats_split(node, 'PP'),
            },
            tdate=self.tdate,
            validity_start=self.validity_start,
            validity_end=self.validity_end,
        )

    def get_or_create_orintglob_transform(self, node, source, target):
        affinity = xmlutil.child(node, 'Affinite')
        p = xmlutil.child_floats_split(affinity, 'I00')
        u = xmlutil.child_floats_split(affinity, 'V10')
        v = xmlutil.child_floats_split(affinity, 'V01')
        return self.api.get_or_create_transfo(
            'affinity', 'affine_3_2', source, target,
            description='imported from "{}"'.format(self.basename),
            parameters={'matrix': [u[0], v[0], p[0], u[1], v[1], p[1]]},
            tdate=self.tdate,
            validity_start=self.validity_start,
            validity_end=self.validity_end,
            reverse=xmlutil.child_bool(node, 'C2M'),
        )

    def get_or_create_distortion_transform(self, node, source, target, i):
        transfo_type, parameters = distortion.read_info(node)
        return self.api.get_or_create_transfo(
            'distortion_{}'.format(i+1), transfo_type, source, target,
            description='imported from "{}"'.format(self.basename),
            parameters=parameters,
            tdate=self.tdate,
            validity_start=self.validity_start,
            validity_end=self.validity_end,
        )

    def get_or_create_transfotree(self, node, transfos):
        return self.api.get_or_create_transfotree(
            name=self.basename,
            transfos=transfos,
            owner=self.owner,
        )
