"""システムフォントの列挙（埋め込み用 TTF/OTF/TTC パス解決）。"""
from __future__ import annotations

import glob
import os

_FONT_DIRS = [
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts"),
    "/usr/share/fonts",
    "/Library/Fonts",
    os.path.expanduser("~/.fonts"),
]

# 先頭に出したい日本語フォントの候補（存在すれば優先表示）
_PREFERRED = ["msgothic", "meiryo", "YuGothM", "YuGothR", "msmincho", "BIZ-UDGothicR"]


def list_fonts() -> dict[str, str]:
    """{表示名: ファイルパス} を返す。重複ファイル名は最初に見つかったものを採用。"""
    fonts: dict[str, str] = {}
    for d in _FONT_DIRS:
        if not d or not os.path.isdir(d):
            continue
        for ext in ("*.ttf", "*.otf", "*.ttc", "*.TTF", "*.OTF", "*.TTC"):
            for p in glob.glob(os.path.join(d, ext)):
                label = os.path.splitext(os.path.basename(p))[0]
                fonts.setdefault(label, p)
    # 優先フォントを前に、それ以外を名前順に
    ordered: dict[str, str] = {}
    lower_map = {k.lower(): k for k in fonts}
    for pref in _PREFERRED:
        key = lower_map.get(pref.lower())
        if key:
            ordered[key] = fonts[key]
    for k in sorted(fonts, key=str.lower):
        ordered.setdefault(k, fonts[k])
    return ordered


def default_font(fonts: dict[str, str]) -> str | None:
    """日本語が出せそうな既定フォントのラベルを返す。"""
    lower_map = {k.lower(): k for k in fonts}
    for pref in _PREFERRED:
        key = lower_map.get(pref.lower())
        if key:
            return key
    return next(iter(fonts), None)
