
"""Низкоуровневые SVG-примитивы, размеры шрифтов и экспорт файлов."""
import re
from dataclasses import dataclass
from html import escape
from pathlib import Path
from tkinter import font as tkfont
from typing import Optional

#===== Настройки этикеток =====
FONT, FONT_SLANT, FONT_WEIGHT = 'Gost Type A', 'italic', 'normal'
FONT_PT, FONT_LARGE_PT, FONT_SMALL_PT, FONT_DOCUMENT_PT = 14, 18, 12, 9
TEXT_STROKE, BORDER_STROKE, GRID_STROKE = 0.07, 0.2, 0.5
BORDER_INSET, QR_TEXT_GAP, MIN_TEXT_SCALE = 0.1, 0.1, 0.6
PT, SCALE = 25.4 / 72, 10


@dataclass
class MatrixCode:
    size: int
    cells: list
    version: Optional[int] = None
    mask: Optional[int] = None
    module: float = 0.381
    quiet: int = 4

    #===== Размер матрицы с тихой зоной =====
    @property
    def full_mm(self):
        return (self.size + 2 * self.quiet) * self.module

    #===== Представление матрицы SVG-документом =====
    @property
    def svg(self):
        return document(self.full_mm, self.full_mm, symbol(self))


#===== Сборка SVG-документа =====
def document(w, h, parts):
    body = '\n'.join(parts) if isinstance(parts, list) else parts
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:g}mm" '
            f'height="{h:g}mm" viewBox="0 0 {w:g} {h:g}">\n{body}\n</svg>\n')


#===== Компактное представление модулей матрицы одним SVG-путём =====
def symbol(code, x=0, y=0):
    m, q = code.module, code.quiet
    cells = ' '.join(
        f'M{x + (cx + q) * m:.6f} {y + (cy + q) * m:.6f}h{m:g}v{m:g}h{-m:g}z'
        for cx, cy in code.cells)
    return (f'<rect x="{x:.6f}" y="{y:.6f}" width="{code.full_mm:g}" '
            f'height="{code.full_mm:g}" fill="white"/>'
            f'<path d="{cells}" fill="black"/>')


#===== Рамка и фон этикетки =====
def border(w, h):
    d = BORDER_INSET
    return [f'<rect width="{w:g}" height="{h:g}" fill="white"/>',
            f'<rect x="{d:g}" y="{d:g}" width="{w - 2*d:g}" height="{h - 2*d:g}" '
            f'fill="none" stroke="black" stroke-width="{BORDER_STROKE:g}"/>']


#===== Шрифт для измерения текста =====
def font(mm, master=None):
    return tkfont.Font(root=master, family=FONT, size=-round(mm * SCALE),
                       slant=FONT_SLANT, weight=FONT_WEIGHT)


#===== SVG-надпись с проверкой ширины =====
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


#===== Встраивание другого SVG в область =====
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
