import copy
import sys
from typing import List, Type

from bs4 import BeautifulSoup, Tag, NavigableString, PageElement
from janome.tokenizer import Tokenizer
from pykakasi.scripts import K2
from tqdm import tqdm

import sources
from util import NovelDB
from .base import Base

tokenizer = Tokenizer()
converter = K2("H")

zygote = BeautifulSoup('<p></p>', 'lxml').find('p')


def make_tag(name):
    tag = copy.copy(zygote)
    tag.name = name
    return tag


def make_ruby(base, reading):
    ruby = make_tag('ruby')

    rb = make_tag('rb')
    rb.append(NavigableString(base))
    ruby.append(rb)

    rt = make_tag('rt')
    rt.append(NavigableString(reading))
    ruby.append(rt)

    return ruby


def rubify_string(string) -> List[PageElement]:
    content = []
    for word in tokenizer.tokenize(str(string)):
        base, reading = word.surface, word.reading
        if base == reading or reading == '*':
            content.append(NavigableString(base))
            continue

        reading, _ = converter.convert(reading)
        if base == reading:
            content.append(NavigableString(base))
            continue

        prefix, suffix = '', ''
        while base and reading and base[0] == reading[0]:
            prefix += base[0]
            base, reading = base[1:], reading[1:]
        while base and reading and base[-1] == reading[-1]:
            suffix += base[-1]
            base, reading = base[:-1], reading[:-1]
        if prefix:
            content.append(NavigableString(prefix))
        if reading:
            content.append(make_ruby(base, reading))
        else:
            content.append(NavigableString(base))
        if suffix:
            content.append(NavigableString(suffix[::-1]))

    return content


def rubify_line(p: Tag):
    if 'class' in p.attrs and 'blank' in p.attrs['class']:
        return p

    new_content = []
    for item in p.contents:
        match item:
            case NavigableString():
                new_content.extend(rubify_string(item))
            case Tag():
                new_content.append(item)
    p.clear()
    p.extend(new_content)


def rubify_content(content):
    content = BeautifulSoup(content, 'lxml').select_one('.content')
    for line in content.contents:
        if not isinstance(line, Tag) or line.name != 'p':
            continue

        rubify_line(line)

    content = content.decode()
    return content


class BuildRuby(Base):
    command = "ruby"
    description = "update rubified version of episodes"
    parametric = True

    def execute(self, source: Type[sources.Base], source_id: str):
        db = NovelDB()
        book = db.find_book(source_id, source.source)

        episode_ids = db.findall_episode_rubified_stale(book.id)
        if not episode_ids:
            print("Rubified version up to date.")
            return

        for episode_id in tqdm(episode_ids, desc="Rubify episodes", file=sys.stdout):
            s_episode = db.find_episode(book.id, episode_id.source_id)
            content = rubify_content(s_episode.content)
            db.add_rubified(book.id, episode_id.source_id, s_episode.title, content, s_episode.version,
                            s_episode.creation)
