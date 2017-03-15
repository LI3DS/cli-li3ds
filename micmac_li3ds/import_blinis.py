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
        api_url = parsed_args.api_url
        api_key = parsed_args.api_key

        root = self.parse_blinis(parsed_args.blinis_file)
        if root.tag != 'StructBlockCam':
            err = 'Parsing blinis file failed: root is not StructBlockCam'
            raise RuntimeError(err)

        key_im2_time_cam_node = root.find('KeyIm2TimeCam')
        if key_im2_time_cam_node is None:
            err = 'Parsing blinis file failed: no tag KeyIm2TimeCam'
            raise RuntimeError(err)

        # create a sensor group if sensor_id is not specified on the
        # command line arguments
        if sensor_id is None:
            sensor = {
                'brand': '',
                'description': '',
                'model': key_im2_time_cam_node.text,
                'serial_number': '',
                'short_name': '',
                'specifications': {},
                'type': 'group',
            }
            sensor = api.create_sensor(sensor, api_url, api_key)
            sensor_id = sensor['id']
            self.log.info('Sensor {:d} created.'.format(sensor_id))
        else:
            sensor = api.get_sensor(sensor_id, api_url, api_key)
            if not sensor:
                err = 'Sensor id {:d} not in db'.format(sensor_id)
                raise RuntimeError(err)
            if sensor['type'] != 'group':
                err = 'Sensor id {:d} is not of type "group"'.format(sensor_id)

        # create the sensor group referential
        # FIXME description?
        base_referential = {
            'description': '',
            'name': key_im2_time_cam_node.text,
            'root': True,
            'sensor': sensor_id,
            'srid': 0,
        }
        base_referential = api.create_referential(
                base_referential, api_url, api_key)
        base_referential_id = base_referential['id']
        self.log.info('Referential {:d} created.'.format(base_referential_id))

        liaisons_shc_node = root.find('LiaisonsSHC')
        if key_im2_time_cam_node is None:
            err = 'Parsing blinis file failed: no tag LiaisonsSHC'
            raise RuntimeError(err)

        param_orient_shc_nodes = liaisons_shc_node.findall('ParamOrientSHC')

        transfo_ids = []
        for param_orient_shc_node in param_orient_shc_nodes:
            id_grp_node = param_orient_shc_node.find('IdGrp')

            # FIXME description?
            referential = {
                'description': '',
                'name': id_grp_node.text,
                'root': True,
                'sensor': sensor_id,
                'srid': 0,
            }
            referential = api.create_referential(referential, api_url, api_key)
            referential_id = referential['id']
            self.log.info('Referential {:d} created.'.format(referential_id))

            # FIXME
            # validity_start, validity_end and transfo_type currently
            # hard-coded
            transfo = {
                'description': '',
                'parameters': {},
                'source': base_referential_id,
                'target': referential_id,
                'tdate': datetime.datetime.now().isoformat(),
                'validity_start': '0001-01-01T00:00:00+00',
                'validity_end': '9999-12-31T23:59:59+01',
                'transfo_type': 2,
            }
            transfo = api.create_transfo(transfo, api_url, api_key)
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
            transfotree = api.create_transfotree(transfotree, api_url, api_key)
            transfotree_id = transfotree['id']
            self.log.info('Transfo tree {:d} created.'.format(transfotree_id))

        self.log.info('Success!')

    @staticmethod
    def parse_blinis(blinis_file):
        tree = xml.etree.ElementTree.parse(blinis_file)
        return tree.getroot()
