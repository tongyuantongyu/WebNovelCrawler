import cmd
import sources


def handle_once(last):
    line = input('> ')
    fields = [i for i in line.split(' ') if i]
    if not fields:
        return last

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
        except ValueError as e:
            print(e)
            return []

    if action.parametric:
        for source, source_id in last:
            action().execute(source, source_id)
    else:
        last = []
        action().execute(None, None)

    return last


def main():
    print("Novel Crawl and Storage tool")
    last = []
    while True:
        try:
            last = handle_once(last)
        except KeyboardInterrupt:
            return


if __name__ == '__main__':
    main()
