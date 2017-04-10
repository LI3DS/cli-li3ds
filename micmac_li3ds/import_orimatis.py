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
        self.file = None
        self.file_basename = None
        self.transfo_defaults = {}

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
        self.file = parsed_args.orimatis_file
        self.file_basename = os.path.basename(self.file)
        self.owner = parsed_args.owner or getpass.getuser()
        self.tdate = parsed_args.calibration_date
        self.validity_start = parsed_args.validity_start
        self.validity_end = parsed_args.validity_end
        if self.tdate:
            self.transfo_defaults['tdate'] = self.tdate
        if self.validity_start:
            self.transfo_defaults['validity_start'] = self.validity_start
        if self.validity_end:
            self.transfo_defaults['validity_end'] = self.validity_end

        root = xmlutil.root(self.file,'orientation')

        sensor = self.get_or_create_camera_sensor(root)

        ref_wo = self.get_or_create_wo_referential(root, sensor)
        ref_eu = self.get_or_create_eu_referential(root, sensor)
        ref_ii = self.get_or_create_ii_referential(root, sensor)
        ref_ri = self.get_or_create_ri_referential(root, sensor)

        pinhole     = self.get_or_create_pinh_transform(root, ref_eu, ref_ii)
        distortion  = self.get_or_create_dist_transform(root, ref_ii, ref_ri)
        pose        = self.get_or_create_pose_transform(root, ref_wo, ref_eu)

        transfotree = self.get_or_create_transfotree(root, [pinhole,distortion,pose])

        self.log.info('Success!')

    def get_or_create_camera_sensor(self, node):
        """
        Create a camera sensor
        """

        sensor_name = self.sensor_name or self.file_basename

        # create the sensor
        description = 'camera sensor, imported from {}'.format(
                self.file_basename)
        sensor = {
            'name': sensor_name,
            'description': description,
            'type': 'camera',
            'brand': '',
            'model': '',
            'serial_number': '',
            'specifications': {},
        }

        return self.api.get_or_create_object('sensor', sensor, [], self.log)


    def get_or_create_wo_referential(self, node, sensor):

        systeme   = xmlutil.child(node, 'geometry/extrinseque/systeme').text
        grid_alti = xmlutil.child(node, 'geometry/extrinseque/grid_alti').text

        srid = 0
        if systeme is 'Lambert93' and grid_alti is 'RAF09' :
            srid = 2154

        description = 'world referential ({}/{}), ' \
                      'imported from {}'.format(
                          systeme, grid_alti, self.file_basename)
        referential = {
            'description': description,
            'name': 'world',
            'root': False,
            'sensor': sensor['id'],
            'srid': srid,
        }
        return self.api.get_or_create_object('referential', referential, ['sensor'], self.log)


    def get_or_create_ri_referential(self, node, sensor):
        description = 'origin: top left corner or top left pixel, ' \
                      '+XY: raster pixel coordinates, ' \
                      '+Z: inverse depth (measured along the optical axis), ' \
                      'imported from {}'.format(self.file_basename)
        referential = {
            'description': description,
            'name': 'rawImage',
            'root': True,
            'sensor': sensor['id'],
            'srid': 0,
        }
        return self.api.get_or_create_object('referential', referential, ['sensor'], self.log)


    def get_or_create_ii_referential(self, node, sensor):
        description = 'origin: top left corner or top left pixel, ' \
                      '+XY: raster pixel coordinates, ' \
                      '+Z: inverse depth (measured along the optical axis), ' \
                      'imported from {}'.format(self.file_basename)
        referential = {
            'description': description,
            'name': 'idealImage',
            'root': False,
            'sensor': sensor['id'],
            'srid': 0,
        }
        return self.api.get_or_create_object('referential', referential, ['sensor'], self.log)


    def get_or_create_eu_referential(self, node, sensor):
        description = 'origin: camera position, ' \
                      '+X: right of the camera, ' \
                      '+Y: bottom of the camera, ' \
                      '+Z: optical axis (in front of the camera), ' \
                      'imported from {}'.format(self.file_basename)
        referential = {
            'description': description,
            'name': 'euclidean',
            'root': False,
            'sensor': sensor['id'],
            'srid': 0,
        }
        return self.api.get_or_create_object('referential', referential, ['sensor'], self.log)


    def get_or_create_pinh_transform(self, node, ref_eu, ref_ii):

        node  = xmlutil.child(node, 'geometry/intrinseque/sensor')
        transfo_type = {
            'name': 'pinhole',
            'func_signature': [ 'focal', 'ppa' ],
        }
        transfo_type = self.api.get_or_create_object('transfos/type', transfo_type, [], self.log)

        description = '"{}" transformation, imported from "{}"'.format(
                      transfo_type['name'], self.file_basename)
        # image_size  = xmlutil.childFloats(node, 'image_size', ['width', 'height'])
        transfo = self.transfo_defaults
        transfo.update({
            'name': 'projection',
            'description': description,
            'parameters': {
                'focal': xmlutil.childFloat(node, 'ppa/focale'),
                'ppa': xmlutil.childFloats(node, 'ppa', ['c','l']),
            },
            'source': ref_eu['id'],
            'target': ref_ii['id'],
            'transfo_type': transfo_type['id'],
        })
        return self.api.get_or_create_object('transfo', transfo, ['source','target'], self.log)


    def get_or_create_dist_transform(self, node, ref_ii, ref_ri):

        node  = xmlutil.child(node, 'geometry/intrinseque/sensor')
        transfo_type = {
            'name': 'distortionr357',
            'func_signature': [ 'pps', 'coef' ],
        }
        transfo_type = self.api.get_or_create_object('transfos/type', transfo_type, [], self.log)

        description = '"{}" transformation, imported from "{}"'.format(
                      transfo_type['name'], self.file_basename)
        transfo = self.transfo_defaults
        transfo.update({
            'name': 'distortion',
            'description': description,
            'parameters': {
                'pps': xmlutil.childFloats(node, 'distortion/pps', ['c', 'l']),
                'coef': xmlutil.childFloats(node, 'distortion', ['r3', 'r5', 'r7']),
            },
            'source': ref_ii['id'],
            'target': ref_ri['id'],
            'transfo_type': transfo_type['id'],
        })
        return self.api.get_or_create_object('transfo', transfo, ['source','target'], self.log)


    def get_or_create_pose_transform(self, node, ref_world, ref_camera):

        node  = xmlutil.child(node, 'geometry/extrinseque')
        transfo_type = {
            'name': 'affine43',
            'func_signature': [ 'mat4x3' ],
        }
        transfo_type = self.api.get_or_create_object('transfos/type', transfo_type, [], self.log)

        if xmlutil.childBool(node, 'rotation/Image2Ground') :
            source, target = ref_camera, ref_world
        else :
            source, target = ref_world, ref_camera

        tx = xmlutil.childFloat(node, 'sommet/easting')
        ty = xmlutil.childFloat(node, 'sommet/northing')
        tz = xmlutil.childFloat(node, 'sommet/altitude')
        l1  = xmlutil.childFloats(node, 'rotation/mat3d/l1/pt3d', ['x','y','z'])
        l2  = xmlutil.childFloats(node, 'rotation/mat3d/l2/pt3d', ['x','y','z'])
        l3  = xmlutil.childFloats(node, 'rotation/mat3d/l3/pt3d', ['x','y','z'])

        matrix = []
        matrix.extend(l1)
        matrix.append(tx)
        matrix.extend(l2)
        matrix.append(ty)
        matrix.extend(l3)
        matrix.append(tz)

        description = '"{}" transformation, imported from "{}"'.format(
                      transfo_type['name'], self.file_basename)
        transfo = self.transfo_defaults
        transfo.update({
            'name': 'pose',
            'description': description,
            'parameters': {
                'mat4x3': matrix,
            },
            'source': source['id'],
            'target': target['id'],
            'transfo_type': transfo_type['id'],
        })
        return self.api.get_or_create_object('transfo', transfo, ['source','target'], self.log)


    def get_or_create_transfotree(self, node, transfos):
        """
        Create the transfo tree
        """
        transfotree = {
            'name': self.file_basename,
            'owner': self.owner,
            'isdefault': True,
            'sensor_connections': False,
            'transfos': list(map(lambda t: t['id'], transfos)),
        }
        return self.api.get_or_create_object('transfotree', transfotree, ['transfos'], self.log)