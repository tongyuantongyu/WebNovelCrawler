import abc


def make_track_sub_meta(field):
    base_field = field + "s"

    class TrackSubMeta(abc.ABCMeta):
        def __init__(cls, name, bases, attrs):
            if not getattr(cls, "__abstractmethods__", False):
                for class_ in cls.__mro__:
                    if class_ == cls:
                        continue
                    if hasattr(class_, base_field):
                        getattr(class_, base_field)[getattr(cls, field)] = cls
                        break
            super().__init__(name, bases, attrs)

    return TrackSubMeta
