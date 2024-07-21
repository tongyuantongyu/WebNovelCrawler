from typing import Type

import trio

import sources
from .base import Base


class Fetch(Base):
    command = "fetch"
    description = "fetch new episodes"
    parametric = True

    def execute(self, source: Type[sources.Base], source_id: str):
        fetcher: sources.Base = source(source_id)
        trio.run(fetcher.fetch)
