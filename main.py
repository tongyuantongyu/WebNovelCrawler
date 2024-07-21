import code
import sys

import cmd
import sources


def handle_once(fields, last):
    raw_action, *args = fields
    action = cmd.Base.commands.get(raw_action)
    if action is None:
        print(f'Unknown command "{raw_action}"')
        return []

    if args:
        if not action.parametric:
            print(f'Command {raw_action} does not accept parameters')
        try:
            last = [sources.Base.detect_source(arg) for arg in args]
        except (KeyError, ValueError) as e:
            print(e)
            return None

    if action.parametric:
        if last is None:
            print(f'Command {raw_action} accepts parameters but no parameter is given')
            return None
        for source, source_id in last:
            action().execute(source, source_id)
    else:
        last = None
        action().execute(None, None)

    return last


class MyInteractive(code.InteractiveConsole):
    def __init__(self):
        super().__init__()
        self.closed = False
        self.last = None

    def write(self, data):
        sys.stdout.write(data)
        sys.stdout.flush()

    def raw_input(self, prompt=""):
        if self.closed:
            raise EOFError()

        return super().raw_input(prompt)

    def runsource(self, source, filename="<input>", symbol="single"):
        fields = [i for i in source.split(' ') if i]
        if not fields:
            return False

        if fields[0] == "exit":
            self.closed = True
            return False

        self.last = handle_once(fields, self.last)
        return False


if __name__ == '__main__':
    if len(sys.argv) > 1:
        handle_once(sys.argv[1:], None)
    else:
        MyInteractive().interact(banner="Novel Crawl and Storage tool", exitmsg="")
