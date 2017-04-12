import os
import getpass
import logging
import json
import datetime
import pytz

from cliff.command import Command

from . import api
from . import xmlutil


class ImportOrimatis(Command):
    """ import an Ori-Matis file
    """

    log = logging.getLogger(__name__)

    def __init__(self, *args, **kwargs):
        super(ImportOrimatis, self).__init__(*args, **kwargs)
        self.api = None
        self.sensor_id = None
        self.sensor_name = None
        self.owner = None
        self.tdate = None
        self.validity_start = None
        self.validity_end = None
        self.file = None
        self.file_basename = None
        self.transfo = {}
        self.staging = True
        self.staging_id = 0
        self.indent = None

    def get_parser(self, prog_name):
        self.log.debug(prog_name)
        parser = super(ImportOrimatis, self).get_parser(prog_name)
        parser.add_argument(
            '--api-url', '-u',
            help='the li3ds API URL (optional)')
        parser.add_argument(
            '--api-key', '-k',
            help='the li3ds API key (optional)')
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
            '--indent', type=int,
            help='number of spaces for pretty print indenting')
        parser.add_argument(
            'orimatis_file',
            help='the orimatis file')
        return parser

    def take_action(self, parsed_args):
        """
        Create or update a camera sensor.
        """

        if parsed_args.api_url or parsed_args.api_key:
            self.api = api.Api(parsed_args.api_url, parsed_args.api_key)
        else:
            self.log.info("Staging mode (no api url/key provided).")
        self.sensor_id = parsed_args.sensor_id
        self.sensor_name = parsed_args.sensor_name
        self.file = parsed_args.orimatis_file
        self.file_basename = os.path.basename(self.file)
        self.owner = parsed_args.owner or getpass.getuser()
        self.tdate = parsed_args.calibration_date
        self.validity_start = parsed_args.validity_start
        self.validity_end = parsed_args.validity_end
        self.indent = parsed_args.indent
        if self.tdate:
            self.transfo['tdate'] = self.tdate
        if self.validity_start:
            self.transfo['validity_start'] = self.validity_start
        if self.validity_end:
            self.transfo['validity_end'] = self.validity_end

        root = xmlutil.root(self.file, 'orientation')

        self.metadata = self.get_metadata(root)
        self.acquisition_datetime = self.get_acquisition_datetime(root)
        self.calibration_datetime = self.get_calibration_datetime(root)

        sensor = self.get_or_create_camera_sensor(root)

        # get or create world, euclidean, idealImage and rawImage referentials
        ref_wo = self.get_or_create_wo_referential(root, sensor)
        ref_eu = self.get_or_create_eu_referential(root, sensor)
        ref_ii = self.get_or_create_ii_referential(root, sensor)
        ref_ri = self.get_or_create_ri_referential(root, sensor)

        # get or create pinhole, distortion and pose transforms
        pinh = self.get_or_create_pinh_transform(root, ref_eu, ref_ii)
        dist = self.get_or_create_dist_transform(root, ref_ii, ref_ri)
        pose = self.get_or_create_pose_transforms(root, ref_wo, ref_eu)

        transfos = [pinh, dist, pose[0]]
        transfotree = self.get_or_create_transfotree(root, transfos)

        metadata_dump = json.dumps(self.metadata, indent=self.indent)
        self.log.info('[metadata] {}'.format(metadata_dump))

        self.log.info('[{}] Success!'.format(transfotree['id']))

    def get_acquisition_datetime(self, node):

        node = xmlutil.child(node, 'auxiliarydata/image_date')
        Y = xmlutil.child_int(node, 'year')
        m = xmlutil.child_int(node, 'month')
        d = xmlutil.child_int(node, 'day')
        H = xmlutil.child_int(node, 'hour')
        M = xmlutil.child_int(node, 'minute')
        x = xmlutil.child_float(node, 'second')
        S = int(x)
        s = int(1000000*(x-S))
        time_system = xmlutil.child(node, 'time_system').text.strip()
        if time_system != 'UTC':
            err = 'Error: supported time_system is "UTC"'
            raise RuntimeError(err)

        return datetime.datetime(Y, m, d, H, M, S, s, pytz.UTC)

    def get_calibration_datetime(self, node):
        tag = 'geometry/intrinseque/sensor/calibration_date'
        D, M, Y = xmlutil.child(node, tag).text.strip().split('-')
        return datetime.date(int(Y), int(M), int(D))

    def get_metadata(self, node):
        version = xmlutil.child(node, 'version').text.strip()
        if version != '1.0':
            err = 'Error: orimatis version {} is not supported' \
                .format(version)
            raise RuntimeError(err)

        image = xmlutil.child(node, 'auxiliarydata/image_name').text.strip()
        node = xmlutil.child(node, 'auxiliarydata/stereopolis')

        date = xmlutil.child_int(node, 'date')
        Y = 2000 + int(date/10000)
        m = int(date/100) % 100
        d = date % 100
        date = datetime.date(Y, m, d)

        metadata = {
            'image': image,
            'project': xmlutil.child(node, 'chantier').text.strip(),
            'date': date.isoformat(),
            'session': xmlutil.child_int(node, 'session'),
            'section': xmlutil.child_int(node, 'section'),
            'numero': xmlutil.child_int(node, 'numero'),
            'position': xmlutil.child(node, 'position').text.strip(),
            'flatfield': xmlutil.child(node, 'flatfield_name').text.strip(),
        }
        return metadata

    def get_or_create_camera_sensor(self, node):
        """
        Create a camera sensor
        """
        node = xmlutil.child(node, 'geometry/intrinseque/sensor')
        pixel_size = xmlutil.child_float(node, 'pixel_size')
        image_size = xmlutil.child_floats(node, 'image_size/[width,height]')
        name = xmlutil.child(node, 'name').text.strip()
        serial = xmlutil.child(node, 'serial_number').text.strip()

        description = 'camera sensor, imported from {}'.format(
                self.file_basename)
        sensor = {
            'name': name,
            'description': description,
            'type': 'camera',
            'brand': '',
            'model': '',
            'serial_number': serial,
            'specifications': {
                'pixel_size': pixel_size,
                'image_size': image_size,
                'flatfield': self.metadata['flatfield'],
            },
        }

        return self.get_or_create('sensor', sensor, [])

    def get_or_create_wo_referential(self, node, sensor):

        node = xmlutil.child(node, 'geometry/extrinseque')
        systeme = xmlutil.child(node, 'systeme').text.strip()
        grid_alti = xmlutil.child(node, 'grid_alti').text.strip()

        srid = 0
        if systeme is 'Lambert93' and grid_alti is 'RAF09':
            srid = 2154

        description = 'world referential ({}/{}), ' \
                      'imported from {}'.format(
                          systeme, grid_alti, self.file_basename)
        referential = {
            'description': description,
            'name': systeme,
            'root': False,
            'sensor': sensor['id'],
            'srid': srid,
        }
        return self.get_or_create('referential', referential, ['sensor'])

    def get_or_create_ri_referential(self, node, sensor):
        description = 'origin: top left corner of top left pixel, ' \
                      '+XY: raster pixel coordinates, ' \
                      '+Z: inverse depth (measured along the optical axis), ' \
                      'imported from {}'.format(self.file_basename)
        referential = {
            'description': description,
            'name': '{}/raw'.format(sensor['name']),
            'root': True,
            'sensor': sensor['id'],
            'srid': 0,
        }
        return self.get_or_create('referential', referential, ['sensor'])

    def get_or_create_ii_referential(self, node, sensor):
        description = 'origin: top left corner of top left pixel, ' \
                      '+XY: raster pixel coordinates, ' \
                      '+Z: inverse depth (measured along the optical axis), ' \
                      'imported from {}'.format(self.file_basename)
        referential = {
            'description': description,
            'name': '{}/ideal'.format(sensor['name']),
            'root': False,
            'sensor': sensor['id'],
            'srid': 0,
        }
        return self.get_or_create('referential', referential, ['sensor'])

    def get_or_create_eu_referential(self, node, sensor):
        description = 'origin: camera position, ' \
                      '+X: right of the camera, ' \
                      '+Y: bottom of the camera, ' \
                      '+Z: optical axis (in front of the camera), ' \
                      'imported from {}'.format(self.file_basename)
        referential = {
            'description': description,
            'name': self.metadata['position'],
            'root': False,
            'sensor': sensor['id'],
            'srid': 0,
        }
        return self.get_or_create('referential', referential, ['sensor'])

    def get_or_create_pinh_transform(self, node, ref_eu, ref_ii):
        node = xmlutil.child(node, 'geometry/intrinseque/sensor')

        transfo = {
            'name': 'projection',
            'parameters': {
                'focal': xmlutil.child_float(node, 'ppa/focale'),
                'ppa': xmlutil.child_floats(node, 'ppa/[c,l]'),
            },
            'tdate': self.calibration_datetime.isoformat(),
            'transfo_type': 'pinhole',
        }
        return self.get_or_create_transfo(transfo, ref_eu, ref_ii)

    def get_or_create_dist_transform(self, node, ref_ii, ref_ri):
        node = xmlutil.child(node, 'geometry/intrinseque/sensor')

        transfo = {
            'name': 'distortion',
            'parameters': {
                'pps': xmlutil.child_floats(node, 'distortion/pps/[c,l]'),
                'coef': xmlutil.child_floats(node, 'distortion/[r3,r5,r7]'),
            },
            'tdate': self.calibration_datetime.isoformat(),
            'transfo_type': 'distortionr357',
        }
        return self.get_or_create_transfo(transfo, ref_ii, ref_ri)

    def get_or_create_pose_transforms(self, node, ref_wo, ref_eu):
        node = xmlutil.child(node, 'geometry/extrinseque')

        p0 = xmlutil.child_floats(node, 'sommet/[easting,northing,altitude]')
        if xmlutil.child_bool(node, 'rotation/Image2Ground'):
            source, target = ref_eu, ref_wo
        else:
            source, target = ref_wo, ref_eu

        transfos = []

        if node.find('rotation/quaternion') is not None:
            quat = xmlutil.child_floats(node, 'rotation/quaternion/[x,y,z,w]')
            transfo = {
                'name': 'pose_quat',
                'parameters': {'quat': quat, 'vec3': p0},
                'transfo_type': 'affine_quat',
                'validity_start': self.acquisition_datetime.isoformat(),
                'validity_end': self.acquisition_datetime.isoformat(),
            }
            transfo = self.get_or_create_transfo(transfo, source, target)
            transfos.append(transfo)

        if node.find('rotation/mat3d') is not None:
            l1 = xmlutil.child_floats(node, 'rotation/mat3d/l1/pt3d/[x,y,z]')
            l2 = xmlutil.child_floats(node, 'rotation/mat3d/l2/pt3d/[x,y,z]')
            l3 = xmlutil.child_floats(node, 'rotation/mat3d/l3/pt3d/[x,y,z]')

            matrix = []
            matrix.extend(l1)
            matrix.append(p0[0])
            matrix.extend(l2)
            matrix.append(p0[1])
            matrix.extend(l3)
            matrix.append(p0[2])

            transfo = {
                'name': 'pose_mat',
                'parameters': {'mat4x3': matrix},
                'transfo_type': 'affine_mat',
                'validity_start': self.acquisition_datetime.isoformat(),
                'validity_end': self.acquisition_datetime.isoformat(),
            }
            transfo = self.get_or_create_transfo(transfo, source, target)
            transfos.append(transfo)

        return transfos

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
        return self.get_or_create('transfotree', transfotree, ['transfos'])

    def get_or_create(self, typ, obj, keys):
        if self.api:
            return self.api.get_or_create_object(typ, obj, keys, self.log)
        else:
            strobj = json.dumps(obj, indent=self.indent)
            self.log.info('[{}:{}] {}'.format(typ, self.staging_id, strobj))
            if 'id' not in obj:
                obj['id'] = self.staging_id
                self.staging_id = self.staging_id + 1
            return obj

    def get_or_create_transfo(self, obj, source, target):
        transfo_type = {
            'name': obj['transfo_type'],
            'func_signature': obj['parameters'].keys(),
        }
        transfo_type = self.get_or_create('transfos/type', transfo_type, [])
        obj['transfo_type'] = transfo_type['id']
        obj['source'] = source['id']
        obj['target'] = target['id']
        obj['description'] = '"{}" transformation, imported from "{}"'.format(
                            transfo_type['name'], self.file_basename)
        transfo = self.transfo.copy()
        transfo.update(obj)
        return self.get_or_create('transfo', transfo, ['source', 'target'])
