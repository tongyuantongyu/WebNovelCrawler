import os
import pathlib
import pickle
import sys
from typing import Type

import bs4
from bs4 import BeautifulSoup, Tag, NavigableString
from tqdm import tqdm

import sources
from util import NovelDB, LinearMenu, Episode
from .base import Base


def render_line(p: bs4.Tag):
    text = ''
    if 'class' in p.attrs:
        if 'blank' in p.attrs['class']:
            count = len([node for node in p.contents if isinstance(node, Tag) if node.name == 'br'])
            return '\\\\' if count == 1 else f'\\vspace{{{count}\\baselineskip}}'
        elif 'split' in p.attrs['class']:
            return '----------\\\\'
    if not p.text.strip():
        return '\\\\'

    for node in p.contents:
        match node:
            case NavigableString():
                text += node
            case Tag(name='em', attrs={'class': ['dot']}):
                text += f"\\textbf{{{node.text}}}"
            case Tag(name='ruby'):
                base, ruby = [], []
                for piece in node.contents:
                    match piece:
                        case Tag(name='rb'):
                            base.append(piece.text)
                        case Tag(name='rt'):
                            ruby.append(piece.text)
                text += f"\\ruby{{{'|'.join(base)}}}{{{'|'.join(ruby)}}}"
            case _:
                text += node.text

    text = text.strip()
    return text


def render_episode(episode):
    content = BeautifulSoup(episode.content, 'lxml').select_one('.content')
    text = []
    for line in content.contents:
        if not isinstance(line, Tag):
            continue
        t = render_line(line)
        if text and t == '\\\\':
            text[-1] += t
        else:
            text.append("% " + t)

    title = f"\\subsection{{{episode.title}}}"
    text = '\n\n\n'.join(text) + '\n\n\n'

    content = f"""% {title}
{title}

{text}"""

    return content


class MakeTex(Base):
    command = "tex"
    description = "build TeX Files for translation"
    parametric = True

    def execute(self, source: Type[sources.Base], source_id: str):
        book_id = f"{source.source}:{source_id}"

        db = NovelDB()
        book = db.find_book(source_id, source.source)
        linear_menu: LinearMenu = pickle.loads(book.menu)
        episodes = {i.source_id: i for i in db.findall_episode(book.id)}

        folder = book.title[:63]
        for char in "\\/?*:\"|<>":
            folder = folder.replace(char, '_')
        folder = pathlib.Path("texfile") / folder
        os.makedirs(folder, exist_ok=True)
        entries = [item for item in linear_menu.items if isinstance(item, Episode)]
        for idx, item in enumerate(tqdm(entries, desc="Render episodes", file=sys.stdout)):
            tex = render_episode(episodes[item.id])
            with open(folder / f"{idx + 1:0>4}.tex", "wb") as episode:
                episode.write(tex.encode())
        print(f"Book {book_id} saved to {folder}")
