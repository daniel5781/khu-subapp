"""설치된 한글 폰트를 골라 PNG에서도 산업 이름이 표시되게 한다."""

from functools import lru_cache
from matplotlib.font_manager import FontProperties, fontManager


@lru_cache(maxsize=1)
def korean_font():
    available = {font.name for font in fontManager.ttflist}
    for name in (
        "AppleGothic",
        "Malgun Gothic",
        "NanumGothic",
        "Nanum Gothic",
        "Noto Sans CJK KR",
        "Noto Sans KR",
        "Arial Unicode MS",
    ):
        if name in available:
            return FontProperties(family=name)
    return None
