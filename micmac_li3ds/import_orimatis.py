import os
import logging
import datetime
import pytz

from cliff.command import Command

from . import api as Api
from . import xmlutil


class ImportOrimatis(Command):
    """ import an Ori-Matis file
    """

    log = logging.getLogger(__name__)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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
            '--sensor-id', '-i',
            type=int,
            help='the camera sensor id (optional)')
        parser.add_argument(
            '--sensor', '-s',
            help='the camera sensor name (optional)')
        parser.add_argument(
            '--transfotree',
            help='the transfotree name (optional)')
        parser.add_argument(
            '--transfo', '-t',
            help='the transfo basename (optional)')
        parser.add_argument(
            '--config', '-c',
            help='the configuration name (optional)')
        parser.add_argument(
            '--owner', '-o',
            help='the data owner (optional, default is unix username)')
        parser.add_argument(
            '--calibration-datetime', '-d',
            help='the calibration date (optional, default is the current '
                 'local date and time')
        parser.add_argument(
            '--acquisition-datetime', '-a',
            help='the acquisition datetime (optional)')
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
            'filenames', nargs='+',
            help='the list of orimatis filenames')
        return parser

    def take_action(self, parsed_args):
        """
        Create or update a camera sensor.
        """
        self.api = Api.Api(parsed_args.api_url, parsed_args.api_key,
                           parsed_args.no_proxy, self.log, parsed_args.indent)

        args = {
            'sensor': {
                '*': {
                    'type': 'camera',
                    'name': parsed_args.sensor,
                    'id': parsed_args.sensor_id,
                },
            },
            'transfo': {
                '*#extrinseque#*': {
                    'name': parsed_args.transfo,
                    'validity_start': parsed_args.acquisition_datetime,
                    'validity_end': parsed_args.acquisition_datetime,
                },
                '*#intrinseque#*': {
                    'name': parsed_args.transfo,
                    'tdate': parsed_args.calibration_datetime,
                    'validity_start': parsed_args.validity_start,
                    'validity_end': parsed_args.validity_end,
                },
            },
            'transfotree': {
                '*': {
                    'name': parsed_args.transfotree,
                    'owner': parsed_args.owner,
                },
            },
            'config': {
                '*': {
                    'name': parsed_args.config,
                    'owner': parsed_args.owner,
                },
            },
            'referential': {'*': {}},
            'transfos/type': {'*': {}},
            'platforms/{id}/config': {'*': {}},
            'platform': {'*': {}},
            'project': {'*': {}},
            'session': {'*': {}},
            'datasource': {'*': {}},
        }
        for filename in parsed_args.filenames:
            self.log.info('Importing {}'.format(filename))
            self.get_or_create(self.api, filename, args)
            self.log.info('Success!\n')

    @staticmethod
    def get_or_create(api, filename, args):
        root = xmlutil.root(filename, 'orientation')
        xmlutil.child_check(root, 'version', '1.0')

        # copy and set defaults to the object templates
        args = args.copy()
        basename = os.path.basename(filename)
        description = 'Imported from "{}"'.format(basename)
        calibration_datetime = ImportOrimatis.get_calibration_datetime(root)
        acquisition_datetime = ImportOrimatis.get_acquisition_datetime(root)
        for type_ in args:
            arg = args[type_].copy()
            for key in arg:
                arg[key] = {k: v for k, v in arg[key].items() if v}
                if type_ in ['transfo', 'transfos/type',
                             'sensor', 'referential']:
                    arg[key].setdefault('description', description)
                if type_ not in ['datasource']:
                    arg[key].setdefault('name', basename)
                if key == '*#extrinseque#*':
                    arg[key].setdefault('validity_start', acquisition_datetime)
                    arg[key].setdefault('validity_end', acquisition_datetime)
                elif key == '*#intrinseque#*':
                    arg[key].setdefault('tdate', calibration_datetime)
            args[type_] = arg

        # get or create sensor
        sensor_node = root.find('geometry/intrinseque/sensor')
        spherique_node = root.find('geometry/intrinseque/spherique')
        node = sensor_node or spherique_node
        if not node:
            err = 'Error: no supported "intrinseque" node found' \
                '("sensor" or "spherique")'
            raise RuntimeError(err)

        sensor = Sensor(args, root, node).get_or_create(api)

        # get or create world, euclidean and rawImage referentials
        ref_w = Referential.world(sensor, args, root).get_or_create(api)
        ref_e = Referential.eucli(sensor, args, root).get_or_create(api)
        ref_i = Referential.image(sensor, args).get_or_create(api)

        # get or create matr, quat, pinh, dist or sphe transforms
        matr = Transfo.matr(ref_w, ref_e, args, root).get_or_create(api)
        quat = Transfo.quat(ref_w, ref_e, args, root).get_or_create(api)

        if sensor_node:
            ref_u = Referential.undis(sensor, args).get_or_create(api)
            pinh = Transfo.pinh(ref_e, ref_u, args, root).get_or_create(api)
            dist = Transfo.dist(ref_u, ref_i, args, root).get_or_create(api)
            transfos = [quat or matr, pinh, dist]

        else:
            sphe = Transfo.sphe(ref_e, ref_i, args, root).get_or_create(api)
            transfos = [quat or matr, sphe]

        transfotree = Transfotree(transfos, args).get_or_create(api)
        project = Project(args, root).get_or_create(api)
        platform = Platform(args).get_or_create(api)
        session = Session(project, platform, args, root).get_or_create(api)
        Datasource(session, ref_i, args, root).get_or_create(api)
        Config(platform, [transfotree], args).get_or_create(api)

    @staticmethod
    def get_acquisition_datetime(root):

        node = xmlutil.child(root, 'auxiliarydata/image_date')
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
    def get_calibration_datetime(root):
        date = root.find('geometry/intrinseque/sensor/calibration_date')
        if date is None:
            return None
        try:
            date = datetime.datetime.strptime(date.text.strip(), '%d-%m-%Y')
        except:
            date = datetime.datetime.strptime(date.text.strip(), '%m-%Y')
        return date.isoformat()

    @staticmethod
    def get_flatfield(root):
        flatfield = root.findtext('auxiliarydata/stereopolis/flatfield_name')
        return flatfield.strip() if flatfield else None

    @staticmethod
    def get_date(root):
        date = xmlutil.child(root, 'auxiliarydata/stereopolis/date')
        return datetime.datetime.strptime(date.text.strip(), '%y%m%d')

    @staticmethod
    def get_project(root):
        tag = 'auxiliarydata/stereopolis/chantier'
        return xmlutil.child(root, tag).text.strip()

    @staticmethod
    def get_position(root):
        tag = 'auxiliarydata/stereopolis/position'
        return xmlutil.child(root, tag).text.strip()

    @staticmethod
    def get_session(root):
        return xmlutil.child_int(root, 'auxiliarydata/stereopolis/session')

    @staticmethod
    def get_section(root):
        return xmlutil.child_int(root, 'auxiliarydata/stereopolis/section')

    @staticmethod
    def get_numero(root):
        return xmlutil.child_int(root, 'auxiliarydata/stereopolis/numero')


class Sensor(Api.Sensor):
    def __init__(self, args, root, node):
        sensor = args['sensor']['*']
        pixel_size = None
        serial_number = None

        if node.tag == 'sensor':
            sensor.setdefault('name', xmlutil.child(node, 'name').text.strip())
            pixel_size = xmlutil.child_float(node, 'pixel_size')
            serial_number = xmlutil.child(node, 'serial_number').text.strip()

        image_size = xmlutil.child_floats(node, 'image_size/[width,height]')
        super().__init__(
            sensor,
            type='camera',
            serial_number=serial_number,
            specifications={
                'image_size': image_size,
                'pixel_size': pixel_size,
                'flatfield': ImportOrimatis.get_flatfield(root),
            },
        )


class Referential:
    def world(sensor, args, root):
        referential = args['referential']['*']
        node = xmlutil.child(root, 'geometry/extrinseque')
        systeme = xmlutil.child(node, 'systeme').text.strip()
        grid_alti = xmlutil.child(node, 'grid_alti').text.strip()

        srid = 0
        if systeme is 'Lambert93' and grid_alti is 'RAF09':
            srid = 2154

        return Api.Referential(
            sensor,
            referential,
            name='{}/{}'.format(systeme, grid_alti),
            srid=srid
        )

    def image(sensor, args):
        referential = args['referential']['*']
        description = 'origin: top left corner of top left pixel, ' \
                      '+XY: raster pixel coordinates, ' \
                      '+Z: inverse depth (measured along the optical axis). ' \
                      '{description}'
        return Api.Referential(
            sensor, referential,
            name='image',
            description=description.format(**referential),
            root=True,
        )

    def undis(sensor, args):
        referential = args['referential']['*']
        description = 'origin: top left corner of top left pixel, ' \
                      '+XY: raster pixel coordinates, ' \
                      '+Z: inverse depth (measured along the optical axis). ' \
                      '{description}'
        return Api.Referential(
            sensor, referential,
            name='undistorted',
            description=description.format(**referential),
        )

    def eucli(sensor, args, root):
        referential = args['referential']['*']
        description = 'origin: camera position, ' \
                      '+X: right of the camera, ' \
                      '+Y: bottom of the camera, ' \
                      '+Z: optical axis (in front of the camera). ' \
                      '{description}'
        return Api.Referential(
            sensor, referential,
            name=ImportOrimatis.get_position(root),
            description=description.format(**referential),
        )


class Transfo:
    def pinh(source, target, args, root):
        transfo = args['transfo']['*#intrinseque#*']
        node = xmlutil.child(root, 'geometry/intrinseque/sensor')
        return Api.Transfo(
            source, target, transfo,
            name='{name}#intrinseque#projection'.format(**transfo),
            type_name='projective_pinhole',
            parameters={
                'focal': xmlutil.child_float(node, 'ppa/focale'),
                'ppa': xmlutil.child_floats(node, 'ppa/[c,l]'),
            },
        )

    def sphe(source, target, args, root):
        transfo = args['transfo']['*#intrinseque#*']
        node = xmlutil.child(root, 'geometry/intrinseque/spherique')
        return Api.Transfo(
            source, target, transfo,
            name='{name}#intrinseque#projection'.format(**transfo),
            type_name='cartesian_to_spherical',
            parameters={
                'ppa': xmlutil.child_floats(node, 'ppa/[c,l]'),
                'lambda': xmlutil.child_floats(node, 'frame/lambda_[min,max]'),
                'phi': xmlutil.child_floats(node, 'frame/phi_[min,max]'),
            },
        )

    def dist(source, target, args, root):
        transfo = args['transfo']['*#intrinseque#*']
        node = xmlutil.child(root, 'geometry/intrinseque/sensor')
        return Api.Transfo(
            source, target, transfo,
            name='{name}#intrinseque#distortion'.format(**transfo),
            type_name='poly_radial_7',
            parameters={
                'C': xmlutil.child_floats(node, 'distortion/pps/[c,l]'),
                'R': xmlutil.child_floats(node, 'distortion/[r3,r5,r7]'),
            },
        )

    def quat(source, target, args, root):
        transfo = args['transfo']['*#extrinseque#*']
        node = xmlutil.child(root, 'geometry/extrinseque')
        p = xmlutil.child_floats(node, 'sommet/[easting,northing,altitude]')
        reverse = xmlutil.child_bool(node, 'rotation/Image2Ground')
        if node.find('rotation/quaternion') is None:
            return Api.NoObj

        quat = xmlutil.child_floats(node, 'rotation/quaternion/[x,y,z,w]')
        return Api.Transfo(
            source, target, transfo,
            name='{name}#extrinseque#quaternion'.format(**transfo),
            type_name='affine_quat',
            parameters={'quat': quat, 'vec3': p},
            reverse=reverse,
        )

    def matr(source, target, args, root):
        transfo = args['transfo']['*#extrinseque#*']
        node = xmlutil.child(root, 'geometry/extrinseque')
        p = xmlutil.child_floats(node, 'sommet/[easting,northing,altitude]')
        reverse = xmlutil.child_bool(node, 'rotation/Image2Ground')
        if node.find('rotation/mat3d') is None:
            return Api.NoObj

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

        return Api.Transfo(
            source, target, transfo,
            name='{name}#extrinseque#mat3d'.format(**transfo),
            type_name='affine_mat4x3',
            parameters={'mat4x3': matrix},
            reverse=reverse,
        )


class Transfotree(Api.Transfotree):
    def __init__(self, transfos, args):
        super().__init__(transfos, args['transfotree']['*'])


class Project(Api.Project):
    def __init__(self, args, root):
        name = ImportOrimatis.get_project(root)
        super().__init__(args['project']['*'], name=name)


class Platform(Api.Platform):
    def __init__(self, args):
        super().__init__(args['platform']['*'], name='Stereopolis II')


class Session(Api.Session):
    def __init__(self, project, platform, args, root):
        super().__init__(
            project, platform, args['session']['*'],
            name='{}/{}/{}'.format(
                ImportOrimatis.get_date(root),
                ImportOrimatis.get_section(root),
                ImportOrimatis.get_session(root)
            )
        )


class Datasource(Api.Datasource):
    def __init__(self, session, referential, args, root):
        super().__init__(
            session, referential, args['datasource']['*'],
            uri=xmlutil.child(root, 'auxiliarydata/image_name').text,
        )


class Config(Api.Config):
    def __init__(self, platform, transfotrees, args):
        super().__init__(platform, transfotrees, args['config']['*'])
