import os
import logging
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
        self.config = None
        self.transfotree = 'orimatis'

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
            '--no-proxy', action='store_true',
            help='disable all proxy settings')
        parser.add_argument(
            '--sensor-id', '-s',
            type=int,
            help='the camera sensor id (optional)')
        parser.add_argument(
            '--sensor-name', '-n',
            help='the camera sensor name (optional)')
        parser.add_argument(
            '--config', '-c',
            help='the configuration name (optional)')
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
            help='the orimatis file')
        return parser

    def take_action(self, parsed_args):
        """
        Create or update a camera sensor.
        """

        self.sensor_id = parsed_args.sensor_id
        self.sensor_name = parsed_args.sensor_name
        self.filename = parsed_args.filename
        self.basename = os.path.basename(self.filename)
        self.owner = parsed_args.owner
        self.tdate = parsed_args.calibration_date
        self.validity_start = parsed_args.validity_start
        self.validity_end = parsed_args.validity_end
        self.indent = parsed_args.indent
        self.config = parsed_args.config
        self.api = api.Api(parsed_args.api_url, parsed_args.api_key,
                           parsed_args.no_proxy, self.log, parsed_args.indent)

        root = xmlutil.root(self.filename, 'orientation')
        xmlutil.child_check(root, 'version', '1.0')

        sensor_node = root.find('geometry/intrinseque/sensor')
        spherique_node = root.find('geometry/intrinseque/spherique')
        intrinsic = sensor_node or spherique_node
        if not intrinsic:
            err = 'Error: no supported "intrinseque" node found' \
                '("sensor" or "spherique")'
            raise RuntimeError(err)

        self.acquisition_datetime = self.get_acquisition_datetime(root)
        self.calibration_datetime = self.get_calibration_datetime(root)

        sensor = self.get_or_create_camera_sensor(intrinsic)

        # get or create world, euclidean and rawImage referentials
        ref_wo = self.get_or_create_wo_referential(root, sensor)
        ref_eu = self.get_or_create_eu_referential(root, sensor)
        ref_ri = self.get_or_create_ri_referential(root, sensor)

        # get or create pose transforms
        pose = self.get_or_create_pose_transforms(root, ref_wo, ref_eu)

        if sensor_node:
            ref_ii = self.get_or_create_ii_referential(root, sensor)
            pinh = self.get_or_create_pinh_transform(root, ref_eu, ref_ii)
            dist = self.get_or_create_dist_transform(root, ref_ii, ref_ri)
            transfos = [pose[0], pinh, dist]

        else:
            sphe = self.get_or_create_sphe_transform(root, ref_eu, ref_ri)
            transfos = [pose[0], sphe]

        transfotree = self.get_or_create_transfotree(root, transfos)

        project = self.get_or_create_project(root)
        platform = self.get_or_create_platform(root)
        session = self.get_or_create_session(root, project, platform)
        self.get_or_create_datasource(root, session, ref_ri)
        self.get_or_create_config(root, platform, [transfotree])

        self.log.info('Success!')

    @staticmethod
    def get_acquisition_datetime(node):

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

        return datetime.datetime(Y, m, d, H, M, S, s, pytz.UTC).isoformat()

    @staticmethod
    def get_calibration_datetime(node):
        date = node.find('geometry/intrinseque/sensor/calibration_date')
        if not date:
            return None
        D, M, Y = date.text.strip().split('-')
        return datetime.date(int(Y), int(M), int(D)).isoformat()

    @staticmethod
    def get_flatfield(node):
        flatfield = node.findtext('auxiliarydata/stereopolis/flatfield_name')
        return flatfield.strip() if flatfield else None

    @staticmethod
    def get_date(node):
        date = xmlutil.child_int(node, 'auxiliarydata/stereopolis/date')
        Y = 2000 + int(date/10000)
        m = int(date/100) % 100
        d = date % 100
        return datetime.date(Y, m, d).isoformat()

    @staticmethod
    def get_project(node):
        tag = 'auxiliarydata/stereopolis/chantier'
        return xmlutil.child(node, tag).text.strip()

    @staticmethod
    def get_position(node):
        tag = 'auxiliarydata/stereopolis/position'
        return xmlutil.child(node, tag).text.strip()

    @staticmethod
    def get_session(node):
        return xmlutil.child_int(node, 'auxiliarydata/stereopolis/session')

    @staticmethod
    def get_section(node):
        return xmlutil.child_int(node, 'auxiliarydata/stereopolis/section')

    @staticmethod
    def get_numero(node):
        return xmlutil.child_int(node, 'auxiliarydata/stereopolis/numero')

    def get_or_create_camera_sensor(self, node):
        name = None
        pixel_size = None
        serial = ''

        if node.tag == 'sensor':
            name = xmlutil.child(node, 'name').text.strip()
            pixel_size = xmlutil.child_float(node, 'pixel_size')
            serial = xmlutil.child(node, 'serial_number').text.strip()

        elif node.tag == 'spherique':
            name = 'spherical'

        image_size = xmlutil.child_floats(node, 'image_size/[width,height]')
        specs = {
            'image_size': image_size,
            'pixel_size': pixel_size,
            'flatfield': self.get_flatfield(node),
        }
        return self.api.get_or_create_sensor(
            name=self.sensor_name or name,
            sensor_type='camera',
            sensor_id=self.sensor_id,
            description='imported from "{}"'.format(self.basename),
            serial=serial,
            specs=specs,
        )

    def get_or_create_wo_referential(self, node, sensor):

        node = xmlutil.child(node, 'geometry/extrinseque')
        systeme = xmlutil.child(node, 'systeme').text.strip()
        grid_alti = xmlutil.child(node, 'grid_alti').text.strip()

        srid = 0
        if systeme is 'Lambert93' and grid_alti is 'RAF09':
            srid = 2154

        description = 'world referential, imported from "{}"'.format(
            self.basename)
        return self.api.get_or_create_referential(
            name='{}/{}'.format(systeme, grid_alti),
            sensor=sensor,
            description=description,
            srid=srid
        )

    def get_or_create_ri_referential(self, node, sensor):
        description = 'origin: top left corner of top left pixel, ' \
                      '+XY: raster pixel coordinates, ' \
                      '+Z: inverse depth (measured along the optical axis), ' \
                      'imported from "{}"'.format(self.basename)
        return self.api.get_or_create_referential(
            name='{}/raw'.format(sensor['name']),
            sensor=sensor,
            description=description,
            root=True,
        )

    def get_or_create_ii_referential(self, node, sensor):
        description = 'origin: top left corner of top left pixel, ' \
                      '+XY: raster pixel coordinates, ' \
                      '+Z: inverse depth (measured along the optical axis), ' \
                      'imported from "{}"'.format(self.basename)
        return self.api.get_or_create_referential(
            name='{}/ideal'.format(sensor['name']),
            sensor=sensor,
            description=description,
        )

    def get_or_create_eu_referential(self, node, sensor):
        description = 'origin: camera position, ' \
                      '+X: right of the camera, ' \
                      '+Y: bottom of the camera, ' \
                      '+Z: optical axis (in front of the camera), ' \
                      'imported from "{}"'.format(self.basename)
        return self.api.get_or_create_referential(
            name=self.get_position(node),
            sensor=sensor,
            description=description,
        )

    def get_or_create_pinh_transform(self, node, source, target):
        node = xmlutil.child(node, 'geometry/intrinseque/sensor')
        return self.api.get_or_create_transfo(
            'projection', 'pinhole', source, target,
            description='imported from "{}"'.format(self.basename),
            parameters={
                'focal': xmlutil.child_float(node, 'ppa/focale'),
                'ppa': xmlutil.child_floats(node, 'ppa/[c,l]'),
            },
            tdate=self.calibration_datetime,
            validity_start=self.validity_start,
            validity_end=self.validity_end,
        )

    def get_or_create_sphe_transform(self, node, source, target):
        node = xmlutil.child(node, 'geometry/intrinseque/spherique')
        return self.api.get_or_create_transfo(
            'projection', 'spherical', source, target,
            description='imported from "{}"'.format(self.basename),
            parameters={
                'ppa': xmlutil.child_floats(node, 'ppa/[c,l]'),
                'lambda': xmlutil.child_floats(node, 'frame/lambda_[min,max]'),
                'phi': xmlutil.child_floats(node, 'frame/phi_[min,max]'),
            },
            validity_start=self.validity_start,
            validity_end=self.validity_end,
        )

    def get_or_create_dist_transform(self, node, source, target):
        node = xmlutil.child(node, 'geometry/intrinseque/sensor')
        return self.api.get_or_create_transfo(
            'distortion', 'poly_radial_7', source, target,
            description='imported from "{}"'.format(self.basename),
            parameters={
                'C': xmlutil.child_floats(node, 'distortion/pps/[c,l]'),
                'R': xmlutil.child_floats(node, 'distortion/[r3,r5,r7]'),
            },
            tdate=self.calibration_datetime,
            validity_start=self.validity_start,
            validity_end=self.validity_end,
        )

    def get_or_create_pose_transforms(self, node, source, target):
        node = xmlutil.child(node, 'geometry/extrinseque')
        p = xmlutil.child_floats(node, 'sommet/[easting,northing,altitude]')
        reverse = xmlutil.child_bool(node, 'rotation/Image2Ground')
        transfos = []

        if node.find('rotation/quaternion') is not None:
            quat = xmlutil.child_floats(node, 'rotation/quaternion/[x,y,z,w]')
            transfo = self.api.get_or_create_transfo(
                'pose_quat', 'affine_quat', source, target,
                description='imported from "{}"'.format(self.basename),
                parameters={'quat': quat, 'vec3': p},
                tdate=self.tdate,
                validity_start=self.acquisition_datetime,
                validity_end=self.acquisition_datetime,
                reverse=reverse,
            )
            transfos.append(transfo)

        if node.find('rotation/mat3d') is not None:
            l1 = xmlutil.child_floats(node, 'rotation/mat3d/l1/pt3d/[x,y,z]')
            l2 = xmlutil.child_floats(node, 'rotation/mat3d/l2/pt3d/[x,y,z]')
            l3 = xmlutil.child_floats(node, 'rotation/mat3d/l3/pt3d/[x,y,z]')

            matrix = []
            matrix.extend(l1)
            matrix.append(p[0])
            matrix.extend(l2)
            matrix.append(p[1])
            matrix.extend(l3)
            matrix.append(p[2])

            transfo = self.api.get_or_create_transfo(
                'pose_mat', 'affine_mat', source, target,
                description='imported from "{}"'.format(self.basename),
                parameters={'mat4x3': matrix},
                tdate=self.tdate,
                validity_start=self.acquisition_datetime,
                validity_end=self.acquisition_datetime,
                reverse=reverse,
            )
            transfos.append(transfo)

        return transfos

    def get_or_create_transfotree(self, node, transfos):
        return self.api.get_or_create_transfotree(
            name=self.transfotree,
            transfos=transfos,
            owner=self.owner,
        )

    def get_or_create_project(self, node):
        return self.api.get_or_create_project(name=self.get_project(node))

    def get_or_create_platform(self, node):
        return self.api.get_or_create_platform(
            name='Stereopolis II',
            description='IGN Stereopolis',
        )

    def get_or_create_session(self, node, project, platform):
        name = '{}/{}/{}'.format(
            self.get_date(node),
            self.get_section(node),
            self.get_session(node))
        return self.api.get_or_create_session(name, project, platform)

    def get_or_create_datasource(self, node, session, referential):
        return self.api.get_or_create_datasource(
            session=session,
            referential=referential,
            uri=xmlutil.child(node, 'auxiliarydata/image_name').text,
        )

    def get_or_create_config(self, node, platform, transfotrees):
        return self.api.get_or_create_config(
            name=self.config,
            platform=platform,
            transfotrees=transfotrees,
            owner=self.owner,
        )
