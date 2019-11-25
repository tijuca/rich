from __future__ import annotations

import textwrap
from typing import Any, Dict, Union

from pygments.lexers import get_lexer_by_name
from pygments.styles import get_style_by_name
from pygments.token import Token
from pygments.util import ClassNotFound

from .color import Color, parse_rgb_hex, blend_rgb
from .console import Console, ConsoleOptions, RenderResult, Segment, ConsoleRenderable
from .style import Style
from .text import Text
from ._tools import iter_first


class Syntax:
    def __init__(
        self,
        code: str,
        lexer_name: str,
        *,
        style: Union[str, Style] = None,
        theme: str = "emacs",
        dedent: bool = True,
        line_numbers: bool = False,
        start_line: int = 1,
    ) -> None:

        if dedent:
            code = textwrap.dedent(code)
        self.code = code
        self.lexer_name = lexer_name
        self.style = style
        self.theme = theme
        self.dedent = dedent
        self.line_numbers = line_numbers
        self.start_line = start_line

        self._style_cache: Dict[Any, Style] = {}

        try:
            self._pygments_style_class = get_style_by_name(theme)
        except ClassNotFound:
            self._pygments_style_class = get_style_by_name("default")

        self._background_color = self._pygments_style_class.background_color[1:]

    def _get_theme_style(self, token_type) -> Style:
        if token_type in self._style_cache:
            style = self._style_cache[token_type]
        else:
            pygments_style = self._pygments_style_class.style_for_token(token_type)

            color = pygments_style["color"]
            bgcolor = pygments_style["bgcolor"]
            style = Style(
                color="#" + color if color else "#000000",
                bgcolor="#" + bgcolor if bgcolor else self._background_color,
                bold=pygments_style["bold"],
                italic=pygments_style["italic"],
                underline=pygments_style["underline"],
            )
            self._style_cache[token_type] = style

        return style.copy()

    def _get_default_style(self) -> Style:

        style = self._get_theme_style(Token.Text)
        style = style.apply(Style(bgcolor=self._pygments_style_class.background_color))

        return style

    def _highlight(self, lexer_name: str) -> Text:
        default_style = self._get_default_style()

        try:
            lexer = get_lexer_by_name(lexer_name)
        except ClassNotFound:
            return Text(self.code, style=default_style)
        text = Text(style=default_style)
        for token_type, token in lexer.get_tokens(self.code):
            style = self._get_theme_style(token_type)
            text.append(token, style)
        return text

    def _get_line_numbers_color(self) -> Color:
        background_color = parse_rgb_hex(
            self._pygments_style_class.background_color[1:]
        )
        foreground_color = self._get_theme_style(Token.Text)._color
        if foreground_color is None:
            return Color.default()
        # TODO: Handle no full colors here
        assert foreground_color.triplet is not None
        new_color = blend_rgb(background_color, foreground_color.triplet)
        return Color.from_triplet(new_color)

    def __console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        code = self.code
        if self.dedent:
            code = textwrap.dedent(code)
        text = self._highlight(self.lexer_name)
        if not self.line_numbers:
            yield text
            return

        lines = text.split("\n")
        numbers_column_width = len(str(self.start_line + len(lines))) + 2
        render_options = options.with_width(options.max_width - numbers_column_width)

        if self.style is None:
            background_style = Style(
                bgcolor=self._pygments_style_class.background_color
            )
        else:
            if isinstance(self.style, str):
                background_style = console.parse_style(self.style) or Style()
            else:
                background_style = self.style

        number_style = background_style.apply(self._get_theme_style(Token.Text))
        number_style._color = self._get_line_numbers_color()
        padding = Segment(" " * numbers_column_width, background_style)
        new_line = Segment("\n")
        for line_no, line in enumerate(lines, self.start_line):
            wrapped_lines = console.render_lines([line], render_options)
            for first, wrapped_line in iter_first(wrapped_lines):
                if first:
                    yield Segment(
                        f" {str(line_no).rjust(numbers_column_width - 2)} ",
                        number_style,
                    )
                else:
                    yield padding
                yield from wrapped_line
                yield new_line


CODE = r'''
    def __console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        """This is a docstring."""
        code = self.code
        if self.dedent:
            code = textwrap.dedent(code)
        text = highlight(code, self.lexer_name, theme=self.theme)
        if not self.line_numbers:
            yield text
            return

        # This is a comment
        lines = text.split("\n")
        numbers_column_width = len(str(len(lines))) + 1
        render_options = options.with_width(options.max_width - numbers_column_width)

        padding = Segment(" " * numbers_column_width)
        new_line = Segment("\n")
        for line_no, line in enumerate(lines, self.start_line):

            wrapped_lines = console.render_lines([line], render_options)
            for first, wrapped_line in iter_first(wrapped_lines):
                if first:
                    yield Segment(f"{line_no}".ljust(numbers_column_width))
                else:
                    yield padding
                yield from wrapped_line
                yield new_line
'''

if __name__ == "__main__":

    syntax = Syntax(CODE, "python", dedent=True, line_numbers=True, start_line=990)
    console = Console()
    console.print(syntax)
