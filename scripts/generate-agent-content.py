#!/usr/bin/env python3
"""Regenerate checked-in Markdown from the public HTML pages, using only Python's standard library."""

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin


class MarkdownPage(HTMLParser):
    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base = base
        self.parts = []
        self.stack = []
        self.links = []
        self.skip = 0
        self.in_body = False

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == 'body':
            self.in_body = True
        suppressed = tag in {'head', 'script', 'style', 'svg', 'noscript', 'template', 'nav'}
        suppressed = suppressed or 'hidden' in attrs or attrs.get('aria-hidden') == 'true'
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.stack.append((tag, suppressed))
            if suppressed:
                self.skip += 1
        if self.skip or not self.in_body:
            return
        if tag in {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}:
            self.parts.append('\n\n' + '#' * int(tag[1]) + ' ')
        elif tag in {'p', 'div', 'section', 'article', 'main', 'header', 'footer', 'ul', 'ol', 'dl', 'blockquote'}:
            self.parts.append('\n\n')
        elif tag == 'li':
            self.parts.append('\n- ')
        elif tag in {'br', 'tr'}:
            self.parts.append('\n')
        elif tag in {'td', 'th', 'dd', 'dt'}:
            self.parts.append(' ')
        elif tag == 'a':
            href = attrs.get('href', '')
            safe = href and not href.startswith(('javascript:', 'data:'))
            self.links.append((urljoin(self.base, href) if safe else '', len(self.parts),
                               attrs.get('aria-label') or attrs.get('title') or href))
            if safe:
                self.parts.append('[')
        elif tag == 'img' and attrs.get('alt'):
            self.parts.append(attrs['alt'])

    def handle_endtag(self, tag):
        was_skipping = bool(self.skip)
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                self.skip -= sum(int(skip) for _, skip in self.stack[index:])
                del self.stack[index:]
                break
        if was_skipping or not self.in_body:
            return
        if tag == 'a' and self.links:
            href, start, label = self.links.pop()
            if href:
                caption = re.sub(r'\s+', ' ', ''.join(self.parts[start + 1:])).strip() or label
                self.parts[start:] = ['[' + caption + '](' + href + ')']
        elif tag in {'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'section', 'article', 'main', 'header', 'footer', 'ul', 'ol'}:
            self.parts.append('\n\n')

    def handle_data(self, data):
        if self.in_body and not self.skip:
            self.parts.append(re.sub(r'\s+', ' ', data))

    def markdown(self):
        text = ''.join(self.parts)
        text = re.sub(r'[ \t]+\n', '\n', text)
        text = re.sub(r'\n[ \t]+', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip() + '\n'


def main():
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / 'agent-content.json').read_text())
    site = root / config['site_directory']
    overview = ['# ' + config['name'], '', config['description'], '', '## Public pages', '']
    for page in config['pages']:
        parser = MarkdownPage(config['origin'] + page['path'])
        parser.feed((site / page['file']).read_text())
        content = parser.markdown()
        source = '[Canonical HTML page](' + config['origin'] + page['path'] + ')\n\n'
        (site / page['markdown'].lstrip('/')).write_text(source + content + '\n')
        overview.append('- [' + page['title'] + '](' + config['origin'] + page['markdown'] + ')')
    overview.extend(['', 'The HTML pages are authoritative. Markdown is generated from the same public content.', ''])
    if config.get('preview'):
        overview.extend(['This website is a prelaunch preview and is not intended for search indexing.', ''])
    if not config.get('preserve_llms'):
        (site / 'llms.txt').write_text('\n'.join(overview) + '\n')
    print('Generated Markdown for', len(config['pages']), 'public pages.')


if __name__ == '__main__':
    main()

