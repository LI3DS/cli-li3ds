import logging
import datetime
import pathlib
import pytz
import re

from cliff.command import Command

from . import api


class ImportImage(Command):
    """ import one or several images
    """

    log = logging.getLogger(__name__)

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
            '--filename-pattern', '-p',
            help='file name pattern')
        parser.add_argument(
            '--base-uri', '-b',
            help='base directory in image URIs (optional, default is None)')
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

        for filename in parsed_args.filename:
            for image_path in image_dir.rglob(filename):
                if parsed_args.filename_pattern:
                    match = re.match(parsed_args.filename_pattern, image_path.name)
                    if not match:
                        continue
                self.log.info('Importing {}'.format(image_path.relative_to(image_dir)))
                self.handle_image(objs, image_dir, image_path, base_uri,
                                  parsed_args.image_size)

        objs.get_or_create()
        self.log.info('Success!\n')

    @staticmethod
    def handle_image(objs, image_dir, image_path, base_uri, image_size):

        project_name, session_time, section_name, image_num, camera_num = \
            parse_image_path(image_path)

        metadata = {
            'basename': image_path.name,
            'camera_num': camera_num,
            'project_name': project_name,
            'section_name': section_name,
            'session_time': session_time,
            'session_time_iso': api.isoformat(session_time),
        }

        sensor = {
            'type': 'camera',
            'name': '{camera_num}',
            'description': 'Created while importing {basename}',
        }
        referential = {
            'name': 'camera',
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
            'capture_start': '{session_time_iso}',
            'capture_end': '{session_time_iso}',
        }
        api.update_obj(None, metadata, sensor, 'sensor')
        api.update_obj(None, metadata, referential, 'referential')
        api.update_obj(None, metadata, platform, 'platform')
        api.update_obj(None, metadata, project, 'project')
        api.update_obj(None, metadata, session, 'session')
        api.update_obj(None, metadata, datasource, 'datasource')

        sensor = sensor_camera(sensor, image_size)
        project = api.Project(project)
        platform = api.Platform(platform)
        session = api.Session(project, platform, session)
        referential = referential_camera(referential, sensor)
        datasource = datasource_image(
                datasource, session, referential,
                image_dir, image_path, base_uri, image_size)

        objs.add(datasource)


def parse_image_path(image_path):
    parts = image_path.stem.split('_')
    if len(parts) < 5:
        err = 'Error:image filename structure is unknown'
        raise RuntimeError(err)
    project_name = parts[0]
    session_time = parse_date(parts[1])
    section_name = parts[2]
    image_num = parts[3]
    camera_num = parts[4]
    return project_name, session_time, section_name, image_num, camera_num


def parse_date(date_string):
    dt = datetime.datetime.strptime(date_string, '%y%m%d%H%M')
    return pytz.UTC.localize(dt)


def sensor_camera(sensor, image_size):
    specifications = {}
    if image_size:
        specifications['image_size'] = image_size
    return api.Sensor(sensor, specifications=specifications)


def referential_camera(referential, sensor):
    description = 'origin: top left corner of top left pixel, ' \
                  '+XY: raster pixel coordinates, ' \
                  '+Z: inverse depth (measured along the optical axis).'
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
