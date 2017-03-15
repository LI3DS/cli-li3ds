import logging
import xml.etree.ElementTree

from cliff.command import Command

from . import api


class ImportBlinis(Command):
    """ Import a blinis file """

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
            required=True,
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

        sensor = api.get_sensor(sensor_id, api_url, api_key)
        assert(sensor is not None)

        root = self.parse_blinis(parsed_args.blinis_file)
        assert(root.tag == 'StructBlockCam')

        key_im2_time_cam_node = root.find('KeyIm2TimeCam')
        assert(key_im2_time_cam_node is not None)

        # create the sensor group referential
        resp = api.create_referential(
                key_im2_time_cam_node.text, sensor_id, api_url, api_key)
        self.log.info('Success!')
        self.log.info(resp.text)

        liaisons_shc_node = root.find('LiaisonsSHC')
        assert(liaisons_shc_node is not None)

        for param_orient_shc_node in liaisons_shc_node:
            assert(param_orient_shc_node.tag == 'ParamOrientSHC')

            id_grp_node = param_orient_shc_node.find('IdGrp')
            sub_sensor_id = int(id_grp_node.text)
            sub_sensor = api.get_sensor(sub_sensor_id, api_url, api_key)
            assert(sub_sensor is not None)

    @staticmethod
    def parse_blinis(blinis_file):
        tree = xml.etree.ElementTree.parse(blinis_file)
        return tree.getroot()
