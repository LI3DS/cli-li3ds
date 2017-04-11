import sys
from cliff.app import App
from cliff.commandmanager import CommandManager


class Mm2Li(App):

    def __init__(self):
        super(Mm2Li, self).__init__(
            description='The "micmac to li3ds" command line',
            version='0.1',
            command_manager=CommandManager('mm2li'),
            deferred_help=True
        )


def main(argv=sys.argv[1:]):
    mm2li = Mm2Li()
    return mm2li.run(argv)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
