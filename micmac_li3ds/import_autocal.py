import os
import datetime
import getpass
import logging
import xml.etree.ElementTree

from cliff.command import Command

from . import api
from . import util


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
        self.autocal_file = None
        self.autocal_file_basename = None

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
            'autocal_file',
            help='the autocal file')
        return parser

    def take_action(self, parsed_args):
        """
        Create or update a camera sensor.
        """

        self.api = api.Api(parsed_args.api_url, parsed_args.api_key)
        self.sensor_id = parsed_args.sensor_id
        self.sensor_name = parsed_args.sensor_name
        self.autocal_file = parsed_args.autocal_file
        self.autocal_file_basename = os.path.basename(self.autocal_file)
        self.owner = parsed_args.owner or getpass.getuser()
        self.tdate = parsed_args.calibration_date
        self.validity_start = parsed_args.validity_start
        self.validity_end = parsed_args.validity_end

        root = self.parse_autocal(self.autocal_file)
        if root.tag != 'ExportAPERO':
            err = 'Error: root node is not ExportAPERO in autocal file'
            raise RuntimeError(err)

        calibration_intern_conique_node = root.find('CalibrationInternConique')
        if calibration_intern_conique_node is None:
            err = 'Error: no tag CalibrationInternConique in autocal file'
            raise RuntimeError(err)

        sz_im_node = calibration_intern_conique_node.find('SzIm')
        if sz_im_node is None:
            err = 'Error: no tag SzIm in autocal file'
            raise RuntimeError(err)

        if not self.sensor_id and not self.sensor_name:
            # neither sensor_id nor sensor_name specified on the command
            # line, so create a camera sensor
            sensor, ref_ri, ref_ii, ref_eu = self.create_camera_sensor()
        elif self.sensor_id:
            # look up sensor whose id is sensor_id, and raise an error
            # if there's no sensor with that id
            sensor = self.api.get_object_by_id('sensor', self.sensor_id)
            if not sensor:
                err = 'Error: sensor with id {:d} not in db'.format(
                        self.sensor_id)
                raise RuntimeError(err)
            if sensor['type'] != 'camera':
                err = 'Error: sensor with id {:d} not of type "camera"'.format(
                      self.sensor_id)
                raise RuntimeError(err)
            ref_ri, ref_ii, ref_eu = self.api.get_sensor_referentials(
                    self.sensor_id)
        else:
            # we have a sensor name, look up sensor with this name, and
            # create a sensor with that name if there's no such sensor
            # in the database
            assert(self.sensor_name)
            sensor = self.api.get_object_by_name('sensor', self.sensor_name)
            if sensor:
                if sensor['type'] != 'camera':
                    err = 'Error: sensor with id {:d} not of type ' \
                          '"camera"'.format(sensor['id'])
                    raise RuntimeError(err)
                self.log.info('Sensor "{}" found in database.'
                              .format(self.sensor_name))
                ref_ri, ref_ii, ref_eu = \
                    self.api.get_sensor_referentials(sensor['id'])
            else:
                sensor, ref_ri, ref_ii, ref_eu = self.create_camera_sensor()

        # create the "pinhole" and "distortion" transforms
        pinhole = self.create_pinhole_transform(
                calibration_intern_conique_node, ref_eu, ref_ii)
        distortion = self.create_distortion_transform(
               calibration_intern_conique_node, ref_ii, ref_ri)

        # create the transfo tree
        transfotree = {
            'isdefault': True,
            'name': self.autocal_file_basename,
            'owner': self.owner,
            'sensor_connections': False,
            'transfos': [pinhole['id'], distortion['id']],
        }
        transfotree = self.api.create_object('transfotree', transfotree)
        self.log.info('Transfo tree "{}" created.'.format(
            transfotree['name']))

        self.log.info('Success!')

    def create_camera_sensor(self):
        """
        Create a camera sensor, and three referentials.
        """

        sensor_name = self.sensor_name or self.autocal_file_basename

        ret = []

        # create the sensor
        description = 'camera sensor, imported from {}'.format(
                self.autocal_file_basename)
        sensor = {
            'name': sensor_name,
            'brand': '',
            'description': description,
            'model': '',
            'serial_number': '',
            'specifications': {},
            'type': 'camera',
        }
        sensor = self.api.create_object('sensor', sensor)
        sensor_id = sensor['id']
        self.log.info('Sensor "{}" created.'.format(sensor_name))

        ret.append(sensor)

        # create the rawImage referential
        description = 'origin: top left corner or top left pixel, ' \
                      '+XY: raster pixel coordinates, ' \
                      '+Z: inverse depth (measured along the optical axis), ' \
                      'imported from {}'.format(
                          sensor_id, self.autocal_file_basename)
        referential = {
            'description': description,
            'name': 'rawImage',
            'root': True,
            'sensor': sensor_id,
            'srid': 0,
        }
        referential = self.api.create_object('referential', referential)
        self.log.info('Referential "{}" created.'.format(referential['name']))

        ret.append(referential)

        # create the idealImage referential
        description = 'origin: top left corner or top left pixel, ' \
                      '+XY: raster pixel coordinates, ' \
                      '+Z: inverse depth (measured along the optical axis), ' \
                      'imported from {}'.format(
                          sensor_id, self.autocal_file_basename)
        referential = {
            'description': description,
            'name': 'idealImage',
            'root': False,
            'sensor': sensor_id,
            'srid': 0,
        }
        referential = self.api.create_object('referential', referential)
        self.log.info('Referential "{}" created.'.format(referential['name']))

        ret.append(referential)

        # create the euclidean referential
        description = 'origin: camera position, ' \
                      '+X: right of the camera, ' \
                      '+Y: bottom of the camera, ' \
                      '+Z: optical axis (in front of the camera), ' \
                      'imported from {}'.format(
                          sensor_id, self.autocal_file_basename)
        referential = {
            'description': description,
            'name': 'euclidean',
            'root': False,
            'sensor': sensor_id,
            'srid': 0,
        }
        referential = self.api.create_object('referential', referential)
        self.log.info('Referential "{}" created.'.format(referential['name']))

        ret.append(referential)

        return ret

    def create_pinhole_transform(
            self, calibration_intern_conique_node, ref_eu, ref_ii):

        # retrieve the "pinhole" transfo type
        transfo_type = self.api.get_object_by_name(
            'transfos/type', 'pinhole')
        if not transfo_type:
            err = 'Error: no transfo type "pinhole" available.'
            raise RuntimeError(err)

        pp_node = calibration_intern_conique_node.find('PP')
        if pp_node is None:
            err = 'Error: no tag PP in autocal file'
            raise RuntimeError(err)
        try:
            ppa = list(map(float, pp_node.text.split()))
        except ValueError:
            err = 'Error: PP tag ' \
                  'includes non-parseable numbers in autocal file'
            raise RuntimeError(err)

        f_node = calibration_intern_conique_node.find('F')
        if f_node is None:
            err = 'Error: no tag F in autocal file'
            raise RuntimeError(err)
        try:
            focal = float(f_node.text)
        except ValueError:
            err = 'Error: F tag ' \
                  'includes non-parseable numbers in autocal file'
            raise RuntimeError(err)

        description = 'projective transformation, imported from {}'.format(
                      self.autocal_file_basename)

        transfo = {
            'name': 'projection',
            'description': description,
            'parameters': {
                'focal': focal,
                'ppa': ppa,
            },
            'source': ref_eu['id'],
            'target': ref_ii['id'],
            'tdate': self.tdate or datetime.datetime.now().isoformat(),
            'transfo_type': transfo_type['id'],
        }
        if self.validity_start:
            transfo['validity_start'] = self.validity_start
        if self.validity_end:
            transfo['validity_end'] = self.validity_end
        transfo = self.api.create_object('transfo', transfo)
        self.log.info('Transfo "{}" created.'.format(transfo['name']))

        return transfo

    def create_distortion_transform(self, node, ref_ii, ref_ri):

        calib_distortion_node = util.child(node, 'CalibDistortion')
        mod_unif_node = util.child(calib_distortion_node, 'ModUnif')
        type_modele_node = util.child(mod_unif_node, 'TypeModele')

        # retrieve the transfo type
        name = type_modele_node.text
        transfo_type = self.api.get_object_by_name('transfos/type', name)
        if not transfo_type:
            err = 'Error: no transfo type "{}" available.'.format(name)
            raise RuntimeError(err)

        description = 'distortion transformation, imported from {}'.format(
                      self.autocal_file_basename)

        transfo = {
            'name': 'distortion',
            'description': description,
            'parameters': {
            },
            'source': ref_ii['id'],
            'target': ref_ri['id'],
            'tdate': self.tdate or datetime.datetime.now().isoformat(),
            'transfo_type': transfo_type['id'],
        }
        if self.validity_start:
            transfo['validity_start'] = self.validity_start
        if self.validity_end:
            transfo['validity_end'] = self.validity_end
        transfo = self.api.create_object('transfo', transfo)
        self.log.info('Transfo "{}" created.'.format(transfo['name']))

        return transfo

    @staticmethod
    def parse_autocal(autocal_file):
        tree = xml.etree.ElementTree.parse(autocal_file)
        return tree.getroot()
