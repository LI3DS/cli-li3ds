import logging
import datetime
import pathlib
import json
import pytz
import re

from cliff.command import Command

from . import api


class ImportImage(Command):
    """ import one or several images
    """

    log = logging.getLogger(__name__)

    image_date_cache = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_parser(self, prog_name):
        self.log.debug(prog_name)
        parser = super().get_parser(prog_name)
        api.add_arguments(parser)
        parser.add_argument(
            '--image-size', '-z',
            nargs=2, type=float,
            help='image size (e.g. "1200 600") (optional)')
        parser.add_argument(
            '--image-dir', '-f',
            help='base directory to search for images (optional, default is ".")')
        parser.add_argument(
            '--json-dir', '-j',
            type=pathlib.Path,
            help='directory including the json files with date/time information')
        parser.add_argument(
            '--filename-pattern', '-p',
            help='file name pattern')
        parser.add_argument(
            '--base-uri', '-b',
            help='base directory in image URIs (optional, default is None)')
        parser.add_argument(
            '--sensor-prefix', default='',
            help='camera sensor name prefix (optional, default is no prefix)')
        parser.add_argument(
            '--referential-prefix', default='',
            help='referential name prefix (optional, default is no prefix)')
        parser.add_argument(
            'filename', nargs='+',
            help='image file names, may be Unix-style patterns (e.g. *.jpg)')
        return parser

    def take_action(self, parsed_args):
        server = api.ApiServer(parsed_args, self.log)
        objs = api.ApiObjs(server)

        if parsed_args.base_uri:
            base_uri = pathlib.Path(parsed_args.base_uri)
        else:
            base_uri = None

        if parsed_args.image_dir:
            image_dir = pathlib.Path(parsed_args.image_dir)
        else:
            image_dir = pathlib.Path('.')

        args = {
            'referential': {
                'prefix': parsed_args.referential_prefix,
            },
            'sensor': {
                'prefix': parsed_args.sensor_prefix,
            },
        }

        for filename in parsed_args.filename:
            for image_path in image_dir.rglob(filename):
                if parsed_args.filename_pattern:
                    match = re.match(parsed_args.filename_pattern, image_path.name)
                    if not match:
                        continue
                self.log.info('Importing {}'.format(image_path.relative_to(image_dir)))
                self.handle_image(objs, args, image_dir, image_path, base_uri,
                                  parsed_args.image_size, parsed_args.json_dir)

        objs.get_or_create()
        self.log.info('Success!\n')

    @classmethod
    def handle_image(cls, objs, args, image_dir, image_path, base_uri, image_size, json_dir):

        project_name, session_time, section_name, image_num, camera_num = \
            parse_image_path(image_path)

        image_time = cls.lookup_image_datetime(
            json_dir, session_time, section_name, image_path.stem)

        metadata = {
            'basename': image_path.name,
            'camera_num': camera_num,
            'project_name': project_name,
            'section_name': section_name,
            'session_time': parse_date(session_time),
            'image_time_iso': api.isoformat(image_time),
        }

        sensor = {
            'type': 'camera',
            'name': '{camera_num}',
            'description': 'Created while importing {basename}',
        }
        referential = {
            'name': '{camera_num}',
        }
        platform = {
            'name': 'Stereopolis II',
        }
        project = {
            'name': '{project_name}',
        }
        session = {
            'name': '{session_time:%y%m%d}/{section_name}',
        }
        datasource = {
            'capture_start': '{image_time_iso}',
            'capture_end': '{image_time_iso}',
        }
        api.update_obj(args, metadata, sensor, 'sensor')
        api.update_obj(args, metadata, referential, 'referential')
        api.update_obj(args, metadata, platform, 'platform')
        api.update_obj(args, metadata, project, 'project')
        api.update_obj(args, metadata, session, 'session')
        api.update_obj(args, metadata, datasource, 'datasource')

        sensor = sensor_camera(sensor, image_size)
        project = api.Project(project)
        platform = api.Platform(platform)
        session = api.Session(project, platform, session)
        referential = referential_camera(referential, sensor)
        datasource = datasource_image(
                datasource, session, referential,
                image_dir, image_path, base_uri, image_size)

        objs.add(datasource)

    @classmethod
    def lookup_image_datetime(cls, json_dir, session_time, section_name, image_id):
        if not json_dir:
            return None
        image_id_no_cam = '_'.join(image_id.split('_')[0:-1])
        if image_id_no_cam in cls.image_date_cache:
            return cls.image_date_cache[image_id_no_cam]
        json_file = json_dir / '{}-{}.json'.format(session_time, section_name)
        if not json_file.is_file():
            err = '{} is not a file'.format(str(json_file))
            raise RuntimeError(err)
        cls.image_date_cache.clear()
        cls.log.debug('Reading {}'.format(str(json_file)))
        with json_file.open() as f:
            image_objs = json.load(f)
        for image_obj in image_objs:
            # image_obj['date'] is the number of seconds since January 5, 1980 (GPS time
            # reference) minus 1e9. So we add 1e9 and 315964800 to get the number of
            # seconds since January 1, 1970.
            dt = datetime.datetime.fromtimestamp(image_obj['date'] + 1e9 + 315964800, tz=pytz.UTC)
            cls.image_date_cache[image_obj['id']] = dt
        assert(image_id_no_cam in cls.image_date_cache)
        return cls.image_date_cache[image_id_no_cam]


def parse_image_path(image_path):
    parts = image_path.stem.split('_')
    if len(parts) < 5:
        err = 'Error:image filename structure is unknown'
        raise RuntimeError(err)
    project_name = parts[0]
    session_time = parts[1]
    section_name = parts[2]
    image_num = parts[3]
    camera_num = parts[4]
    return project_name, session_time, section_name, image_num, camera_num


def parse_date(date_string):
    dt = datetime.datetime.strptime(date_string, '%y%m%d%H%M')
    return pytz.UTC.localize(dt)


def sensor_camera(sensor, image_size):
    sensor['name'] = sensor['prefix'] + sensor['name']
    del sensor['prefix']
    specifications = {}
    if image_size:
        specifications['image_size'] = image_size
    return api.Sensor(sensor, specifications=specifications)


def referential_camera(referential, sensor):
    description = 'origin: top left corner of top left pixel, ' \
                  '+XY: raster pixel coordinates, ' \
                  '+Z: inverse depth (measured along the optical axis).'
    referential['name'] = '{prefix}{name}'.format(**referential)
    del referential['prefix']
    return api.Referential(
            sensor, referential, description=description)


def datasource_image(datasource, session, referential, image_dir, image_path, base_uri, image_size):
    image_path = image_path.relative_to(image_dir)
    if base_uri:
        image_path = base_uri / image_path
    uri = 'file:{}'.format(image_path)
    bounds = [0, image_size[0], 0, 0, image_size[1], 0] if image_size else None
    return api.Datasource(
            session, referential, datasource,
            type='image', uri=uri, bounds=bounds)
