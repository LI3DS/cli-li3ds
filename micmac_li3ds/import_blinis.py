import os
import logging

from cliff.command import Command

from . import api
from . import xmlutil


class ImportBlinis(Command):
    """ import a blinis file

        Create a sensor group and corresponding referentials and transfos.
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
            help='the sensor group id (optional)')
        parser.add_argument(
            '--sensor-name', '-n',
            help='the sensor group name (optional)')
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
            help='the blinis file')
        return parser

    def take_action(self, parsed_args):
        """
        Create or update a sensor group.
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

        root = xmlutil.root(self.filename, 'StructBlockCam')
        nodes = xmlutil.children(root, 'LiaisonsSHC/ParamOrientSHC')

        sensor = self.get_or_create_sensor_group(root)
        base_ref = self.get_or_create_base_referential(root, sensor)

        transfos = []
        for node in nodes:
            ref = self.get_or_create_referential(node, sensor)
            transfo = self.get_or_create_transform(node, base_ref, ref)
            transfos.append(transfo)

        self.get_or_create_transfotree(root, transfos)

        self.log.info('Success!')

    def get_or_create_sensor_group(self, node):
        name = xmlutil.child(node, 'KeyIm2TimeCam').text.strip()
        return self.api.get_or_create_sensor(
            name=self.sensor_name or name,
            sensor_type='group',
            sensor_id=self.sensor_id,
            description='imported from "{}"'.format(self.basename),
        )

    def get_or_create_base_referential(self, node, sensor):
        description = 'base referential for sensor group {:d}, ' \
            'imported from "{}"'.format(sensor['id'], self.basename)
        return self.api.get_or_create_referential(
            name='base',
            sensor=sensor,
            description=description,
            root=True,
        )

    def get_or_create_referential(self, node, sensor):
        description = 'referential for sensor group {:d}, ' \
                      'imported from "{}"'.format(
                          sensor['id'], self.basename)
        return self.api.get_or_create_referential(
            name=xmlutil.child(node, 'IdGrp').text.strip(),
            sensor=sensor,
            description=description,
        )

    def get_or_create_transform(self, node, source, target):
        matrix = []
        p = xmlutil.child_floats_split(node, 'Vecteur')
        for i, l in enumerate(('Rot/L1', 'Rot/L2', 'Rot/L3')):
            matrix.extend(xmlutil.child_floats_split(node, l))
            matrix.append(p[i])

        return self.api.get_or_create_transfo(
            target['name'], 'affine_mat', source, target,
            description='imported from "{}"'.format(self.basename),
            parameters={'mat4x3': matrix},
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
