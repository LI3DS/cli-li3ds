import os
import logging
import json

from cliff.command import Command

from . import api
from . import xmlutil


class ImportExtCalib(Command):
    """ import external calibration data

        The input file may be a blinis XML file or a Stereopolis cameraMetaData JSON file. The
        command creates a sensor group and corresponding referentials and transforms.
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
            help='the camera group sensor id (optional)')
        parser.add_argument(
            '--sensor', '-s',
            help='the camera group sensor name (optional)')
        parser.add_argument(
            '--sensor-prefix', default='',
            help='camera sensor name prefix (optional, default is no prefix)')
        parser.add_argument(
            '--referential-prefix', default='',
            help='referential name prefix (optional, default is no prefix)')
        parser.add_argument(
            '--transfotree',
            help='the transfotree name (optional)')
        parser.add_argument(
            '--transfo', '-t',
            help='the transfo basename (optional)')
        parser.add_argument(
            '--calibration', '-d',
            help='the calibration datetime (optional')
        parser.add_argument(
            '--validity-start',
            help='validity start date for transfos (optional, '
                 'default is valid since always)')
        parser.add_argument(
            '--validity-end',
            help='validity end date for transfos (optional, '
                 'default is valid until forever)')
        parser.add_argument(
            'filename', nargs='+',
            help='the list of blinis XML or camera metadata JSON files')
        return parser

    def take_action(self, parsed_args):
        """
        Create or update sensor groups.
        """
        server = api.ApiServer(parsed_args, self.log)
        objs = api.ApiObjs(server)

        args = {
            'referential': {
                'prefix': parsed_args.referential_prefix,
            },
            'sensor_group': {
                'name': parsed_args.sensor,
                'id': parsed_args.sensor_id,
            },
            'sensor': {
                'prefix': parsed_args.sensor_prefix,
            },
            'transfo': {
                'name': parsed_args.transfo,
                'tdate': parsed_args.calibration,
                'validity_start': parsed_args.validity_start,
                'validity_end': parsed_args.validity_end,
            },
            'transfotree': {
                    'name': parsed_args.transfotree,
                    'owner': parsed_args.owner,
            },
        }
        for filename in parsed_args.filename:
            self.log.info('Importing {}'.format(filename))
            try:
                self.handle_json_file(objs, args, filename)
            except json.decoder.JSONDecodeError:
                self.handle_xml_file(objs, args, filename)
            objs.get_or_create()
            self.log.info('Success!\n')

    @staticmethod
    def handle_json_file(objs, args, filename):
        with open(filename) as f:
            # raise a json.decoder.JSONDecodeError if the file content is not JSON
            cameras = json.load(f)

        metadata = {
            'basename': os.path.basename(filename),
        }

        sensor_group = {'type': 'group'}
        referential_base = {'name': 'base'}
        transfotree = {}

        api.update_obj(args, metadata, sensor_group, 'sensor_group')
        api.update_obj(args, metadata, referential_base, 'referential')
        api.update_obj(args, metadata, transfotree, 'transfotree')

        sensor_group = api.Sensor(sensor_group)

        referential_base['name'] = referential_base['prefix'] + referential_base['name']
        del referential_base['prefix']
        referential_base = api.Referential(sensor_group, referential_base)

        transfos1 = []
        transfos2 = []
        for camera in cameras:
            metadata['IdGrp'] = camera['id']

            sensor = {'name': '{IdGrp}', 'type': 'camera'}
            referential = {'name': '{IdGrp}'}
            transfo = {'name': '{IdGrp}'}

            api.update_obj(args, metadata, sensor, 'sensor')
            api.update_obj(args, metadata, referential, 'referential')
            api.update_obj(args, metadata, transfo, 'transfo')

            sensor['name'] = sensor['prefix'] + sensor['name']
            del sensor['prefix']

            referential['name'] = referential['prefix'] + referential['name']
            del referential['prefix']

            sensor = api.Sensor(sensor)
            referential = api.Referential(sensor, referential)
            transfo1 = transfo_grp_json(referential_base, referential, transfo, camera, False)
            transfo2 = transfo_grp_json(referential_base, referential, transfo, camera, True)

            transfos1.append(transfo1)
            transfos2.append(transfo2)

        transfotree1 = api.Transfotree(transfos1, transfotree)
        transfotree2 = api.Transfotree(transfos2, transfotree)
        objs.add(transfotree1, transfotree2)

    @staticmethod
    def handle_xml_file(objs, args, filename):
        root = xmlutil.root(filename, 'StructBlockCam')
        nodes = xmlutil.children(root, 'LiaisonsSHC/ParamOrientSHC')

        metadata = {
            'basename': os.path.basename(filename),
            'sensor_name': xmlutil.findtext(root, 'KeyIm2TimeCam'),
        }

        sensor_group = {'name': '{sensor_name}', 'type': 'group'}
        referential_base = {'name': 'base'}
        transfotree = {}

        api.update_obj(args, metadata, sensor_group, 'sensor_group')
        api.update_obj(args, metadata, referential_base, 'referential')
        api.update_obj(args, metadata, transfotree, 'transfotree')

        sensor_group = api.Sensor(sensor_group)

        referential_base['name'] = referential_base['prefix'] + referential_base['name']
        del referential_base['prefix']
        referential_base = api.Referential(sensor_group, referential_base)

        transfos1 = []
        transfos2 = []
        for node in nodes:
            metadata['IdGrp'] = xmlutil.findtext(node, 'IdGrp')

            sensor = {'name': '{IdGrp}', 'type': 'camera'}
            referential = {'name': '{IdGrp}'}
            transfo = {'name': '{IdGrp}'}

            api.update_obj(args, metadata, sensor, 'sensor')
            api.update_obj(args, metadata, referential, 'referential')
            api.update_obj(args, metadata, transfo, 'transfo')

            sensor['name'] = sensor['prefix'] + sensor['name']
            del sensor['prefix']

            referential['name'] = referential['prefix'] + referential['name']
            del referential['prefix']

            sensor = api.Sensor(sensor)
            referential = api.Referential(sensor, referential)
            transfo1 = transfo_grp_xml(referential_base, referential, transfo, node, False)
            transfo2 = transfo_grp_xml(referential_base, referential, transfo, node, True)

            transfos1.append(transfo1)
            transfos2.append(transfo2)

        transfotree1 = api.Transfotree(transfos1, transfotree)
        transfotree2 = api.Transfotree(transfos2, transfotree)
        objs.add(transfotree1, transfotree2)


def transfo_grp(source, target, transfo, matrix, inverse):
    if inverse:
        # transpose the rotation part
        matrix[1], matrix[4] = matrix[4], matrix[1]
        matrix[2], matrix[8] = matrix[8], matrix[2]
        matrix[6], matrix[9] = matrix[9], matrix[6]
        # multiply the translation part by -transposed rotation
        x, y, z = -matrix[3], -matrix[7], -matrix[11]
        matrix[3] = x * matrix[0] + y * matrix[1] + z * matrix[2]
        matrix[7] = x * matrix[4] + y * matrix[5] + z * matrix[6]
        matrix[11] = x * matrix[8] + y * matrix[9] + z * matrix[10]
        source, target = target, source
    return api.Transfo(
        source, target, transfo,
        type_name='affine_mat4x3',
        func_signature=['mat4x3'],
        parameters=[{'mat4x3': matrix}],
    )


def transfo_grp_json(source, target, transfo, node, inverse):
    matrix = []
    p = node['position']
    r = node['rotation']
    for i in range(0, 3):
        matrix.extend(r[i*3:(i+1)*3])
        matrix.append(p[i])
    return transfo_grp(source, target, transfo, matrix, inverse)


def transfo_grp_xml(source, target, transfo, node, inverse):
    matrix = []
    p = xmlutil.child_floats_split(node, 'Vecteur')
    for i, l in enumerate(('Rot/L1', 'Rot/L2', 'Rot/L3')):
        matrix.extend(xmlutil.child_floats_split(node, l))
        matrix.append(p[i])
    return transfo_grp(source, target, transfo, matrix, inverse)
