import logging

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
        return parser

    def take_action(self, parsed_args):
        server = api.ApiServer(parsed_args, self.log)
        objs = api.ApiObjs(server)

        self.log.info('Importing platform configuration sample')

        lidar = api.Sensor({
            'name': 'lidar',
            'type': 'lidar',
            'description': 'Imported from cli-li3ds'})

        ins = api.Sensor({
            'name': 'ins',
            'type': 'ins',
            'description': 'Imported from cli-li3ds'})

        camera_group = api.Sensor({
            'name': 'cameraMetaData.json',
            'type': 'group'})

        ref_camera_group = api.Referential(
            camera_group,
            {'name': 'base'})

        ref_lidar = api.Referential(
            lidar,
            {'name': 'lidar cartesian'})

        ref_ins = api.Referential(
            ins,
            {'name': 'ins'})

        identity = api.TransfoType(
            name='identity',
            func_signature=['mat4x3']
        )

        transfo_ins2camera_group = api.Transfo(
            ref_ins,
            ref_camera_group,
            name='identity',
            transfo_type=identity,
            parameters=[
                {'mat4x3': [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0]}
            ])
        transfo_lidar2ins = api.Transfo(
            ref_lidar,
            ref_ins,
            name='identity',
            transfo_type=identity,
            parameters=[
                {'mat4x3': [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0]}
            ])

        transfotree_ins2cam = api.Transfotree([transfo_ins2camera_group], name='ins2cam')
        transfotree_lidar2ins = api.Transfotree([transfo_lidar2ins], name='lidar2ins')

        pconfig = api.Config(
            api.Platform(name='Stereopolis II'),
            [transfotree_ins2cam, transfotree_lidar2ins],
            name='test_platform')

        objs.add(pconfig)
        objs.get_or_create()
        self.log.info('Success!\n')
