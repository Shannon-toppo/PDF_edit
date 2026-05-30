"""フォントの「ファイルパス → ファミリ名」解決をディスクにキャッシュする。

毎回の起動で全フォントファイルを QFontDatabase.addApplicationFont で再パース
するのを避け、ファイルの mtime/size が変わらない限りキャッシュ済みのファミリ名を
再利用する。スキャン対象は OS インストール済みフォントが大半なので、解決後は
QFont(family) で（再登録なしに）プレビュー描画できる。
"""
from __future__ import annotations

import json
import os

from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QFontDatabase

_CACHE_NAME = "font_families.json"


def _cache_path() -> str:
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)
    if not base:
        base = os.path.join(os.path.expanduser("~"), ".cache", "pdf-editor")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, _CACHE_NAME)


def _load_cache(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def resolve_families(font_map: dict[str, str]) -> dict[str, str]:
    """{label: path} を受け取り {label: family} を返す（パス単位でキャッシュ）。

    - キャッシュにあり mtime/size 一致 → 再パースせずに再利用
    - 未キャッシュ/変更あり → addApplicationFont で解決してキャッシュ更新
    - ファミリが未インストールなら描画用に登録（フォールバック）
    """
    cache_file = _cache_path()
    cache = _load_cache(cache_file)          # {path: [family, mtime, size]}
    result: dict[str, str] = {}
    used_paths: set[str] = set()
    changed = False

    for label, fpath in font_map.items():
        used_paths.add(fpath)
        try:
            st = os.stat(fpath)
            mtime, size = st.st_mtime, st.st_size
        except OSError:
            mtime, size = 0.0, 0

        entry = cache.get(fpath)
        if (entry and len(entry) == 3
                and abs(entry[1] - mtime) < 1e-6 and entry[2] == size):
            # キャッシュヒット: 再パースしない。キャッシュ時点でインストール済み
            # （= QFont(family) で描画可能）なので登録も families() 確認も省く。
            family = entry[0]
        else:
            # キャッシュミス/変更あり: ここで addApplicationFont により描画用に
            # 登録もされる。未インストールのフォントでもこの経路で描画可能になる。
            fid = QFontDatabase.addApplicationFont(fpath)
            fams = QFontDatabase.applicationFontFamilies(fid)
            family = fams[0] if fams else label
            cache[fpath] = [family, mtime, size]
            changed = True

        result[label] = family

    # 既に存在しないフォントのエントリを掃除
    for stale in [p for p in cache if p not in used_paths]:
        del cache[stale]
        changed = True

    if changed:
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)
        except Exception:
            pass

    return result
