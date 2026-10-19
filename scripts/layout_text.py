"""Measure and wrap mixed Chinese/Latin runs without drawing any images."""
from functools import lru_cache
import re

from PIL import ImageFont

CLOSING = set('，。；：！？、）］】》〉”’％,.;:!?)]}%')
OPENING = set('（［【《〈“‘([{')


def split_at_source_lines(segments, source_lines):
    """Preserve visible reference line breaks without losing run emphasis."""
    full = ''.join(s['text'] for s in segments)
    if ''.join(source_lines) != full:
        raise ValueError('Source lines must preserve the complete transcribed text exactly')
    characters = []
    for segment in segments:
        for char in segment['text']:
            characters.append({**segment, 'text': char})
    result, offset = [], 0
    for line in source_lines:
        runs = []
        for char in characters[offset:offset+len(line)]:
            style = {k: v for k, v in char.items() if k != 'text'}
            if runs and {k: v for k, v in runs[-1].items() if k != 'text'} == style:
                runs[-1]['text'] += char['text']
            else: runs.append(dict(char))
        result.append(runs)
        offset += len(line)
    return result


@lru_cache(maxsize=64)
def _font(path, size10, index):
    return ImageFont.truetype(path, size=size10, index=index)


def wrap_segments(segments, width, size, regular_font, bold_font, font_index=0, reserve=7):
    """Return line runs, preserving every character and its authored emphasis.

    Latin words/numbers stay intact. Closing punctuation is kept with preceding
    content; opening punctuation is carried to the following line. Final Office
    rendering remains necessary because its font metrics may differ.
    """
    if width <= reserve or size <= 0:
        raise ValueError('Invalid text geometry')
    tokens = []
    for segment in segments:
        if not isinstance(segment.get('text'), str):
            raise ValueError('Segment text must be a string')
        for value in re.findall(r'[A-Za-z0-9]+(?:[.+/%-][A-Za-z0-9]+)*|[^\n]|\n', segment['text']):
            token = {**segment, 'text': value}
            font = _font(bold_font if segment.get('bold') else regular_font, round(size*10), font_index)
            token['_width'] = font.getlength(value)/10 if value != '\n' else 0
            if token['_width'] > width:
                raise ValueError(f'Unbreakable token wider than text box: {value}')
            tokens.append(token)
    lines, current, used = [], [], 0
    for token in tokens:
        value, tw = token['text'], token['_width']
        if value == '\n':
            lines.append(current); current, used = [], 0
            continue
        if current and used+tw > width-reserve:
            if value[0] in CLOSING and used+tw <= width:
                current.append(token); used += tw
                continue
            carry = []
            if value[0] in CLOSING:
                while current and current[-1]['text'][0] in CLOSING:
                    carry.insert(0, current.pop())
                if current:
                    carry.insert(0, current.pop())
            while current and current[-1]['text'][-1] in OPENING:
                carry.insert(0, current.pop())
            if current: lines.append(current)
            current = carry
            used = sum(t['_width'] for t in current)
        current.append(token); used += tw
    if current: lines.append(current)
    result = []
    for line in lines:
        runs = []
        for token in line:
            run = {k: v for k, v in token.items() if k != '_width'}
            style = {k: v for k, v in run.items() if k != 'text'}
            if runs and {k: v for k, v in runs[-1].items() if k != 'text'} == style:
                runs[-1]['text'] += run['text']
            else: runs.append(run)
        result.append(runs)
    return result
