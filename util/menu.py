from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(repr=False)
class Episode:
    id: str
    title: str
    version: int
    creation: int

    def __repr__(self):
        return f"<Episode id={self.id} title={repr(self.title)} version={self.version} creation={self.creation}>"


@dataclass(repr=False)
class Chapter:
    id: str
    title: str
    level: int

    def __repr__(self):
        return f"<Chapter id={self.id} title={repr(self.title)}>"


@dataclass(repr=False)
class NChapter:
    id: str
    title: str
    items: List[NChapter | Episode]

    def __repr__(self):
        return f"<Chapter n_items={len(self.items)} id={self.id} title={repr(self.title)}>"


class Menu:
    def __init__(self):
        self.items: List[NChapter | Episode] = []
        self.episodes: List[Episode] = []
        self._cursor: List[NChapter | Episode] = self.items
        self._stack: List[List[NChapter | Episode]] = []
        self._has_chapter = False

    def _push_chapter(self, level, chapter: NChapter):
        if level >= len(self._stack) + 1:
            # descend chapter
            self._cursor.append(chapter)
            self._stack.append(self._cursor)
            self._cursor = chapter.items
        elif level == len(self._stack):
            # sibling chapter
            self._stack[-1].append(chapter)
            self._cursor = chapter.items
        else:
            # ascend chapter
            while level < len(self._stack) + 1:
                self._cursor = self._stack.pop()
            # re-descent
            self._push_chapter(level, chapter)

    def push_chapter(self, chapter: Chapter):
        self._push_chapter(chapter.level, NChapter(chapter.id, chapter.title, []))
        self._has_chapter = True

    def push_episode(self, episode: Episode):
        self._cursor.append(episode)
        self.episodes.append(episode)

    def finish(self):
        self._stack = None
        self._cursor = None
        if not self._has_chapter:
            self.items = [NChapter('', '目次', self.items)]


class LinearMenu:
    def __init__(self):
        self.items: List[Chapter | Episode] = []

    def push_item(self, item):
        self.items.append(item)

    def get_episodes(self):
        return [episode for episode in self.items if isinstance(episode, Episode)]

    def build_menu(self) -> Menu:
        menu = Menu()
        for item in self.items:
            match item:
                case Chapter():
                    menu.push_chapter(item)
                case Episode():
                    menu.push_episode(item)
        menu.finish()
        return menu
