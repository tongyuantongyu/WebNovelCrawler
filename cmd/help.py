from .base import Base


class Help(Base):
    command = "help"
    description = "print help"
    parametric = False

    def execute(self, _, _1):
        print("Available commands:")
        for name, command in Base.commands.items():
            if command.parametric:
                name += " desc"
            print(f"    {name: <14}    {command.description}")
