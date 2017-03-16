import os
import datetime
import logging
import xml.etree.ElementTree

from cliff.command import Command

from . import api


class ImportBlinis(Command):
    """ Import a blinis file

        Create a sensor group if no sensor_id is provided. And create new
        referentials and transforms for the sensor group.
    """

    log = logging.getLogger(__name__)

    api_url = None
    api_key = None

    def get_parser(self, prog_name):
        self.log.debug(prog_name)
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--api-url', '-u',
            required=True,
            help='the li3ds API URL')
        parser.add_argument(
            '--api-key', '-k',
            required=True,
            help='the li3ds API key')
        parser.add_argument(
            '--sensor-id', '-s',
            type=int,
            help='the sensor group id')
        parser.add_argument(
            'blinis_file',
            help='the blinis file')
        return parser

    def take_action(self, parsed_args):

        sensor_id = parsed_args.sensor_id
        api_url = self.api_url = parsed_args.api_url
        api_key = self.api_key = parsed_args.api_key
        blinis_file = self.blinis_file = parsed_args.blinis_file
        self.blinis_file_basename = os.path.basename(blinis_file)

        root = self.parse_blinis(blinis_file)
        if root.tag != 'StructBlockCam':
            err = 'Parsing blinis file failed: root is not StructBlockCam'
            raise RuntimeError(err)

        key_im2_time_cam_node = root.find('KeyIm2TimeCam')
        if key_im2_time_cam_node is None:
            err = 'Parsing blinis file failed: no tag KeyIm2TimeCam'
            raise RuntimeError(err)

        liaisons_shc_node = root.find('LiaisonsSHC')
        if key_im2_time_cam_node is None:
            err = 'Parsing blinis file failed: no tag LiaisonsSHC'
            raise RuntimeError(err)

        param_orient_shc_nodes = liaisons_shc_node.findall('ParamOrientSHC')
        if not param_orient_shc_nodes:
            err = 'Parsing blinis file failed: no ParamOrientSHC tags'
            raise RuntimeError(err)

        # create a sensor group if sensor_id not specified on command line
        if sensor_id is None:
            sensor_id, base_referential, referentials = \
                self.create_sensor_group(
                    key_im2_time_cam_node.text, param_orient_shc_nodes)
        else:
            sensor = api.get_object_by_id(
                    'sensor', sensor_id, api_url, api_key)
            if not sensor:
                err = 'Sensor id {:d} not in db'.format(sensor_id)
                raise RuntimeError(err)
            if sensor['type'] != 'group':
                err = 'Sensor id {:d} is not of type "group"'.format(sensor_id)
            base_referential, referentials = api.get_sensor_referentials(
                    sensor_id, api_url, api_key)

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
                referential = api.create_object(
                        'referential', referential, api_url, api_key)
                referential_id = referential['id']
                self.log.info('Referential {:d} created.'.format(
                    referential_id))
                referentials_map[referential_name] = referential['id']

            referential_id = referentials_map[referential_name]

            # FIXME
            # validity_start, validity_end and transfo_type currently
            # hard-coded
            description = 'affine transformation, imported from {}'.format(
                          self.blinis_file_basename)
            transfo = {
                'description': description,
                'parameters': {},
                'source': base_referential['id'],
                'target': referential_id,
                'tdate': datetime.datetime.now().isoformat(),
                'transfo_type': 1,
            }
            transfo = api.create_object('transfo', transfo, api_url, api_key)
            transfo_id = transfo['id']
            self.log.info('Transfo {:d} created.'.format(transfo_id))

            transfo_ids.append(transfo_id)

        if len(transfo_ids):
            # FIXME owner?
            transfotree = {
                'isdefault': True,
                'name': key_im2_time_cam_node.text,
                'owner': '',
                'sensor_connections': False,
                'transfos': transfo_ids,
            }
            transfotree = api.create_object(
                    'transfotree', transfotree, api_url, api_key)
            transfotree_id = transfotree['id']
            self.log.info('Transfo tree {:d} created.'.format(transfotree_id))

        self.log.info('Success!')

    def create_sensor_group(self, sensor_name, param_orient_shc_nodes):
        """
        Create a sensor group, its base referentials and its N non-base
        referentials. One non-base referential per IdGrp node.
        """

        assert(self.api_url)
        assert(self.api_key)

        # create the sensor
        description = 'sensor group, imported from {}'.format(
                self.blinis_file_basename)
        sensor = {
            'brand': '',
            'description': description,
            'model': sensor_name,
            'serial_number': '',
            'short_name': '',
            'specifications': {},
            'type': 'group',
        }
        sensor = api.create_object(
                'sensor', sensor, self.api_url, self.api_key)
        sensor_id = sensor['id']
        self.log.info('Sensor {:d} created.'.format(sensor_id))

        # create the base referential
        description = 'base referential for sensor group {:d}, ' \
                      'imported from {}'.format(
                          sensor_id, self.blinis_file_basename)
        base_referential = {
            'description': description,
            'name': sensor_name,
            'root': True,
            'sensor': sensor_id,
            'srid': 0,
        }
        base_referential = api.create_object(
                'referential', base_referential, self.api_url, self.api_key)
        base_referential_id = base_referential['id']
        self.log.info('Referential {:d} created.'.format(base_referential_id))

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
            referential = api.create_object(
                    'referential', referential, self.api_url, self.api_key)
            referential_id = referential['id']
            self.log.info('Referential {:d} created.'.format(referential_id))
            referentials.append(referential)

        return sensor_id, base_referential, referentials

    @staticmethod
    def parse_blinis(blinis_file):
        tree = xml.etree.ElementTree.parse(blinis_file)
        return tree.getroot()
