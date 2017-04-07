import os
import datetime
import getpass
import logging

from cliff.command import Command

from . import api
from . import xmlutil


class ImportOrimatis(Command):
    """ import an Ori-Matis file
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
        self.orimatis_file = None
        self.orimatis_file_basename = None

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
            'orimatis_file',
            help='the orimatis file')
        return parser



    def take_action(self, parsed_args):
        """
        Create or update a camera sensor.
        """

        self.api = api.Api(parsed_args.api_url, parsed_args.api_key)
        self.sensor_id = parsed_args.sensor_id
        self.sensor_name = parsed_args.sensor_name
        self.orimatis_file = parsed_args.orimatis_file
        self.orimatis_file_basename = os.path.basename(self.orimatis_file)
        self.owner = parsed_args.owner or getpass.getuser()
        self.tdate = parsed_args.calibration_date
        self.validity_start = parsed_args.validity_start
        self.validity_end = parsed_args.validity_end

        root = xmlutil.root(self.orimatis_file,'orientation')
        geometry_node   = xmlutil.child(root, 'geometry')
        intrinseque_node  = xmlutil.child(geometry_node, 'intrinseque')
        extrinseque_node  = xmlutil.child(geometry_node, 'extrinseque')
        sensor_node  = xmlutil.child(intrinseque_node, 'sensor')

        systeme   = xmlutil.child(extrinseque_node, 'systeme').text
        grid_alti = xmlutil.child(extrinseque_node, 'grid_alti').text

        self.srid = 0
        if systeme is 'Lambert93' and grid_alti is 'RAF09' :
            self.srid = 2154

        if not self.sensor_id and not self.sensor_name:
            # neither sensor_id nor sensor_name specified on the command
            # line, so create a camera sensor
            sensor, ref_ri, ref_ii, ref_eu, ref_wo = self.create_camera_sensor()
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
                ref_ri, ref_ii, ref_eu, ref_wo = \
                    self.api.get_sensor_referentials(sensor['id'])
            else:
                sensor, ref_ri, ref_ii, ref_eu, ref_wo = self.create_camera_sensor()

        # create the "pinhole" and "distortion" transforms
        pinhole    = self.create_pinhole_transform(sensor_node, ref_eu, ref_ii)
        distortion = self.create_distortion_transform(sensor_node, ref_ii, ref_ri)
        pose       = self.create_pose_transform(extrinseque_node, ref_wo, ref_eu)

        # create the transfo tree
        transfotree = {
            'isdefault': True,
            'name': self.orimatis_file_basename,
            'owner': self.owner,
            'sensor_connections': False,
            'transfos': [pose['id'], pinhole['id'], distortion['id']],
        }
        transfotree = self.api.create_object('transfotree', transfotree)
        self.log.info('Transfo tree "{}" created.'.format(
            transfotree['name']))

        self.log.info('Success!')

    def create_camera_sensor(self):
        """
        Create a camera sensor, and three referentials.
        """

        sensor_name = self.sensor_name or self.orimatis_file_basename

        ret = []

        # create the sensor
        description = 'camera sensor, imported from {}'.format(
                self.orimatis_file_basename)
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
                          sensor_id, self.orimatis_file_basename)
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
                          sensor_id, self.orimatis_file_basename)
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
                          sensor_id, self.orimatis_file_basename)
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

        # create the world referential
        description = 'world referential, ' \
                      'imported from {}'.format(
                          sensor_id, self.orimatis_file_basename)
        referential = {
            'description': description,
            'name': 'world',
            'root': False,
            'sensor': sensor_id,
            'srid': self.srid,
        }
        referential = self.api.create_object('referential', referential)
        self.log.info('Referential "{}" created.'.format(referential['name']))

        ret.append(referential)

        return ret

    def create_pinhole_transform(self, node, ref_eu, ref_ii):

        image_size_node = xmlutil.child(node, 'image_size')
        ppa_node = xmlutil.child(node, 'ppa')

        width  = xmlutil.childFloat(image_size_node, 'width')
        height = xmlutil.childFloat(image_size_node, 'height')
        focal  = xmlutil.childFloat(ppa_node, 'focale')
        ppa    = [ xmlutil.childFloat(ppa_node, 'c'), xmlutil.childFloat(ppa_node, 'l') ]

        # retrieve the "pinhole" transfo type
        transfo_type = self.api.get_object_by_name('transfos/type', 'pinhole')
        if not transfo_type:
            err = 'Error: no transfo type "pinhole" available.'
            raise RuntimeError(err)

        description = 'projective transformation, imported from {}'.format(
                      self.orimatis_file_basename)

        transfo = {
            'name': 'projection',
            'description': description,
            'parameters': {
                'focal': focal,
                'ppa': ppa,
            },
            'source': ref_eu['id'],
            'target': ref_ii['id'],
            'transfo_type': transfo_type['id'],
        }
        if self.tdate:
            transfo['tdate'] = self.tdate
        if self.validity_start:
            transfo['validity_start'] = self.validity_start
        if self.validity_end:
            transfo['validity_end'] = self.validity_end
        transfo = self.api.create_object('transfo', transfo)
        self.log.info('Transfo "{}" created.'.format(transfo['name']))

        return transfo

    def create_distortion_transform(self, node, ref_ii, ref_ri):

        distortion_node = xmlutil.child(node, 'distortion')
        pps_node = xmlutil.child(distortion_node, 'pps')
        pps = [ xmlutil.childFloat(pps_node, 'c'), xmlutil.childFloat(pps_node, 'l') ]
        r3 = xmlutil.childFloat(distortion_node, 'r3')
        r5 = xmlutil.childFloat(distortion_node, 'r5')
        r7 = xmlutil.childFloat(distortion_node, 'r7')

        # retrieve the transfo type
        transfo_type = self.api.get_object_by_name('transfos/type', 'distortionr357')
        if not transfo_type:
            err = 'Error: no transfo type "{}" available.'.format('distortionr357')
            raise RuntimeError(err)

        description = 'distortion transformation, imported from {}'.format(
                      self.orimatis_file_basename)
        transfo = {
            'name': 'distortion',
            'description': description,
            'parameters': {
                'pps': pps,
                'coef': [ r3, r5, r7 ]
            },
            'source': ref_ii['id'],
            'target': ref_ri['id'],
            'transfo_type': transfo_type['id'],
        }
        if self.tdate:
            transfo['tdate'] = self.tdate
        if self.validity_start:
            transfo['validity_start'] = self.validity_start
        if self.validity_end:
            transfo['validity_end'] = self.validity_end
        transfo = self.api.create_object('transfo', transfo)
        self.log.info('Transfo "{}" created.'.format(transfo['name']))

        return transfo

    def create_pose_transform(self, node, ref_world, ref_camera):

        sommet_node  = xmlutil.child(node, 'sommet')
        rotation_node  = xmlutil.child(node, 'rotation')
        mat3d_node  = xmlutil.child(rotation_node, 'mat3d')
        l1_node  = xmlutil.child(xmlutil.child(mat3d_node, 'l1'), 'pt3d')
        l2_node  = xmlutil.child(xmlutil.child(mat3d_node, 'l2'), 'pt3d')
        l3_node  = xmlutil.child(xmlutil.child(mat3d_node, 'l3'), 'pt3d')

        Image2Ground = xmlutil.childBool(rotation_node, 'Image2Ground')
        if Image2Ground :
            source, target = ref_camera, ref_world
        else :
            source, target = ref_world, ref_camera

        tx = xmlutil.childFloat(sommet_node, 'easting')
        ty = xmlutil.childFloat(sommet_node, 'northing')
        tz = xmlutil.childFloat(sommet_node, 'altitude')

        x1 =  xmlutil.childFloat(l1_node,'x');
        x2 =  xmlutil.childFloat(l2_node,'x');
        x3 =  xmlutil.childFloat(l3_node,'x');
        y1 =  xmlutil.childFloat(l1_node,'y');
        y2 =  xmlutil.childFloat(l2_node,'y');
        y3 =  xmlutil.childFloat(l3_node,'y');
        z1 =  xmlutil.childFloat(l1_node,'z');
        z2 =  xmlutil.childFloat(l2_node,'z');
        z3 =  xmlutil.childFloat(l3_node,'z');

        matrix = [
            x1, y1, z1, tx,
            x2, y2, z2, ty,
            x3, y3, z3, tz
        ]

        # retrieve the transfo type
        transfo_type = self.api.get_object_by_name('transfos/type', 'affine43')
        if not transfo_type:
            err = 'Error: no transfo type "{}" available.'.format('affine43')
            raise RuntimeError(err)

        description = 'pose transformation, imported from {}'.format(
                      self.orimatis_file_basename)
        transfo = {
            'name': 'pose',
            'description': description,
            'parameters': {
                'mat4x3': matrix,
            },
            'source': source['id'],
            'target': target['id'],
            'transfo_type': transfo_type['id'],
        }
        if self.tdate:
            transfo['tdate'] = self.tdate
        if self.validity_start:
            transfo['validity_start'] = self.validity_start
        if self.validity_end:
            transfo['validity_end'] = self.validity_end
        transfo = self.api.create_object('transfo', transfo)
        self.log.info('Transfo "{}" created.'.format(transfo['name']))

        return transfo
