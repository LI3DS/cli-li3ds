import logging
import requests
import json

from cliff.command import Command


class AddSensor(Command):
    """ Add a sensor """

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
            'json_file',
            help='the JSON file including the sensor description')
        return parser

    def take_action(self, parsed_args):
        sensors_url = parsed_args.api_url.rstrip('/') + '/sensors/'
        headers = {'X-API-KEY': parsed_args.api_key}
        with open(parsed_args.json_file, 'r') as f:
            json_obj = json.load(f)
            resp = requests.post(sensors_url, json=json_obj, headers=headers)
            if resp.status_code != 201:
                err = 'Adding sensor failed (status code: {})'.format(
                      resp.status_code)
                raise RuntimeError(err)
            self.log.info('Success!')
            self.log.info(resp.text)
