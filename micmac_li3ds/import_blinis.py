import os
import datetime
import getpass
import logging
import xml.etree.ElementTree

from cliff.command import Command

from . import api


class ImportBlinis(Command):
    """ import a blinis file

        Create a sensor group if no sensor_id is provided. And create new
        referentials and transforms for the sensor group.
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
        self.blinis_file = None
        self.blinis_file_basename = None

    def get_parser(self, prog_name):
        self.log.debug(prog_name)
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--api-url', '-u',
            required=True,
            help='the li3ds API URL (required)')
        parser.add_argument(
            '--api-key', '-k',
            required=True,
            help='the li3ds API key (required)')
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
            'blinis_file',
            help='the blinis file')
        return parser

    def take_action(self, parsed_args):
        """
        Create or update a sensor group.

        If a sensor id is not provided on the command line then a sensor group
        is created, together with its base referential and other referentials
        based on the content of the blinis file. Then transfos grouped in
        a transfo tree are created.

        If a sensor id is provided on the command line then new transfos
        grouped in a transfo tree are created for the sensor group.
        """

        self.api = api.Api(parsed_args.api_url, parsed_args.api_key)
        self.sensor_id = parsed_args.sensor_id
        self.sensor_name = parsed_args.sensor_name
        self.blinis_file = parsed_args.blinis_file
        self.blinis_file_basename = os.path.basename(self.blinis_file)
        self.owner = parsed_args.owner or getpass.getuser()
        self.tdate = parsed_args.calibration_date
        self.validity_start = parsed_args.validity_start
        self.validity_end = parsed_args.validity_end

        root = self.parse_blinis(self.blinis_file)
        if root.tag != 'StructBlockCam':
            err = 'Error: root node is not StructBlockCam in blinis file'
            raise RuntimeError(err)

        key_im2_time_cam_node = root.find('KeyIm2TimeCam')
        if key_im2_time_cam_node is None:
            err = 'Error: no tag KeyIm2TimeCam in blinis file'
            raise RuntimeError(err)

        liaisons_shc_node = root.find('LiaisonsSHC')
        if key_im2_time_cam_node is None:
            err = 'Error: no tag LiaisonsSHC in blinis file'
            raise RuntimeError(err)

        param_orient_shc_nodes = liaisons_shc_node.findall('ParamOrientSHC')
        if not param_orient_shc_nodes:
            err = 'Error: no ParamOrientSHC tags in blinis file'
            raise RuntimeError(err)

        if not self.sensor_id and not self.sensor_name:
            # neither sensor_id nor sensor_name specified on the command
            # line, so create a sensor group
            sensor_id, base_referential, referentials = \
                self.create_sensor_group(
                    key_im2_time_cam_node.text, param_orient_shc_nodes)
        elif self.sensor_id:
            # look up sensor whose id is sensor_id, and raise an error
            # if there's no sensor with that id
            sensor = self.api.get_object_by_id('sensor', self.sensor_id)
            if not sensor:
                err = 'Error: sensor with id {:d} not in db'.format(
                        self.sensor_id)
                raise RuntimeError(err)
            if sensor['type'] != 'group':
                err = 'Error: sensor with id {:d} not of type "group"'.format(
                      self.sensor_id)
                raise RuntimeError(err)
            base_referential, referentials = \
                self.api.get_sensor_referentials(self.sensor_id)
        else:
            # we have a sensor name, look up sensor with this name, and
            # create a sensor with that name if there's no such sensor
            # in the database
            assert(self.sensor_name)
            sensor = self.api.get_object_by_name('sensor', self.sensor_name)
            if sensor:
                if sensor['type'] != 'group':
                    err = 'Error: sensor with id {:d} not of type ' \
                          '"group"'.format(sensor['id'])
                    raise RuntimeError(err)
                self.log.info('Sensor "{}" found in database.'
                              .format(self.sensor_name))
                base_referential, referentials = \
                    self.api.get_sensor_referentials(sensor['id'])
            else:
                sensor_id, base_referential, referentials = \
                    self.create_sensor_group(
                        self.sensor_name, param_orient_shc_nodes)

        # referential names to ids map
        referentials_map = {r['name']: r['id'] for r in referentials}

        transfo_ids = []
        for param_orient_shc_node in param_orient_shc_nodes:

            id_grp_node = param_orient_shc_node.find('IdGrp')
            referential_name = id_grp_node.text

            if referential_name not in referentials_map:
                # create referential
                description = 'referential for sensor group {:d}, ' \
                              'imported from {}'.format(
                                  sensor_id, self.blinis_file_basename)
                referential = {
                    'description': description,
                    'name': referential_name,
                    'root': True,
                    'sensor': sensor_id,
                    'srid': 0,
                }
                referential = self.api.create_object(
                    'referential', referential)
                referential_id = referential['id']
                self.log.info('Referential "{}" created.'.format(
                    referential_name))
                referentials_map[referential_name] = referential['id']

            referential_id = referentials_map[referential_name]

            # retrieve the "affine" transfo type
            transfo_type = self.api.get_object_by_name(
                'transfos/type', 'affine')
            if not transfo_type:
                err = 'Error: no transfo type "affine" available.'
                raise RuntimeError(err)

            matrix = self.create_transfo_matrix(param_orient_shc_node)
            description = 'affine transformation, imported from {}'.format(
                    self.blinis_file_basename)
            transfo = {
                'name': 'Affine_{}'.format(referential_name),
                'description': description,
                'parameters': {
                    'mat4x3': matrix
                },
                'source': base_referential['id'],
                'target': referential_id,
                'tdate': self.tdate or datetime.datetime.now().isoformat(),
                'transfo_type': transfo_type['id'],
            }
            if self.validity_start:
                transfo['validity_start'] = self.validity_start
            if self.validity_end:
                transfo['validity_end'] = self.validity_end
            transfo = self.api.create_object('transfo', transfo)
            transfo_id = transfo['id']
            self.log.info('Transfo "{}" created.'.format(transfo['name']))

            transfo_ids.append(transfo_id)

        if len(transfo_ids):
            transfotree = {
                'isdefault': True,
                'name': key_im2_time_cam_node.text,
                'owner': self.owner,
                'sensor_connections': False,
                'transfos': transfo_ids,
            }
            transfotree = self.api.create_object('transfotree', transfotree)
            self.log.info('Transfo tree "{}" created.'.format(
                transfotree['name']))

        self.log.info('Success!')

    def create_sensor_group(self, sensor_name, param_orient_shc_nodes):
        """
        Create a sensor group, its base referentials and its N non-base
        referentials. One non-base referential per IdGrp node.
        """

        # create the sensor
        description = 'sensor group, imported from {}'.format(
                self.blinis_file_basename)
        sensor = {
            'name': sensor_name,
            'brand': '',
            'description': description,
            'model': '',
            'serial_number': '',
            'specifications': {},
            'type': 'group',
        }
        sensor = self.api.create_object('sensor', sensor)
        sensor_id = sensor['id']
        self.log.info('Sensor "{}" created.'.format(sensor_name))

        # create the base referential
        description = 'base referential for sensor group {:d}, ' \
                      'imported from {}'.format(
                          sensor_id, self.blinis_file_basename)
        base_referential = {
            'description': description,
            'name': 'base',
            'root': True,
            'sensor': sensor_id,
            'srid': 0,
        }
        base_referential = self.api.create_object(
            'referential', base_referential)
        self.log.info('Referential "{}" created.'.format(
            base_referential['name']))

        referentials = []

        for param_orient_shc_node in param_orient_shc_nodes:
            id_grp_node = param_orient_shc_node.find('IdGrp')

            # create referential
            description = 'referential for sensor group {:d}, ' \
                          'imported from {}'.format(
                              sensor_id, self.blinis_file_basename)
            referential = {
                'description': description,
                'name': id_grp_node.text,
                'root': False,
                'sensor': sensor_id,
                'srid': 0,
            }
            referential = self.api.create_object('referential', referential)
            self.log.info('Referential "{}" created.'.format(
                referential['name']))
            referentials.append(referential)

        return sensor_id, base_referential, referentials

    @staticmethod
    def parse_blinis(blinis_file):
        tree = xml.etree.ElementTree.parse(blinis_file)
        return tree.getroot()

    @staticmethod
    def create_transfo_matrix(param_orient_shc_node):
        matrix = [[], [], []]
        vecteur_node = param_orient_shc_node.find('Vecteur')
        if vecteur_node is None:
            err = 'Error: no Vecteur tag in blinis file'
            raise RuntimeError(err)
        try:
            tx, ty, tz = map(float, vecteur_node.text.split())
        except ValueError:
            err = 'Error: Vecteur tag ' \
                  'includes non-parseable numbers in blinis file'
            raise RuntimeError(err)
        rot_node = param_orient_shc_node.find('Rot')
        if rot_node is None:
            err = 'Error: no Rot tag in blinis file'
            raise RuntimeError(err)
        for i, l in enumerate(('L1', 'L2', 'L3')):
            l_node = rot_node.find(l)
            if l_node is None:
                err = 'Error: no {} tag in blinis file'.format(l)
                raise RuntimeError(err)
            try:
                v1, v2, v3 = map(float, l_node.text.split())
            except ValueError:
                err = 'Error: {} tag includes non-parseable numbers ' \
                      'in blinis files'.format(l)
                raise RuntimeError(err)
            matrix[i].extend((v1, v2, v3, tx))
        return matrix
