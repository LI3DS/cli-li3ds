import sys
from cliff.app import App
from cliff.commandmanager import CommandManager


class Li3ds(App):

    def __init__(self):
        super().__init__(
            description='The li3ds command line',
            version='0.1',
            command_manager=CommandManager('li3ds'),
            deferred_help=True
        )


def main(argv=sys.argv[1:]):
    app = Li3ds()
    return app.run(argv)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
