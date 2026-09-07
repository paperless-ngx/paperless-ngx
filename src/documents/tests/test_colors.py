import re
from unittest import mock

from documents.colors import random_color


class TestRandomColor:
    def test_format_is_hex(self) -> None:
        """
        GIVEN:
            - The server-side random_color helper
        WHEN:
            - It is called
        THEN:
            - The result is a lowercase #rrggbb hex string
        """
        color = random_color()
        assert re.fullmatch(r"#[0-9a-f]{6}", color)

    def test_does_not_use_model_default(self) -> None:
        """
        GIVEN:
            - Controlled random values that cannot produce the model default
        WHEN:
            - random_color is called
        THEN:
            - The result is not the Tag model default #a6cee3
        """
        with mock.patch("documents.colors.random.random", side_effect=[0.0, 0.0]):
            assert random_color() != "#a6cee3"

    def test_matches_frontend_hsl_mapping(self) -> None:
        """
        GIVEN:
            - Fixed hue and lightness inputs matching the frontend algorithm
        WHEN:
            - random_color is called
        THEN:
            - The hex matches the expected HSL→RGB conversion
              (h=0, s=0.6, l=0.4 → #a32828)
        """
        with mock.patch("documents.colors.random.random", side_effect=[0.0, 0.0]):
            assert random_color() == "#a32828"
