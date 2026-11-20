
"""Просмотр SVG-этикеток и демонстрационных шаблонов через CairoSVG."""
import os
import sys
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from tkinter import filedialog, messagebox
from xml.etree import ElementTree as ET

from Interface.SVGViewer import SVGViewer

TEMPLATES = (
    ('Общая маркировка УИИ / ФНН', 'SVG_Uniq_Marker'),
    ('Упаковка одного изделия', 'SVG_Single_Item_Package'),
    ('Упаковка нескольких изделий', 'package_many'),
    ('Руководство по эксплуатации', 'SVG_RE'),
    ('Руководство по обслуживанию', 'SVG_RO'),
    ('Паспорт изделия', 'SVG_Passport'),
    ('Транспортная этикетка', 'transport'))

#===== Подключение локальных DLL Cairo =====
if os.name == 'nt':
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
    folder = root / 'cairo'
    if not (folder / 'libcairo-2.dll').is_file():
        raise FileNotFoundError('Не найдена библиотека Cairo: ' + str(folder))
    os.environ['CAIROCFFI_DLL_DIRECTORIES'] = str(folder)
    os.environ['PATH'] = str(folder) + os.pathsep + os.environ.get('PATH', '')
    _dll_handle = os.add_dll_directory(str(folder))


#===== Преобразование SVG в изображение с кэшированием =====
@lru_cache(maxsize=8)
def preview(source):
    from PIL import Image
    import cairosvg

    _, _, w, h = map(float, ET.fromstring(source).get('viewBox').split())
    scale = min(12, 500 / max(w, h))
    png = cairosvg.svg2png(bytestring=source.encode('utf-8'),
                           output_width=max(1, round(w * scale)),
                           output_height=max(1, round(h * scale)),
                           background_color='white')
    with Image.open(BytesIO(png)) as image:
        return image.convert('RGB')


class PreviewController:
    #===== Подготовка окна просмотра или каталога =====
    def __init__(self, parent, make_label=None, custom_names=None, make_custom=None):
        self.parent, self.make_label = parent, make_label
        self.custom_names, self.make_custom = custom_names, make_custom
        self.catalog = list(TEMPLATES)
        self.view, self.image, self.zoom, self.fit = None, None, 1, False
        self.results, self.pending, self.request = Queue(), 0, 0
        self.sources = {}

    #===== Привязка событий просмотра =====
    def attach(self, view):
        self.view = view
        view.canvas.bind('<Configure>', lambda _: self.redraw())
        view.canvas.bind('<MouseWheel>', self.wheel)

    #===== Масштабирование колесом мыши =====
    def wheel(self, event):
        if self.image is not None:
            self.fit = False
            factor = 1.15 if event.delta > 0 else 1 / 1.15
            self.zoom = max(0.05, min(4000 / max(self.image.size), self.zoom * factor))
            self.redraw()
        return 'break'

    #===== Отображение изображения на холсте =====
    def redraw(self):
        if self.image is None or self.view is None or not self.view.winfo_exists():
            return
        if self.fit:
            canvas = self.view.canvas
            self.zoom = max(0.05, min(1, (canvas.winfo_width() - 40) / self.image.width,
                                      (canvas.winfo_height() - 40) / self.image.height))
        self.view.display(self.image, self.zoom)

    #===== Запуск фонового преобразования SVG =====
    def load(self, source):
        self.request += 1
        token = self.request
        self.pending += 1

        #===== Передача результата в очередь =====
        def work():
            try:
                image, error = preview(source), None
            except Exception as exc:
                image, error = None, exc
            self.results.put((token, image, error))

        Thread(target=work, daemon=True).start()
        if self.pending == 1:
            self.parent.after(40, self.poll)

    #===== Получение результата в основном потоке Tkinter =====
    def poll(self):
        try:
            while True:
                token, image, error = self.results.get_nowait()
                self.pending -= 1
                if token != self.request or not self.view or not self.view.winfo_exists():
                    continue
                if error:
                    self.view.clear('Ошибка предпросмотра')
                    messagebox.showerror('Предпросмотр SVG', str(error), parent=self.view)
                else:
                    self.image, self.fit = image, True
                    self.view.size = None
                    self.redraw()
        except Empty:
            pass
        if self.pending:
            self.parent.after(40, self.poll)

    #===== Открытие сохранённой этикетки =====
    def open(self, source, name, product_id, title, owner=None):
        if self.view is None or not self.view.winfo_exists():
            self.attach(SVGViewer(self.parent, on_save=self.save))
        self.source, self.filename = source, f'{name[4:]}_{product_id}.svg'
        self.view.heading.configure(text=title)
        self.load(source)
        self.view.transient(owner if owner and owner.winfo_exists() else self.parent.winfo_toplevel())
        self.view.deiconify()
        self.view.lift(owner if owner and owner.winfo_exists() else self.parent.winfo_toplevel())
        self.view.focus_force()

    #===== Сохранение исходного SVG =====
    def save(self):
        path = filedialog.asksaveasfilename(
            parent=self.view, initialfile=self.filename,
            defaultextension='.svg', filetypes=[('SVG', '*.svg')])
        if path:
            try:
                Path(path).write_text(self.source, encoding='utf-8')
            except OSError as error:
                messagebox.showerror('Ошибка сохранения', str(error), parent=self.view)

    #===== Открытие каталога стандартных и пользовательских шаблонов =====
    def open_catalog(self):
        if self.make_label is None:
            raise RuntimeError('Для каталога не задан генератор примеров')
        names = list(self.custom_names()) if self.custom_names else []
        self.catalog = list(TEMPLATES) + [('Пользовательский: ' + name, name) for name in names]
        titles = [title for title, _ in self.catalog]
        if self.view is None or not self.view.winfo_exists():
            self.attach(SVGViewer(self.parent, titles=titles, on_select=self.select_template))
        else:
            self.view.set_titles(titles)
        self.sources.clear()
        self.view.deiconify()
        self.view.lift()
        self.view.focus_set()
        self.select_template(0)

    #===== Показ шаблона на демонстрационных данных =====
    def select_template(self, index):
        title, key = self.catalog[index]
        try:
            if index >= len(TEMPLATES):
                if self.make_custom is None:
                    raise ValueError('Просмотр пользовательских шаблонов недоступен')
                source, _ = self.make_custom(key)
            else:
                if key not in self.sources:
                    self.sources[key] = self.make_label(key, self.parent)
                source = self.sources[key]
            _, _, w, h = map(float, ET.fromstring(source).get('viewBox').split())
            self.view.set_selection(index, title,
                                    f'Размер: {w:g} × {h:g} мм · Демонстрационные данные')
            self.load(source)
        except Exception as error:
            self.request += 1
            self.image = None
            self.view.clear('Не удалось сформировать макет')
            messagebox.showerror('Шаблоны этикеток', str(error), parent=self.view)
