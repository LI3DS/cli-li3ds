import logging
import datetime
import pathlib
import json
import pytz
import re
import parse

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
            '--image-dir', '-d',
            help='base directory to search for images (optional, default is ".")')
        parser.add_argument(
            '--json-dir', '-j',
            type=pathlib.Path,
            help='directory including the json files with date/time information')
        parser.add_argument(
            '--filter', '-f',
            help='file name filtering pattern')
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
            '--pattern', '-p', default='{project}_{session}_{section}_{image}_{camera}_{suffix}',
            help='pattern to extract metadata from the stem of the image file names')
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
                if parsed_args.filter:
                    match = re.match(parsed_args.filter, image_path.name)
                    if not match:
                        continue
                self.log.info('Importing {}'.format(image_path.relative_to(image_dir)))
                self.handle_image(objs, args, image_dir, image_path, base_uri,
                                  parsed_args.image_size, parsed_args.json_dir, parsed_args.pattern)

        objs.get_or_create()
        self.log.info('Success!\n')

    @classmethod
    def handle_image(cls, objs, args, image_dir, image_path, base_uri, image_size, json_dir, pattern):

        parsed = parse.parse(pattern, image_path.stem)
        if parsed:
            parsed = parsed.named
        else:
            # self.log.error('filename parsing failed')
            return

        image_time = cls.lookup_image_datetime(json_dir, parsed.get('session'), parsed.get('section'), image_path.stem)

        metadata = {
            'basename': image_path.name,
            'camera': parsed.get('camera','camera'),
            'project': parsed.get('project','project'),
            'section': parsed.get('section','section'),
            'session': parse_date(parsed.get('session','0001010000')),
            'image_time_iso': api.isoformat(image_time),
            'platform': 'Stereopolis II',
        }
        print(parsed)

        sensor = {
            'type': 'camera',
            'name': '{camera}',
            'description': 'Created while importing {basename}',
        }
        referential = {
            'name': '{camera}',
        }
        platform = {
            'name': '{platform}',
        }
        project = {
            'name': '{project}',
        }
        session = {
            'name': '{session:%y%m%d%H%M}/{section}',
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
        referential = referential_image(referential, sensor)
        datasource = datasource_image(
                datasource, session, referential,
                image_dir, image_path, base_uri, image_size)

        objs.add(datasource)

    @classmethod
    def lookup_image_datetime(cls, json_dir, session, section, image_id):
        if not json_dir or not session or not section:
            return None

        image_id_no_cam = '_'.join(image_id.split('_')[0:-1])
        if image_id_no_cam in cls.image_date_cache:
            return cls.image_date_cache[image_id_no_cam]
        json_file = json_dir / '{}-{}.json'.format(session, section)
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


def parse_date(date_string):
    if date_string:
        dt = datetime.datetime.strptime(date_string, '%y%m%d%H%M')
        return pytz.UTC.localize(dt)
    return None

def sensor_camera(sensor, image_size):
    sensor['name'] = sensor['prefix'] + sensor['name']
    del sensor['prefix']
    specifications = {}
    if image_size:
        specifications['image_size'] = image_size
    return api.Sensor(sensor, specifications=specifications)


def referential_image(referential, sensor):
    description = 'origin: top left corner of top left pixel, ' \
                  '+XY: raster pixel coordinates, ' \
                  '+Z: inverse depth (measured along the optical axis). ' \
                  '{description}'.format(**referential)
    name = '{prefix}{name} image'.format(**referential)
    del referential['prefix']
    return api.Referential(sensor, referential, name=name, description=description)


def datasource_image(datasource, session, referential, image_dir, image_path, base_uri, image_size):
    image_path = image_path.relative_to(image_dir)
    if base_uri:
        image_path = base_uri / image_path
    uri = 'file:{}'.format(image_path)
    bounds = [0, image_size[0], 0, 0, image_size[1], 0] if image_size else None
    return api.Datasource(
            session, referential, datasource,
            type='image', uri=uri, bounds=bounds)
