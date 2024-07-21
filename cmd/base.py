from __future__ import annotations

import abc
from typing import Dict, Type

import sources
from util import make_track_sub_meta


class Base(metaclass=make_track_sub_meta("command")):
    commands: Dict[str, Type[Base]] = {}

    @property
    @abc.abstractmethod
    def command(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def description(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def parametric(self) -> bool:
        pass

    @abc.abstractmethod
    def execute(self, source: Type[sources.Base], source_id: str):
        pass
