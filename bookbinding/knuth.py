"""Classes that support Knuth TeX-style paragraph breaking."""

from __future__ import print_function

import re
from .texlib.wrap import ObjectList, Box, Glue, Penalty
from .hyphenate import hyphenate_word

NONWORD = re.compile(r'(\W+)')
BREAKING_SPACE = re.compile(r'[ \n]+')
ZERO_WIDTH_BREAK = Glue(0, 0, 0)

def knuth_paragraph(actions, a, fonts, line, next_line,
                    indent, first_indent, fonts_and_texts):

    font_name = fonts_and_texts[0][0]
    font = fonts[font_name]
    width_of = font.width_of

    leading = max(fonts[name].leading for name, text in fonts_and_texts)
    height = max(fonts[name].height for name, text in fonts_and_texts)

    line = next_line(line, leading, height)
    line_lengths = [line.column.width]  # TODO: support interesting shapes

    if first_indent is True:
        first_indent = font.height

    olist = ObjectList()
    # olist.debug = True

    if first_indent:
        olist.append(Glue(first_indent, 0, 0))

    # TODO: get rid of this since it changes with the font?  Compute
    # and pre-cache them in each metrics cache?
    space_width = width_of(u'm m') - width_of(u'mm')

    # TODO: should do non-breaking spaces with glue as well
    space_glue = Glue(space_width, space_width * .5, space_width * .3333)

    findall = re.compile(r'([\u00a0]?)(\w*)([^\u00a0\w\s]*)([ \n]*)').findall

    def text_boxes(text):
        for control_code, word, punctuation, space in findall(text):
            if control_code:
                if control_code == '\xa0':
                    yield space_glue
                    yield Penalty(0, 999999)
                else:
                    print('Unsupported control code: %r' % control_code)
            if word:
                yield from word_boxes(word)
            if punctuation:
                yield Box(width_of(punctuation), punctuation)
                if punctuation == u'-':
                    yield ZERO_WIDTH_BREAK
            if space:
                yield space_glue

    def word_boxes(word):
        pieces = iter(hyphenate_word(word))
        piece = next(pieces)
        yield Box(width_of(piece), piece)
        for piece in pieces:
            yield Penalty(width_of(u'-'), 100)
            yield Box(width_of(piece), piece)

    indented_lengths = [length - indent for length in line_lengths]

    for font, text in fonts_and_texts:
        olist.append(Box(0, font))  # special sentinel
        olist.extend(text_boxes(text))

    if olist[-1] is space_glue:
        olist.pop()             # ignore trailing whitespace

    olist.add_closing_penalty()

    for tolerance in 1, 2, 3, 4:
        try:
            breaks = olist.compute_breakpoints(
                indented_lengths, tolerance=tolerance)
        except RuntimeError:
            pass
        else:
            break
    else:
        print('FAIL')  # TODO
        breaks = [0, len(olist) - 1]  # TODO

    assert breaks[0] == 0
    start = 0

    for i, breakpoint in enumerate(breaks[1:]):
        r = olist.compute_adjustment_ratio(start, breakpoint, i,
                                           indented_lengths)

        #r = 1.0

        xlist = []
        x = 0
        for i in range(start, breakpoint):
            box = olist[i]
            if box.is_glue():
                x += box.compute_width(r)
            elif box.is_box():
                if box.width:
                    xlist.append((x + indent, box.character))
                    x += box.width
                else:
                    xlist.append((None, box.character))

        bbox = olist[breakpoint]
        if bbox.is_penalty() and bbox.width:
            xlist.append((x + indent, u'-'))

        line.graphics.append((knuth_draw, xlist))
        line = next_line(line, leading, height)
        start = breakpoint + 1

    return a + 1, line.previous

def knuth_draw(fonts, line, painter, xlist):
    pt = 1200 / 72.0
    font = fonts['body-roman']
    for x, text in xlist:
        if x is None:
            font = fonts[text]
            painter.setFont(font.qt_font)
        else:
            x = (line.column.x + x) * pt
            y = (line.column.y + line.y - font.descent) * pt
            painter.drawText(x, y, text)
