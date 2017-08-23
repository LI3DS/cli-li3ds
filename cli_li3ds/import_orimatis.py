import os
import logging
import datetime
import pytz
import pathlib

from cliff.command import Command

from . import api
from . import xmlutil


class ImportOrimatis(Command):
    """ import Ori-Matis files
    """

    log = logging.getLogger(__name__)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_parser(self, prog_name):
        self.log.debug(prog_name)
        parser = super().get_parser(prog_name)
        api.add_arguments(parser)
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
            '--calibration', '-d',
            help='the calibration datetime (optional')
        parser.add_argument(
            '--acquisition', '-a',
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
            '--base-image-dir', '-b',
            help='base image directory in image URIs (optional, '
                 'default is no base image directory)')
        parser.add_argument(
            '--orimatis-dir', '-f',
            help='base directory to search for orimatis files (optional, '
                 'default is ".")')
        parser.add_argument(
            '--image-file-ext', '-e',
            help='file extension to use in image URIs (optional, '
                 'default is none, e.g. ".tif")')
        parser.add_argument(
            'filenames', nargs='+',
            help='the orimatis file names, may be Unix style patterns '
                 '(e.g. Paris-100-*.ori.xml)')
        return parser

    def take_action(self, parsed_args):
        """
        Create or update a camera sensor.
        """
        server = api.ApiServer(parsed_args, self.log)
        objs = api.ApiObjs(server)

        args = {
            'sensor': {
                'name': parsed_args.sensor,
                'id': parsed_args.sensor_id,
            },
            'transfo_ext': {
                'name': parsed_args.sensor,
                'validity_start': parsed_args.acquisition,
                'validity_end': parsed_args.acquisition,
            },
            'transfo_int': {
                'name': parsed_args.transfo,
                'tdate': parsed_args.calibration,
                'validity_start': parsed_args.validity_start,
                'validity_end': parsed_args.validity_end,
            },
            'transfotree': {
                'name': parsed_args.transfotree,
                'owner': parsed_args.owner,
            },
            'config': {
                'name': parsed_args.config,
                'owner': parsed_args.owner,
            },
        }

        if parsed_args.base_image_dir:
            base_image_path = pathlib.Path(parsed_args.base_image_dir)
        else:
            base_image_path = None

        if parsed_args.orimatis_dir:
            orimatis_dir_path = pathlib.Path(parsed_args.orimatis_dir)
        else:
            orimatis_dir_path = pathlib.Path('.')

        for filename in parsed_args.filenames:
            for orimatis_abs_path in orimatis_dir_path.rglob(filename):
                orimatis_rel_path = orimatis_abs_path.relative_to(orimatis_dir_path)
                self.log.info('Importing {}'.format(orimatis_abs_path))
                self.handle_orimatis(
                    objs, args, orimatis_abs_path, orimatis_rel_path, base_image_path,
                    parsed_args.image_file_ext)

        objs.get_or_create()
        self.log.info('Success!\n')

    @staticmethod
    def handle_orimatis(objs, args, orimatis_abs_path, orimatis_rel_path,
                        base_image_path, image_file_ext):

        # open XML file
        root = xmlutil.root(str(orimatis_abs_path), 'orientation')
        xmlutil.child_check(root, 'version', '1.0')

        sensor_node = root.find('geometry/intrinseque/sensor')
        spherique_node = root.find('geometry/intrinseque/spherique')
        node = sensor_node or spherique_node
        if not node:
            err = 'Error: no supported "intrinseque" node found' \
                '("sensor" or "spherique")'
            raise RuntimeError(err)

        # retrieve metadata
        stereopolis = xmlutil.child(root, 'auxiliarydata/stereopolis')
        extrinseque = xmlutil.child(root, 'geometry/extrinseque')
        calibration = get_calibration_datetime(root)
        acquisition = get_acquisition_datetime(root)
        date = xmlutil.finddate(stereopolis, 'date', ['%y%m%d'])
        metadata = {
            'basename': orimatis_abs_path.name,
            'calibration':     calibration,
            'acquisition':     acquisition,
            'date':            date,
            'calibration_iso': api.isoformat(calibration),
            'acquisition_iso': api.isoformat(acquisition),
            'date_iso':        api.isoformat(date),
            'numero':    xmlutil.child_int(stereopolis, 'numero'),
            'section':   xmlutil.child_int(stereopolis, 'section'),
            'session':   xmlutil.child_int(stereopolis, 'session'),
            'flatfield': xmlutil.findtext(stereopolis, 'flatfield_name'),
            'chantier':  xmlutil.findtext(stereopolis, 'chantier'),
            'position':  xmlutil.findtext(stereopolis, 'position'),
            'systeme':   xmlutil.findtext(extrinseque, 'systeme'),
            'grid_alti': xmlutil.findtext(extrinseque, 'grid_alti'),
            'image':     xmlutil.findtext(root, 'auxiliarydata/image_name'),
            'sensor':    xmlutil.findtext(node, 'name'),
            'serial':    xmlutil.findtext(node, 'serial_number'),
            'image_size': xmlutil.child_floats(
                node, 'image_size/[width,height]'),
        }

        # generate template objects
        sensor = {
            'type': 'camera',
            'name': '{sensor}',
            'serial_number': '{serial}',
        }
        transfo_ext = {
            'name': '{sensor}',
        }
        transfo_int = {'tdate': '{calibration_iso}'}
        referential = {'name': '{position}'}
        platform = {'name': 'Stereopolis II'}
        project = {'name': '{chantier}'}
        session = {'name': '{date:%y%m%d}/{session}/{section}'}
        datasource = {
            'image': '{image}',
            'capture_start': '{acquisition_iso}',
            'capture_end': '{acquisition_iso}',
        }
        transfotree = {}
        config = {}

        api.update_obj(args, metadata, sensor, 'sensor')
        api.update_obj(args, metadata, referential, 'referential')
        api.update_obj(args, metadata, transfo_ext, 'transfo_ext')
        api.update_obj(args, metadata, transfo_int, 'transfo_int')
        api.update_obj(args, metadata, transfotree, 'transfotree')
        api.update_obj(args, metadata, project, 'project')
        api.update_obj(args, metadata, platform, 'platform')
        api.update_obj(args, metadata, session, 'session')
        api.update_obj(args, metadata, datasource, 'datasource')
        api.update_obj(args, metadata, config, 'config')

        # get or create sensor
        sensor = sensor_camera(sensor, node, metadata)

        # get or create world, euclidean and rawImage referentials
        ref_w = referential_world(sensor, referential, metadata)
        ref_e = referential_eucli(sensor, referential)
        ref_i = referential_image(sensor, referential)

        # get or create matr transform
        matr = transfo_matr(ref_w, ref_e, transfo_ext, acquisition, root)
        if matr:
            o = objs.lookup(matr)
            if o:
                # we already have that matr transform so just update its
                # parameters list
                o.obj['parameters'].append(matr.obj['parameters'][0])
                matr = o

        # get or create quat transform
        quat = transfo_quat(ref_w, ref_e, transfo_ext, acquisition, root)
        if quat:
            o = objs.lookup(quat)
            if o:
                # we already have that quat transform so just update its
                # parameters list
                o.obj['parameters'].append(quat.obj['parameters'][0])
                quat = o

        # get or create pinh, dist or sphe transforms
        if sensor_node:
            ref_u = referential_undis(sensor, referential)
            pinh = transfo_pinh(ref_e, ref_u, transfo_int, root)
            dist = transfo_dist(ref_u, ref_i, transfo_int, root)
            transfos = [quat or matr, pinh, dist]
        else:
            sphe = transfo_sphe(ref_e, ref_i, transfo_int, root)
            transfos = [quat or matr, sphe]

        transfotree = api.Transfotree(transfos, sensor, transfotree)
        project = api.Project(project)
        platform = api.Platform(platform)
        session = api.Session(project, platform, session)
        datasource = datasource_image(
            session, ref_i, datasource, metadata,
            base_image_path, orimatis_rel_path.parent, image_file_ext)
        config = api.Config(platform, [transfotree], config)

        objs.add(datasource, config)


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
    xmlutil.child_check(node, 'time_system', 'UTC')
    return datetime.datetime(Y, m, d, H, M, S, s, pytz.UTC)


def get_calibration_datetime(root):
    tag = 'geometry/intrinseque/sensor/calibration_date'
    date = xmlutil.finddate(root, tag, ['%d-%m-%Y', '%m-%Y'])
    return date.replace(tzinfo=pytz.UTC) if date else None


def datasource_image(session, referential, datasource,
                     metadata, base_image_dir, subdir, image_file_ext):

    image_path = subdir / pathlib.Path(datasource.pop('image'))
    if base_image_dir:
        image_path = base_image_dir / image_path
    if image_file_ext:
        image_path = image_path.with_suffix(image_file_ext)
    image_path = os.path.normpath(str(image_path))
    uri = 'file:{}'.format(image_path)

    image_size = metadata.get('image_size')
    return api.Datasource(
            session, referential, datasource, type='image', uri=uri,
            bounds=[0, image_size[0], 0, 0, image_size[1], 0])


def sensor_camera(sensor, node, metadata):
    pixel_size = None
    if node.tag == 'sensor':
        pixel_size = xmlutil.child_float(node, 'pixel_size')

    image_size = metadata.get('image_size')
    return api.Sensor(
        sensor,
        specifications={
            'image_size': image_size,
            'pixel_size': pixel_size,
            'flatfield': metadata.get('flatfield'),
        },
    )


def referential_world(sensor, referential, metadata):
    srid = 0
    systeme = metadata.get('systeme')
    grid_alti = metadata.get('grid_alti')
    if systeme is 'Lambert93' and grid_alti is 'RAF09':
        srid = 2154

    return api.Referential(
        sensor, referential,
        name='{systeme}/{grid_alti}'.format(**metadata),
        srid=srid
    )


def referential_image(sensor, referential):
    description = 'origin: top left corner of top left pixel, ' \
                  '+XY: raster pixel coordinates, ' \
                  '+Z: inverse depth (measured along the optical axis). ' \
                  '{description}'
    return api.Referential(
        sensor, referential,
        name='image',
        description=description.format(**referential)
    )


def referential_undis(sensor, referential):
    description = 'origin: top left corner of top left pixel, ' \
                  '+XY: raster pixel coordinates, ' \
                  '+Z: inverse depth (measured along the optical axis). ' \
                  '{description}'
    return api.Referential(
        sensor, referential,
        name='undistorted',
        description=description.format(**referential),
    )


def referential_eucli(sensor, referential):
    description = 'origin: camera position, ' \
                  '+X: right of the camera, ' \
                  '+Y: bottom of the camera, ' \
                  '+Z: optical axis (in front of the camera). ' \
                  '{description}'
    return api.Referential(
        sensor, referential,
        description=description.format(**referential),
    )


def transfo_pinh(source, target, transfo, root):
    node = xmlutil.child(root, 'geometry/intrinseque/sensor')
    return api.Transfo(
        source, target, transfo,
        name='{name}#projection'.format(**transfo),
        type_name='projective_pinhole',
        func_signature=['focal', 'ppa'],
        parameters=[{
            'focal': xmlutil.child_float(node, 'ppa/focale'),
            'ppa': xmlutil.child_floats(node, 'ppa/[c,l]'),
        }],
    )


def transfo_sphe(source, target, transfo, root):
    node = xmlutil.child(root, 'geometry/intrinseque/spherique')
    return api.Transfo(
        source, target, transfo,
        name='{name}#projection'.format(**transfo),
        type_name='cartesian_to_spherical',
        func_signature=['ppa', 'lambda', 'phi'],
        parameters=[{
            'ppa': xmlutil.child_floats(node, 'ppa/[c,l]'),
            'lambda': xmlutil.child_floats(node, 'frame/lambda_[min,max]'),
            'phi': xmlutil.child_floats(node, 'frame/phi_[min,max]'),
        }],
    )


def transfo_dist(source, target, transfo, root):
    node = xmlutil.child(root, 'geometry/intrinseque/sensor')
    return api.Transfo(
        source, target, transfo,
        name='{name}#distortion'.format(**transfo),
        type_name='poly_radial_7',
        func_signature=['C', 'R'],
        parameters=[{
            'C': xmlutil.child_floats(node, 'distortion/pps/[c,l]'),
            'R': xmlutil.child_floats(node, 'distortion/[r3,r5,r7]'),
        }],
    )


def transfo_quat(source, target, transfo, acquisition, root):
    node = xmlutil.child(root, 'geometry/extrinseque')
    p = xmlutil.child_floats(node, 'sommet/[easting,northing,altitude]')
    reverse = xmlutil.child_bool(node, 'rotation/Image2Ground')
    if node.find('rotation/quaternion') is None:
        return api.noobj

    quat = xmlutil.child_floats(node, 'rotation/quaternion/[x,y,z,w]')
    return api.Transfo(
        source, target, transfo,
        name='{name}#quaternion'.format(**transfo),
        type_name='affine_quat',
        func_signature=['quat', 'vec3', '_time'],
        parameters=[{'quat': quat, 'vec3': p, '_time': acquisition}],
        reverse=reverse,
    )


def transfo_matr(source, target, transfo, acquisition, root):
    node = xmlutil.child(root, 'geometry/extrinseque')
    p = xmlutil.child_floats(node, 'sommet/[easting,northing,altitude]')
    reverse = xmlutil.child_bool(node, 'rotation/Image2Ground')
    if node.find('rotation/mat3d') is None:
        return api.noobj

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

    return api.Transfo(
        source, target, transfo,
        name='{name}#mat3d'.format(**transfo),
        type_name='affine_mat4x3',
        func_signature=['mat4x3', '_time'],
        parameters=[{'mat4x3': matrix, '_time': acquisition}],
        reverse=reverse,
    )
