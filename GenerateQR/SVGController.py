
"""SVG: генерация, экспорт и быстрый предпросмотр."""
import re
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from html import escape
from pathlib import Path
from tkinter import font as tkfont
from typing import Optional
from xml.etree import ElementTree as ET

#===== Настройки этикеток =====
FONT, FONT_SLANT, FONT_WEIGHT = 'Gost Type A', 'italic', 'normal'
FONT_PT, FONT_LARGE_PT, FONT_SMALL_PT, FONT_DOCUMENT_PT = 14, 18, 12, 9
TEXT_STROKE, BORDER_STROKE, GRID_STROKE = 0.07, 0.2, 0.5
BORDER_INSET, QR_TEXT_GAP, MIN_TEXT_SCALE = 0.1, 0.1, 0.6
PT, SCALE, PREVIEW_PX_PER_MM = 25.4 / 72, 10, 12


@dataclass
class MatrixCode:
    size: int
    cells: list
    version: Optional[int] = None
    mask: Optional[int] = None
    module: float = 0.381
    quiet: int = 4

    @property
    def full_mm(self):
        return (self.size + 2 * self.quiet) * self.module

    @property
    def svg(self):
        return document(self.full_mm, self.full_mm, symbol(self))


#===== Генерация SVG =====
def document(w, h, parts):
    body = '\n'.join(parts) if isinstance(parts, list) else parts
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:g}mm" '
            f'height="{h:g}mm" viewBox="0 0 {w:g} {h:g}">\n{body}\n</svg>\n')


def symbol(code, x=0, y=0):
    m, q = code.module, code.quiet
    parts = [f'<rect x="{x:.6f}" y="{y:.6f}" width="{code.full_mm:g}" '
             f'height="{code.full_mm:g}" fill="white"/>']
    parts.extend(f'<rect x="{x + (cx + q) * m:.6f}" y="{y + (cy + q) * m:.6f}" '
                 f'width="{m}" height="{m}" fill="black"/>' for cx, cy in code.cells)
    return '\n'.join(parts)


def border(w, h):
    d = BORDER_INSET
    return [f'<rect width="{w:g}" height="{h:g}" fill="white"/>',
            f'<rect x="{d:g}" y="{d:g}" width="{w - 2*d:g}" height="{h - 2*d:g}" '
            f'fill="none" stroke="black" stroke-width="{BORDER_STROKE:g}"/>']


def font(mm, master=None):
    return tkfont.Font(root=master, family=FONT, size=-round(mm * SCALE),
                       slant=FONT_SLANT, weight=FONT_WEIGHT)


def text(value, x, y, mm, anchor='middle', max_width=None, master=None):
    content = (f'<text x="{x:.6f}" y="{y:.6f}" text-anchor="{anchor}" '
               f'font-family="{escape(FONT)}" font-size="{mm:g}" '
               f'font-style="{FONT_SLANT}" font-weight="{FONT_WEIGHT}" fill="black" '
               f'stroke="black" stroke-width="{TEXT_STROKE:g}" stroke-linejoin="round" '
               f'paint-order="stroke fill">{escape(str(value))}</text>')
    if max_width is None:
        return content
    measured = font(mm, master).measure(str(value))
    if measured <= max_width * SCALE:
        return content
    ratio = max_width * SCALE / measured
    if ratio < MIN_TEXT_SCALE:
        raise ValueError('Подпись не помещается на этикетке')
    return (f'<g transform="translate({x:g} 0) scale({ratio:.6f} 1) '
            f'translate({-x:g} 0)">{content}</g>')


def embed(source, x, y, width, height, quiet_x=0, quiet_y=0):
    match = re.search(r'<svg[^>]*viewBox="0 0 ([\d.]+) ([\d.]+)"[^>]*>(.*?)</svg>', source, re.S)
    if not match:
        raise ValueError('Некорректный SVG штрихкода')
    sw, sh, body = match.groups()
    return (f'<svg x="{x:g}" y="{y:g}" width="{width:g}" height="{height:g}" '
            f'viewBox="{quiet_x:g} {quiet_y:g} '
            f'{float(sw) - 2 * quiet_x:g} {float(sh) - 2 * quiet_y:g}" '
            f'preserveAspectRatio="none">{body}</svg>')


#===== Экспорт оригинальных SVG =====
def export(labels, folder, product_id):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    paths = [folder / f'{name[4:]}_{product_id}.svg' for name in labels]
    for path, source in zip(paths, labels.values()):
        path.write_text(source, encoding='utf-8')
    return paths


#===== Поиск браузера для точного SVG-предпросмотра =====
@lru_cache(maxsize=1)
def preview_browser():
    names = ('msedge.exe', 'chrome.exe', 'chromium.exe')
    folders = [os.environ.get(key, '') for key in ('PROGRAMFILES(X86)', 'PROGRAMFILES', 'LOCALAPPDATA')]
    paths = [Path(folder) / subdir / exe for folder in folders if folder
             for subdir, exe in (('Microsoft/Edge/Application', 'msedge.exe'),
                                 ('Google/Chrome/Application', 'chrome.exe'),
                                 ('Chromium/Application', 'chrome.exe'))]
    return next((str(path) for path in paths if path.is_file()), None) or next(
        (shutil.which(name) for name in names if shutil.which(name)), None)


#===== Рендеринг SVG в движке Edge/Chromium =====
@lru_cache(maxsize=8)
def preview(source):
    from PIL import Image

    browser = preview_browser()
    if not browser:
        raise RuntimeError('Для точного предпросмотра нужен Microsoft Edge или Google Chrome')

    root = ET.fromstring(source)
    _, _, width, height = map(float, root.get('viewBox').split())
    scale = min(PREVIEW_PX_PER_MM, 500 / max(width, height))
    w, h = max(1, round(width * scale)), max(1, round(height * scale))

    with tempfile.TemporaryDirectory(prefix='code_studio_svg_') as folder:
        folder = Path(folder)
        (folder / 'label.svg').write_text(source, encoding='utf-8')
        (folder / 'preview.html').write_text(
            '<html><body style="margin:0;background:white">'
            f'<img src="label.svg" style="display:block;width:{w}px;height:{h}px">'
            '</body></html>', encoding='utf-8')
        screenshot = folder / 'preview.png'
        args = [browser, '--headless=new', '--hide-scrollbars', '--no-first-run',
                '--no-default-browser-check', '--disable-extensions',
                '--disable-background-networking',
                '--force-device-scale-factor=1', f'--window-size={w + 100},{h + 160}',
                f'--user-data-dir={folder / "browser"}', f'--screenshot={screenshot}',
                (folder / 'preview.html').as_uri()]
        try:
            subprocess.run(args, check=True, timeout=15, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            with Image.open(screenshot) as image:
                if image.width < w or image.height < h:
                    raise RuntimeError('Браузер создал слишком маленький снимок')
                return image.crop((0, 0, w, h)).convert('RGB')
        except (OSError, subprocess.SubprocessError) as error:
            raise RuntimeError(f'Не удалось отобразить SVG через браузер: {error}') from error
