# WebNovelCrawler

A Python Novel Crawler &amp; Epub Builder using asyncio

This program uses python's new asyncio package to fetch pages.

Works with Python3.5 or higher, but only tested with Python3.6

Syosetu: id means n0611em if you want to crawl ncode.syosetu.com/n0611em/ </br></br>
\[Anti Crawl Found. Working\] Alphapolis: id means 336230288/966208838 if you want to crawl www.alphapolis.co.jp/novel/336230288/966208838</br></br>
Kakuyomu:id means 1177354054880238351 if you want to crawl kakuyomu.jp/works/1177354054880238351</br></br>

Proxies may or may not be used varies from site to site. Configuration is in the file.

Furigana uses kanome and kakasi to work, and will be slow when processing novel that has a lot of words.

TODO:
1. More site.
2. Auto proxy swtich to prevent NoneType Error caused by anti-crawl.

Required libs: requests, beautifulsoup4, ebooklib, aiohttp</br>
Additional required libs for furigana: kanome, kakasi
