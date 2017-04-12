import os
import getpass
import logging
import json

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
        description = 'sensor group, imported from "{}"'.format(
                self.basename)
        sensor = {
            'id': self.sensor_id,
            'name': self.sensor_name or name,
            'brand': '',
            'description': description,
            'model': '',
            'serial_number': '',
            'specifications': {},
            'type': 'group',
        }
        return self.get_or_create('sensor', sensor)

    def get_or_create_base_referential(self, node, sensor):
        description = 'base referential for sensor group {:d}, ' \
            'imported from "{}"'.format(sensor['id'], self.basename)
        referential = {
            'description': description,
            'name': 'base',
            'root': True,
            'sensor': sensor['id'],
            'srid': 0,
        }
        return self.get_or_create('referential', referential)

    def get_or_create_referential(self, node, sensor):
        description = 'referential for sensor group {:d}, ' \
                      'imported from "{}"'.format(
                          sensor['id'], self.basename)
        referential = {
            'name': xmlutil.child(node, 'IdGrp').text.strip(),
            'description': description,
            'root': False,
            'sensor': sensor['id'],
            'srid': 0,
        }
        return self.get_or_create('referential', referential)

    def get_or_create_transform(self, node, source, target):
        matrix = []
        p = xmlutil.child_floats_split(node, 'Vecteur')
        for i, l in enumerate(('Rot/L1', 'Rot/L2', 'Rot/L3')):
            matrix.extend(xmlutil.child_floats_split(node, l))
            matrix.append(p[i])

        transfo = {
            'name': target['name'],
            'parameters': {'mat4x3': matrix},
            'transfo_type': 'affine_mat',
            'tdate': self.tdate,
            'validity_start': self.validity_start,
            'validity_end': self.validity_end,
        }
        return self.get_or_create_transfo(transfo, source, target)

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
        obj, code = self.api.get_or_create_object(typ, obj)
        info = '{} {}({}) "{}"'.format(code, typ, obj['id'], obj['name'])
        self.log.info(info)
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
