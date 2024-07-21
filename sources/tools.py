from bs4 import NavigableString, Tag


# normalize ruby based emphasis
def normalize_ruby_emphasis(content: Tag):
    for em_ruby in content.select('ruby'):
        rts = em_ruby.select('rt')
        if not all(all(char == '・' for char in rt.text) for rt in rts):
            continue

        base = ''.join(part.strip() for part in em_ruby if isinstance(part, NavigableString))
        em_ruby.attrs = {'class': 'dot'}
        em_ruby.name = 'em'
        em_ruby.clear(True)
        em_ruby.append(NavigableString(base))
