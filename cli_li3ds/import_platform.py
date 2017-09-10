import math
import logging
import configparser

from pyquaternion import Quaternion

from cliff.command import Command

from . import api


class ImportPlatform(Command):
    """ import a sample platform configuration for stéréopolis
    """

    log = logging.getLogger(__name__)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_parser(self, prog_name):
        self.log.debug(prog_name)
        parser = super().get_parser(prog_name)
        api.add_arguments(parser)
        parser.add_argument(
            'filename', nargs=1,
            help='The TerraMatch corrections file')
        return parser

    def take_action(self, parsed_args):
        server = api.ApiServer(parsed_args, self.log)
        objs = api.ApiObjs(server)

        self.log.info('Importing platform configuration sample')

        lidar_transform_params = self.read_lidar_rigid_transform_params(parsed_args.filename)

        lidar = api.Sensor({
            'name': 'lidar',
            'type': 'lidar',
            'description': 'Imported from cli-li3ds'})

        ins = api.Sensor({
            'name': 'ins',
            'type': 'ins',
            'description': 'Imported from cli-li3ds'})

        camera_group = api.Sensor({
            'name': 'camera group',
            'type': 'group'})

        ref_camera_group = api.Referential(
            camera_group,
            {'name': 'camera-base'})

        ref_lidar = api.Referential(
            lidar,
            {'name': 'lidar cartesian'})

        ref_ins = api.Referential(
            ins,
            {'name': 'ins', 'srid': 4326})

        affine_mat4x3 = api.TransfoType(
            name='affine_mat4x3',
            func_signature=['mat4x3', '_time']
        )

        transfo_ins2camera_group = api.Transfo(
            ref_ins,
            ref_camera_group,
            name='ins2cam',
            transfo_type=affine_mat4x3,
            parameters=[
                {'mat4x3': [-1, 0, 0, 0, 0, -1, 0, 0, 0, 0, 1, 0]}
            ])

        transfo_camera_group2ins = api.Transfo(
            ref_camera_group,
            ref_ins,
            name='cam2ins',
            transfo_type=affine_mat4x3,
            parameters=[
                {'mat4x3': [-1, 0, 0, 0, 0, -1, 0, 0, 0, 0, 1, 0]}
            ])

        affine_quat = api.TransfoType(
            name='affine_quat',
            func_signature=['quat', 'vec3', '_time']
        )

        transfo_lidar2ins = api.Transfo(
            ref_lidar,
            ref_ins,
            name='lidar2ins',
            transfo_type=affine_quat,
            parameters=[lidar_transform_params]
        )

        transfotree_ins2cam = api.Transfotree([transfo_ins2camera_group], name='ins2cam')
        transfotree_cam2ins = api.Transfotree([transfo_camera_group2ins], name='cam2ins')
        transfotree_lidar2ins = api.Transfotree([transfo_lidar2ins], name='lidar2ins')

        pconfig = api.Config(
            api.Platform(name='Stereopolis II'),
            [transfotree_ins2cam, transfotree_lidar2ins],
            name='test_platform')

        objs.add(transfotree_cam2ins, pconfig)
        objs.get_or_create()
        self.log.info('Success!\n')

    @staticmethod
    def read_lidar_rigid_transform_params(filename):
        config = configparser.ConfigParser()
        config.read(filename)

        section = 'TerraMatch corrections v2'

        easting = config.getfloat(section, 'EastingShift')
        northing = config.getfloat(section, 'NorthingShift')
        elevation = config.getfloat(section, 'ElevationShift')

        heading = - math.radians(config.getfloat(section, 'HeadingShift') * 0.5)
        roll = math.radians(config.getfloat(section, 'RollShift') * 0.5)
        pitch = math.radians(config.getfloat(section, 'PitchShift') * 0.5)

        ch = math.cos(heading)
        sh = math.sin(heading)
        cr = math.cos(roll)
        sr = math.sin(roll)
        cp = math.cos(pitch)
        sp = math.sin(pitch)

        qw = - sh * sr * sp + ch * cr * cp
        qx = - sh * cr * sp + ch * sr * cp
        qy = + sh * sr * cp + ch * cr * sp
        qz = + ch * sr * sp + sh * cr * cp
        q_boresight = Quaternion(qw, qx, qy, qz)

        # rotate by π/2 around y and π around z (lidar to ins)
        q_z = Quaternion(axis=(0, 0, 1), radians=math.pi)
        q_y = Quaternion(axis=(0, 1, 0), radians=math.pi/2)

        q = q_z * q_y * q_boresight

        return {'vec3': [easting, northing, elevation], 'quat': [q[0], q[1], q[2], q[3]]}
