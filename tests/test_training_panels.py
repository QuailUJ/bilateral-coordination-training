import pygame
import pytest

from ui.training_panels import _wrap, _wrap_line, _render_text
from ui.theme import get_font, _font_cache


@pytest.mark.parametrize('width', [1, 80, 166, 240, 600])
def test_cached_wrap_matches_original_character_wrapping(width):
    pygame.font.init()
    try:
        font = get_font(18)
        lines = ['', '左手完成：120 次', '剩餘：59.8 秒；同步容許差 0.3 秒',
                 'Tracking: low_confidence (0.75)', 'AV office ffi 123']
        expected = []
        for line in lines:
            current = ''
            for char in line:
                if current and font.size(current + char)[0] > width:
                    expected.append(current)
                    current = ''
                current += char
            expected.append(current)
        assert _wrap(lines, font, width) == expected
        assert _wrap(lines, font, width) == expected
    finally:
        _wrap_line.cache_clear()
        _render_text.cache_clear()
        _font_cache.clear()
        pygame.font.quit()
