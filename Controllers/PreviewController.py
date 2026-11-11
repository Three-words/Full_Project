
"""Управление просмотром готовых SVG и каталога шаблонов."""
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from tkinter import filedialog, messagebox
from xml.etree import ElementTree as ET
from GenerateQR import SVGController as svg
from GenerateQR.TemplateController import TemplateController
from Interface.SVGViewer import SVGViewer, TemplatesWindow

TEMPLATES = (
    ('Общая маркировка УИИ / ФНН', 'SVG_Uniq_Marker'),
    ('Упаковка одного изделия', 'SVG_Single_Item_Package'),
    ('Упаковка нескольких изделий', 'package_many'),
    ('Руководство по эксплуатации', 'SVG_RE'),
    ('Руководство по обслуживанию', 'SVG_RO'),
    ('Паспорт изделия', 'SVG_Passport'),
    ('Транспортная этикетка', 'transport'))

#===== Демоданные: только подстановка значений, не разметка этикеток =====
SAMPLE = dict(UII='1234567890', FNN='12345678', Serial_number='123456789',
              UYAIS='123456', Issuance_agency_code='45', Organization_code='123',
              Cargo_place_count='2', Items_per_package=1, RE_Translit='RE-1234',
              RO_Translit='RO-1234', Passport_Translit='PASS-1234')
TRANSPORT = dict(tkn='1234567890', fnn='12345678', sender='123', recipient='456',
                 recipient_address='MOSCOW', place_number=1, place_count=2,
                 items_per_package=1, gross='12,5', net='11', dimensions='40x30x20')


class PreviewController:
    #===== Общие состояния двух просмотрщиков =====
    def __init__(self, parent):
        self.parent, self.view = parent, None
        self.image, self.zoom, self.fit = None, 1, False
        self.results, self.pending, self.request = Queue(), 0, 0

    #===== Подключение масштаба и изменения размера =====
    def attach(self, view):
        self.view = view
        view.canvas.bind('<Configure>', lambda _: self.redraw())
        view.canvas.bind('<MouseWheel>', self.wheel)

    #===== Показ окна поверх главного без изменения topmost =====
    def present(self):
        self.view.deiconify()
        self.view.lift(self.parent.winfo_toplevel())
        self.view.focus_set()

    #===== Увеличение и уменьшение колесом мыши =====
    def wheel(self, event):
        if self.image is not None:
            self.fit = False
            self.zoom = max(0.05, min(4000 / max(self.image.size),
                                      self.zoom * (1.15 if event.delta > 0 else 1 / 1.15)))
            self.redraw()
        return 'break'

    #===== Перерисовка при изменении окна =====
    def redraw(self):
        if self.image is None or not self.view or not self.view.winfo_exists():
            return
        canvas = self.view.canvas
        if self.fit:
            self.zoom = min(1, (canvas.winfo_width() - 40) / self.image.width,
                            (canvas.winfo_height() - 40) / self.image.height)
        self.view.display(self.image, self.zoom)

    #===== Общая загрузка без блокировки Tkinter =====
    def load(self, source):
        self.request += 1
        token = self.request
        self.image = None
        self.view.clear('Загрузка этикетки…')

        def work():
            try:
                self.results.put((token, source, svg.preview(source), None))
            except Exception as error:
                self.results.put((token, source, None, error))

        Thread(target=work, daemon=True).start()
        self.pending += 1
        if self.pending == 1:
            self.parent.after(80, self.poll)

    #===== Приём изображений в основном потоке =====
    def poll(self):
        try:
            while True:
                token, source, image, error = self.results.get_nowait()
                self.pending -= 1
                if token != self.request or not self.view.winfo_exists():
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
            self.parent.after(80, self.poll)


class SVGPreviewController(PreviewController):
    #===== Открытие существующей SVG-этикетки =====
    def open(self, source, name, product_id, title):
        if self.view is None or not self.view.winfo_exists():
            self.attach(SVGViewer(self.parent, self.save))
        self.source, self.filename = source, f'{name[4:]}_{product_id}.svg'
        self.view.heading.configure(text=title)
        self.load(source)
        self.present()

    #===== Экспорт исходного SVG =====
    def save(self):
        path = filedialog.asksaveasfilename(parent=self.view, initialfile=self.filename,
                                           defaultextension='.svg', filetypes=[('SVG', '*.svg')])
        if path:
            try:
                Path(path).write_text(self.source, encoding='utf-8')
            except OSError as error:
                messagebox.showerror('Ошибка сохранения', str(error), parent=self.view)


class TemplatesController(PreviewController):
    #===== Подготовка каталога через существующий генератор =====
    def __init__(self, parent, renderer):
        super().__init__(parent)
        self.renderer, self.sources = renderer, {}

    #===== Открытие каталога =====
    def open(self):
        if self.view is None or not self.view.winfo_exists():
            self.attach(TemplatesWindow(self.parent, [title for title, _ in TEMPLATES], self.select))
            self.view.after_idle(lambda: self.select(0))
        self.present()

    #===== Получение этикетки без собственной разметки =====
    def get_source(self, key):
        if key not in self.sources:
            if key == 'transport':
                fields = TemplateController.transport_fields(TRANSPORT)
                self.sources[key] = self.renderer.render_transport(TRANSPORT, fields)
            elif key == 'package_many':
                self.sources[key], _ = self.renderer.render_package(
                    {**SAMPLE, 'Items_per_package': 5}, self.parent)
            else:
                if 'product' not in self.sources:
                    labels, _, errors = self.renderer.render_product(SAMPLE, self.parent)
                    self.sources.update(labels)
                    self.sources['product'] = errors
                if key not in self.sources:
                    raise ValueError('; '.join(self.sources['product']) or 'Шаблон недоступен')
        return self.sources[key]

    #===== Выбор макета и размера =====
    def select(self, index):
        title, key = TEMPLATES[index]
        try:
            source = self.get_source(key)
            _, _, w, h = map(float, ET.fromstring(source).get('viewBox').split())
            info = f'Размер: {w:g} × {h:g} мм · Демонстрационные данные'
            self.view.set_selection(index, title, info)
            self.load(source)
        except Exception as error:
            self.request += 1
            self.image = None
            self.view.clear('Не удалось сформировать макет')
            messagebox.showerror('Шаблоны этикеток', str(error), parent=self.view)
