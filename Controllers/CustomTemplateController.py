"""Управление состоянием и пользовательскими действиями конструктора этикеток."""
import copy
import math
import tkinter as tk
from tkinter import messagebox, font as tkfont
from functools import partial

from Controllers.SQL import SQL
from Controllers.CustomTemplateService import CustomTemplateService


class CustomTemplateController:
    #===== Подключение сервиса формирования этикеток =====
    def __init__(self, bd):
        self.service = CustomTemplateService(bd)

    #===== Независимое состояние для каждого открытого окна =====
    def open_editor(self, view, preview, product_id):
        editor = copy.copy(self)
        editor.attach(view, preview, product_id)
        return editor

    #===== Подключение окна и обработчиков конструктора =====
    def attach(self, view, preview, product_id):
        self.v, self.preview_callback, self.product_id = view, preview, product_id
        self.template = self.blank()
        self.selected = self.selected_field = self.drag = None
        self.zoom, self.scale, self.guides = 1.0, 1.0, []
        self.editor, self.last_click = None, None
        self.font_cache = {}
        self.dragged = False
        self.tables = SQL.get_tables(self.service.bd)
        self.identifiers_cache = self.service.identifiers()
        self.connect()
        self.new()
        self.v.after_idle(self.present)

    #===== Начальное состояние шаблона =====
    @staticmethod
    def blank():
        return dict(name='', width=70, height=50, border=0.0, elements=[])

    #===== Назначение всех команд и событий без обработчиков в интерфейсе =====
    def connect(self):
        v = self.v
        actions = {
            'new': self.new, 'save': self.save_current, 'preview': self.preview,
            'text': lambda: self.add_element('text'), 'line': lambda: self.add_element('line'),
            'remove': self.remove, 'duplicate': self.duplicate,
            'zoom_out': lambda: self.change_zoom(0.8), 'zoom_in': lambda: self.change_zoom(1.25),
            'font_apply': self.apply, 'sheet_apply': self.resize, 'text_apply': self.apply,
            'text_bind': lambda: self.text_binding(True), 'text_unbind': lambda: self.text_binding(False),
            'line_apply': self.apply, 'position_apply': self.apply,
            'up': lambda: self.shift_field(-1), 'down': lambda: self.shift_field(1),
            'field_remove': lambda: self.edit_field('remove'), 'field_add': lambda: self.edit_field('add'),
            'field_replace': lambda: self.edit_field('replace'), 'payload': self.inspect_payload,
            'code_apply': self.apply_settings
        }
        actions.update({name: lambda k=name: self.add_element(k) for name in self.service.TYPES})
        for key, button in v.tools.items():
            button.configure(command=actions[key])
        for key, (_, button, _, _) in v.sections.items():
            button.configure(command=lambda k=key: v.toggle(k))
        v.saved.configure(command=self.load)
        v.saved.configure(values=list(self.service.all_templates()) or ['Новый шаблон'])
        identifiers = [f'{code} — {desc}' for code, desc in self.identifiers_cache] or ['Нет идентификаторов']
        v.identifier.configure(values=identifiers)
        v.identifier.set(identifiers[0])
        for table, column in ((v.table, v.column), (v.text_table, v.text_column)):
            table.configure(values=self.tables or ['Product'],
                            command=lambda name, col=column: self.show_columns(name, col))
            default = 'Product' if 'Product' in self.tables else self.tables[0] if self.tables else 'Product'
            table.set(default)
            self.show_columns(default, column)
        v.source_mode.configure(command=self.source_mode)
        self.source_mode('Из столбца')
        v.border_check.configure(command=self.border)
        v.border_width.bind('<KeyRelease>', lambda _: self.border(False))
        v.layers.bind('<<ListboxSelect>>', self.choose_layer)
        v.field_list.bind('<<ListboxSelect>>', self.choose_field)
        v.canvas.bind('<Configure>', lambda _: self.redraw())
        v.canvas.bind('<Button-1>', self.pick)
        v.canvas.bind('<B1-Motion>', self.move)
        v.canvas.bind('<ButtonRelease-1>', self.release)
        v.bind('<Button-1>', self.outside_edit, add='+')
        v.bind('<F2>', self.edit_selected)
        v.bind('<Control-s>', lambda _: self.save_current())
        v.bind('<Control-n>', lambda _: self.new())
        v.bind('<Escape>', lambda _: self.deselect())
        v.bind('<Delete>', self.delete_key)
        for seq, dx, dy in (('<Left>', -1, 0), ('<Right>', 1, 0), ('<Up>', 0, -1), ('<Down>', 0, 1)):
            v.bind(seq, lambda event, x=dx, y=dy: self.nudge(event, x, y))
        for widget in (v.font, v.font_size, v.text, v.text_stroke, v.line_spacing):
            widget.bind('<KeyRelease>', self.live_text)
        for widget in (v.bold, v.italic):
            widget.configure(command=self.live_text)
        v.align.configure(command=lambda _: self.live_text())
        v.font.configure(command=lambda _: self.live_text())

    #===== Показ полностью построенного окна без мигания =====
    def present(self):
        if self.v.winfo_exists():
            self.v.deiconify()
            self.v.lift(self.v.master.winfo_toplevel())
            self.v.focus_set()

    #===== Вывод ошибок операций в интерфейс =====
    def error(self, title, exc):
        messagebox.showerror(title, str(exc), parent=self.v)

    #===== Обновление доступных столбцов =====
    def show_columns(self, table, widget):
        try:
            names = self.service.columns(table)
            widget.configure(values=names or ['Нет столбцов'])
            widget.set(names[0] if names else 'Нет столбцов')
        except Exception as exc:
            self.error('Источники данных', exc)

    #===== Выбор способа задания значения =====
    def source_mode(self, mode):
        self.v.code_source.pack_forget()
        self.v.literal_frame.pack_forget()
        (self.v.code_source if mode == 'Из столбца' else self.v.literal_frame).pack(fill='x', after=self.v.source_mode)

    #===== Обновление параметров листа =====
    def border(self, alert=True):
        try:
            value = float(self.v.border_width.get()) if self.v.border_var.get() else 0.0
            if value < 0 or (self.v.border_var.get() and not value):
                raise ValueError('Толщина обводки должна быть положительной')
            self.template['border'] = value
            self.redraw()
        except ValueError as exc:
            if alert:
                self.error('Обводка', exc)

    #===== Изменение размера листа =====
    def resize(self):
        try:
            width, height = float(self.v.width.get()), float(self.v.height.get())
            if not 10 <= width <= 500 or not 10 <= height <= 500:
                raise ValueError('Размер листа должен быть от 10 до 500 мм')
            self.template.update(width=width, height=height)
            self.border()
            self.redraw()
        except ValueError as exc:
            self.error('Размер этикетки', exc)

    #===== Создание пустого шаблона =====
    def new(self):
        self.end_edit()
        self.template = self.blank()
        for key in ('name', 'width', 'height'):
            self.v.set_entry(getattr(self.v, key), self.template[key])
        self.v.border_var.set(False)
        self.v.set_entry(self.v.border_width, 0.2)
        self.v.saved.set('Новый шаблон')
        self.deselect()

    #===== Создание и выбор элемента =====
    def add(self, element):
        self.end_edit()
        self.template['elements'].append(element)
        self.select(len(self.template['elements']) - 1)

    #===== Создание нового объекта редактора =====
    def add_element(self, kind):
        element = dict(kind=kind, x=2, y=2)
        if kind in self.service.TYPES:
            element.update(kind='code', code_type=kind, fields=[], settings={}, w=0, h=0)
        elif kind == 'text':
            element.update(text='Подпись', font='Gost Type A', font_size=14,
                           stroke=0, bold=False, italic=True, align='Слева',
                           line_spacing=1.2, field=None, w=30, h=7)
        else:
            element.update(stroke=0.3, w=30, h=0)
        self.add(element)



    #===== Получение выделенного элемента =====
    def current(self, kind=None):
        if self.selected is None or self.selected >= len(self.template['elements']):
            return None
        element = self.template['elements'][self.selected]
        return element if kind is None or element['kind'] == kind else None

    #===== Удаление элемента =====
    def remove(self):
        self.end_edit()
        if self.selected is not None:
            self.template['elements'].pop(self.selected)
            self.deselect()

    #===== Удаление клавишей вне текстовых полей =====
    def delete_key(self, event):
        if not isinstance(event.widget, (tk.Entry, tk.Text, tk.Listbox)) and not hasattr(event.widget, '_entry'):
            self.remove()

    #===== Дублирование выбранного объекта =====
    def duplicate(self):
        element = self.current()
        if element is not None:
            copy_element = copy.deepcopy(element)
            for key, size, extent in (('x', 'w', 'width'), ('y', 'h', 'height')):
                copy_element[key] = max(0, min(element[key] + 3, self.template[extent] - element[size]))
            self.add(copy_element)

    #===== Перечень слоёв с текущим выделением =====
    def layers(self):
        widget = self.v.layers
        widget.delete(0, 'end')
        for element in reversed(self.template['elements']):
            widget.insert('end', (element.get('code_type') or element.get('text') or 'Линия')[:35])
        if self.selected is not None:
            widget.selection_set(len(self.template['elements']) - self.selected - 1)

    #===== Выбор слоя из списка =====
    def choose_layer(self, event):
        values = self.v.layers.curselection()
        if values:
            index = len(self.template['elements']) - values[0] - 1
            if index != self.selected:
                self.select(index)

    #===== Отображение параметров выделенного объекта =====
    def select(self, index):
        if self.editor is not None:
            if index == self.selected:
                return
            self.end_edit()
        if index != self.selected:
            self.selected_field = None
        self.selected = index
        e, v = self.current(), self.v
        kind = e['kind']
        v.element_title.configure(text={'text': 'Текстовая подпись', 'line': 'Линия',
                                        'code': e.get('code_type', 'Штрихкод')}[kind])
        for key in ('x', 'y', 'w', 'h'):
            v.set_entry(getattr(v, key), e.get(key, ''))
        if kind == 'text':
            v.text.delete('1.0', 'end')
            v.text.insert('1.0', e.get('text', ''))
            for attr, key, default in (('font_size', 'font_size', 14),
                                       ('text_stroke', 'stroke', 0),
                                       ('line_spacing', 'line_spacing', 1.2)):
                value = e.get(key)
                value = default if value in (None, '') else value
                v.set_entry(getattr(v, attr), '{:g}'.format(float(value)))
            v.font.set(e.get('font', 'Gost Type A'))
            v.bold_var.set(e.get('bold', False))
            v.italic_var.set(e.get('italic', True))
            v.align.set(e.get('align', 'Слева'))
            field = e.get('field')
            v.binding_label.configure(text='Сейчас: {}.{}'.format(field['table'], field['column'])
                                      if field else 'Сейчас: без привязки')
            if field:
                v.text_table.set(field['table'])
                self.show_columns(field['table'], v.text_column)
                v.text_column.set(field['column'])
        if kind == 'line':
            v.set_entry(v.line_stroke, e.get('stroke', 0.3))
        self.fields_view()
        self.settings_view()
        v.show_sections(kind)
        self.layers()
        self.redraw()

    #===== Очистка выделения =====
    def deselect(self):
        self.end_edit()
        self.selected = self.selected_field = self.drag = None
        self.v.element_title.configure(text='Параметры листа')
        self.v.show_sections(None)
        self.layers()
        self.redraw()

    #===== Изменение положения и параметров объекта =====
    def apply(self):
        e = self.current()
        if e is None:
            return
        v = self.v
        try:
            changes = {key: float(getattr(v, key).get()) for key in ('x', 'y')}
            if e['kind'] != 'code':
                changes.update({key: float(getattr(v, key).get()) for key in ('w', 'h')})
            w, h = changes.get('w', e['w']), changes.get('h', e['h'])
            if min(changes['x'], changes['y'], w, h) < 0 or (e['kind'] != 'code' and not w and not h):
                raise ValueError('Неверные координаты или размеры')
            if changes['x'] + w > self.template['width'] or changes['y'] + h > self.template['height']:
                raise ValueError('Элемент выходит за пределы листа')
            if e['kind'] == 'text':
                changes.update(self.text_options())
            if e['kind'] == 'line':
                changes['stroke'] = float(v.line_stroke.get())
                if changes['stroke'] < 0:
                    raise ValueError('Толщина линии должна быть неотрицательной')
            e.update(changes)
            if e['kind'] == 'text':
                self.fit_text(e)
            self.select(self.selected)
        except ValueError as exc:
            self.error('Свойства элемента', exc)

    #===== Считывание параметров текста с понятной проверкой =====
    def text_options(self):
        v = self.v
        element = self.current('text') or {}
        numbers = {}
        for key, widget, default, label in (
                ('font_size', v.font_size, element.get('font_size', 14), 'Размер шрифта'),
                ('stroke', v.text_stroke, element.get('stroke', 0), 'Обводка букв'),
                ('line_spacing', v.line_spacing, element.get('line_spacing', 1.2), 'Межстрочный интервал')):
            raw = widget.get().strip().replace(',', '.')
            try:
                numbers[key] = float(raw) if raw else float(default)
            except ValueError:
                raise ValueError('{}: введите число'.format(label))
            if not math.isfinite(numbers[key]) or (numbers[key] <= 0 if key != 'stroke'
                                                   else numbers[key] < 0):
                raise ValueError('{}: некорректное значение'.format(label))
        return dict(text=v.text.get('1.0', 'end-1c'), font=v.font.get(),
                    bold=v.bold_var.get(), italic=v.italic_var.get(),
                    align=v.align.get(), **numbers)

    #===== Живое изменение шрифта и текста =====
    def live_text(self, event=None):
        e = self.current('text')
        if e is None:
            return
        try:
            e.update(self.text_options())
            self.fit_text(e)
            self.redraw_element()
        except ValueError:
            pass

    #===== Вычисление требуемой высоты многострочного текста =====
    def fit_text(self, e):
        font = self.canvas_font(e)
        lines = self.service.wrap_text(e.get('text', ''), e['w'] * self.scale, font.measure)
        size = float(e.get('font_size', 14)) * 25.4 / 72
        height = size * (1.15 + (len(lines) - 1) * float(e.get('line_spacing', 1.2)))
        if height <= self.template['height'] - e['y']:
            e['h'] = round(max(e['h'], height), 2)
            if e is self.current():
                self.v.set_entry(self.v.h, e['h'])

    #===== Установка или снятие привязки к столбцу =====
    def text_binding(self, enabled):
        element = self.current('text')
        if element is not None:
            element['field'] = (dict(table=self.v.text_table.get(), column=self.v.text_column.get())
                                if enabled else None)
            self.select(self.selected)


    #===== Создание компонента строки из настроек =====
    def field_input(self):
        identifier = self.v.identifier.get().split(' — ', 1)[0]
        if identifier == 'Нет идентификаторов':
            raise ValueError('В Document_Ident нет идентификаторов')
        field = dict(identifier=identifier, translit=self.v.translit_var.get())
        if self.v.source_mode.get() == 'Вручную':
            field['literal'] = self.v.literal.get()
        else:
            field.update(table=self.v.table.get(), column=self.v.column.get())
            if field['column'] in self.service.DOCUMENTS:
                field['translit'] = True
        return field

    #===== Добавление, замена или удаление компонента штрихкода =====
    def edit_field(self, mode):
        element = self.current('code')
        if element is None or (mode != 'add' and self.selected_field is None):
            return
        fields = element['fields']
        try:
            if mode == 'add':
                fields.append(self.field_input())
                self.selected_field = len(fields) - 1
            elif mode == 'replace':
                fields[self.selected_field] = self.field_input()
            else:
                fields.pop(self.selected_field)
                self.selected_field = None
            self.update_code(element)
            self.select(self.selected)
        except ValueError as exc:
            self.error('Состав кода', exc)

    #===== Отображение компонентов в исходном порядке =====
    def fields_view(self):
        widget = self.v.field_list
        widget.delete(0, 'end')
        e = self.current('code')
        if e is None:
            return
        for field in e['fields']:
            source = '«{}»'.format(field['literal']) if 'literal' in field else (
                '{}.{}'.format(field['table'], field['column']))
            widget.insert('end', '{} → {}{}'.format(field['identifier'], source,
                                                     ' [Т]' if field.get('translit') else ''))
        if self.selected_field is not None and self.selected_field < len(e['fields']):
            widget.selection_set(self.selected_field)

    #===== Выбор компонента для редактирования =====
    def choose_field(self, event):
        e = self.current('code')
        chosen = self.v.field_list.curselection()
        if e is None or not chosen:
            return
        self.selected_field = chosen[0]
        field = e['fields'][self.selected_field]
        self.v.identifier.set(next((f'{key} — {desc}' for key, desc in self.identifiers_cache
                                    if key == field['identifier']), field['identifier']))
        self.v.translit_var.set(field.get('translit', False))
        mode = 'Вручную' if 'literal' in field else 'Из столбца'
        self.v.source_mode.set(mode)
        self.source_mode(mode)
        if mode == 'Вручную':
            self.v.set_entry(self.v.literal, field['literal'])
        else:
            self.v.table.set(field['table'])
            self.show_columns(field['table'], self.v.column)
            self.v.column.set(field['column'])


    #===== Перестановка компонентов в строке =====
    def shift_field(self, offset):
        e = self.current('code')
        if e is None or self.selected_field is None:
            return
        a, b = self.selected_field, self.selected_field + offset
        if 0 <= b < len(e['fields']):
            e['fields'][a], e['fields'][b] = e['fields'][b], e['fields'][a]
            self.selected_field = b
            self.update_code(e)
            self.select(self.selected)


    #===== Вывод доступных настроек генератора =====
    def settings_view(self):
        e = self.current('code')
        if e is None:
            return
        allowed = self.service.SETTINGS[e['code_type']]
        generator = self.service.generators[e['code_type']]
        for key, widget in self.v.settings.items():
            if key in allowed:
                widget.master.pack(fill='x', pady=3)
                self.v.set_entry(widget, e.get('settings', {}).get(key, getattr(generator, key, '')))
            else:
                widget.master.pack_forget()

    #===== Применение настроек и пересчёт размеров штрихкода =====
    def apply_settings(self):
        e = self.current('code')
        if e is None:
            return
        settings = {key: widget.get().strip() for key, widget in self.v.settings.items()
                    if key in self.service.SETTINGS[e['code_type']]}
        old = e.get('settings', {})
        e['settings'] = settings
        try:
            self.service.generator(e)
            self.update_code(e)
            self.select(self.selected)
        except (ValueError, TypeError) as exc:
            e['settings'] = old
            self.error('Настройки кода', exc)

    #===== Просмотр упакованной строки с управляющими символами =====
    def inspect_payload(self):
        e = self.current('code')
        if e is None or self.product_id is None:
            return
        try:
            raw = self.service.payload(e, self.product_id)
            visible = (raw.decode('utf-8', 'replace').replace('\x1d', '[GS]')
                       .replace('\x1e', '[RS]').replace('\x04', '[EOT]'))
            messagebox.showinfo('Строка для генерации', visible, parent=self.v)
        except Exception as exc:
            self.error('Строка для генерации', exc)

    #===== Расчёт естественного размера штрихкода =====
    def update_code(self, e):
        if not e['fields']:
            e['w'] = e['h'] = 0
        elif self.product_id is not None:
            try:
                self.service.size_code(e, self.product_id)
            except Exception as exc:
                self.error('Размер штрихкода', exc)

    #===== Масштаб холста и положение этикетки =====
    def geometry(self):
        width, height = self.template['width'], self.template['height']
        canvas = self.v.canvas
        scale = max(0.1, min((canvas.winfo_width() - 70) / width,
                              (canvas.winfo_height() - 70) / height, 9) * self.zoom)
        return scale, (canvas.winfo_width() - width * scale) / 2, (canvas.winfo_height() - height * scale) / 2

    #===== Создание и повторное использование шрифтов холста =====
    def canvas_font(self, e):
        size = max(1, round(float(e.get('font_size', 14))*25.4/72*self.scale))
        key = (e.get('font', 'Gost Type A'), size, bool(e.get('bold')), bool(e.get('italic', True)))
        if key not in self.font_cache:
            self.font_cache[key] = tkfont.Font(
                root=self.v, family=key[0], size=-size,
                weight='bold' if key[2] else 'normal',
                slant='italic' if key[3] else 'roman')
        return self.font_cache[key]

    #===== Отрисовка одного элемента с тегами Canvas =====
    def draw_element(self, index):
        c, e = self.v.canvas, self.template['elements'][index]
        s, ox, oy = self.geometry()
        x, y, w, h = (float(e[k]) for k in ('x', 'y', 'w', 'h'))
        x1, y1 = ox+x*s, oy+y*s
        x2 = x1+(w or (22 if e['kind'] == 'code' else 0))*s
        y2 = y1+(h or (18 if e['kind'] == 'code' else 0))*s
        tag = 'object:{}'.format(index)
        common = ('element', tag)
        if e['kind'] == 'line':
            c.create_line(x1, y1, x2, y2, fill='#111827', capstyle=tk.BUTT,
                          width=max(1, e.get('stroke', 0.3)*s), tags=common)
        else:
            c.create_rectangle(x1, y1, x2, y2,
                               fill='#E7EFF9' if e['kind'] == 'code' else 'white',
                               outline='#64748b', tags=common)
            if e['kind'] == 'text':
                font = self.canvas_font(e)
                align = e.get('align', 'Слева')
                px = {'Слева': x1, 'Центр': (x1+x2)/2, 'Справа': x2}.get(align, x1)
                anchor = {'Слева': 'nw', 'Центр': 'n', 'Справа': 'ne'}.get(align, 'nw')
                lines = self.service.wrap_text(e.get('text', ''), w*s, font.measure)
                line_h = font.metrics('linespace')*float(e.get('line_spacing', 1.2))
                for number, line in enumerate(lines):
                    c.create_text(px, y1+number*line_h, text=line, anchor=anchor,
                                  font=font, fill='black', tags=common)
            else:
                title = e['code_type'] + (' · добавьте поле' if not e['fields'] else '')
                c.create_text(x1+4, y1+4, text=title, anchor='nw', fill='#111827',
                              font=('Segoe UI', 11), width=max(10, x2-x1-8), tags=common)
        if index != self.selected:
            return
        if e['kind'] == 'line':
            points = (('start', x1, y1), ('end', x2, y2))
        else:
            c.create_rectangle(x1, y1, x2, y2, outline='#2563EB',
                               dash=(4, 2), width=2, tags=common)
            points = (('size', x2, y2),) if e['kind'] == 'text' else ()
        for name, hx, hy in points:
            c.create_rectangle(hx-6, hy-6, hx+6, hy+6, fill='#2563EB',
                               outline='white', tags=common+('handle', 'handle:'+name))

    #===== Обновление направляющих независимо от объектов =====
    def draw_guides(self):
        c = self.v.canvas
        c.delete('guides')
        s, ox, oy = self.geometry()
        for axis, coordinate in self.guides:
            coords = (coordinate, oy, coordinate, oy+self.template['height']*s) if axis == 'x' else (
                ox, coordinate, ox+self.template['width']*s, coordinate)
            c.create_line(*coords, fill='#2F82EF', dash=(4, 3), tags=('guides',))

    #===== Обновление только изменённого элемента =====
    def redraw_element(self, index=None):
        if self.editor is not None:
            return
        if index is None:
            index = self.selected
        if index is not None:
            self.v.canvas.delete('object:{}'.format(index))
            self.draw_element(index)
        self.draw_guides()

    #===== Отрисовка листа после изменения геометрии или состава =====
    def redraw(self):
        if self.editor is not None:
            return
        c = self.v.canvas
        c.delete('all')
        self.font_cache.clear()
        self.scale, ox, oy = self.geometry()
        width, height = self.template['width'], self.template['height']
        s = self.scale
        c.create_rectangle(ox, oy, ox+width*s, oy+height*s,
                           fill='white', outline='#8292A5', width=2, tags=('sheet',))
        for x in range(0, int(width)+1, 5):
            c.create_line(ox+x*s, oy, ox+x*s, oy+height*s, fill='#EEF1F6', tags=('sheet',))
        for y in range(0, int(height)+1, 5):
            c.create_line(ox, oy+y*s, ox+width*s, oy+y*s, fill='#EEF1F6', tags=('sheet',))
        border = float(self.template.get('border', 0))
        if border > 0:
            inset = border*s/2
            c.create_rectangle(ox+inset, oy+inset, ox+width*s-inset, oy+height*s-inset,
                               outline='black', width=max(1, border*s), tags=('sheet',))
        for index in range(len(self.template['elements'])):
            self.draw_element(index)
        self.draw_guides()
        self.v.zoom_label.configure(text=f'{self.zoom*100:.0f}% · {width:g} × {height:g} мм')

    #===== Получение координат указателя в миллиметрах =====
    def point(self, event):
        s, ox, oy = self.geometry()
        return (event.x-ox)/s, (event.y-oy)/s

    #===== Поиск элемента и ближайшего маркера по тегам Canvas =====
    def hit(self, mx, my):
        s, ox, oy = self.geometry()
        px, py = ox+mx*s, oy+my*s
        c = self.v.canvas
        items = c.find_overlapping(px-6, py-6, px+6, py+6)
        handles = []
        for item in items:
            tags = c.gettags(item)
            if 'handle' in tags:
                coords = c.coords(item)
                distance = (px-(coords[0]+coords[2])/2)**2+(py-(coords[1]+coords[3])/2)**2
                index = next(int(t[7:]) for t in tags if t.startswith('object:'))
                name = next(t[7:] for t in tags if t.startswith('handle:'))
                handles.append((distance, index, name))
        if handles:
            _, index, name = min(handles)
            return index, name
        for item in reversed(items):
            tags = c.gettags(item)
            if 'element' not in tags:
                continue
            index = next(int(t[7:]) for t in tags if t.startswith('object:'))
            e = self.template['elements'][index]
            if e['kind'] != 'line':
                w = e['w'] or (22 if e['kind'] == 'code' else 0)
                h = e['h'] or (18 if e['kind'] == 'code' else 0)
                if not (e['x'] <= mx <= e['x']+w and e['y'] <= my <= e['y']+h):
                    continue
            return index, 'move'
        return None, None

    #===== Выделение объекта для перемещения =====
    def pick(self, event):
        self.end_edit()
        self.dragged = False
        mx, my = self.point(event)
        index, mode = self.hit(mx, my)
        if index is None:
            self.deselect()
            return
        if index != self.selected:
            self.select(index)
        e = self.current()
        self.drag = (mode, mx-e['x'], my-e['y']) if mode == 'move' else (mode, mx, my, e['w'], e['h'])

    #===== Привязка положения к центрам и краям объектов =====
    def snap(self, e, x, y):
        self.guides = []
        if not self.v.snap_var.get():
            return x, y
        width, height = self.template['width'], self.template['height']
        targets = ([0, width/2, width], [0, height/2, height])
        for other in self.template['elements']:
            if other is not e:
                for axis, base, extent in ((0, 'x', 'w'), (1, 'y', 'h')):
                    a, b = other[base], other[extent]
                    targets[axis].extend((a, a+b/2, a+b))
        _, ox, oy = self.geometry()
        result = [x, y]
        for axis, size, origin in ((0, e['w'], ox), (1, e['h'], oy)):
            choices = [(abs(result[axis]+shift-target), target, shift)
                       for target in targets[axis] for shift in (0, size/2, size)]
            distance, target, shift = min(choices)
            if distance <= 5/self.scale:
                result[axis] = target-shift
                self.guides.append(('x' if axis == 0 else 'y', origin+target*self.scale))
        return result

    #===== Перемещение и изменение размеров мышью =====
    def move(self, event):
        e = self.current()
        if e is None or self.drag is None:
            return
        self.dragged = True
        mx, my = self.point(event)
        mode = self.drag[0]
        previous = (e['x'], e['y'])
        if e['kind'] == 'line' and mode in ('start', 'end'):
            x1, y1 = e['x'], e['y']
            x2, y2 = x1+e['w'], y1+e['h']
            ax, ay = (x2, y2) if mode == 'start' else (x1, y1)
            mx, my = max(0, min(self.template['width'], mx)), max(0, min(self.template['height'], my))
            if event.state & 0x0001:
                if abs(mx-ax) >= abs(my-ay):
                    my = ay
                else:
                    mx = ax
            if mode == 'start':
                x1, y1 = min(mx, x2), min(my, y2)
            else:
                x2, y2 = max(mx, x1), max(my, y1)
            e.update(x=round(x1, 2), y=round(y1, 2), w=round(x2-x1, 2), h=round(y2-y1, 2))
            self.guides = []
        elif mode == 'move':
            x, y = self.snap(e, mx-self.drag[1], my-self.drag[2])
            e['x'] = round(max(0, min(self.template['width']-e['w'], x)), 2)
            e['y'] = round(max(0, min(self.template['height']-e['h'], y)), 2)
        else:
            self.guides = []
            e['w'] = round(max(0.1, min(self.template['width']-e['x'],
                                        self.drag[3]+mx-self.drag[1])), 2)
            e['h'] = round(max(0.1, min(self.template['height']-e['y'],
                                        self.drag[4]+my-self.drag[2])), 2)
        for key in ('x', 'y', 'w', 'h'):
            self.v.set_entry(getattr(self.v, key), e[key])
        if mode == 'move':
            self.v.canvas.move('object:{}'.format(self.selected),
                               (e['x']-previous[0])*self.scale, (e['y']-previous[1])*self.scale)
            self.draw_guides()
        else:
            self.redraw_element()

    #===== Завершение жеста и вход в редактирование текста двойным щелчком =====
    def release(self, event):
        e = self.current()
        clicked = e is not None and e['kind'] == 'text' and not self.dragged and self.drag is not None
        if clicked:
            last = self.last_click
            if last and last[0] == self.selected and 0 <= event.time-last[1] <= 500 and (
                    abs(event.x-last[2]) <= 6 and abs(event.y-last[3]) <= 6):
                self.last_click = None
                index = self.selected
                self.v.after_idle(lambda i=index: self.start_edit(i))
            else:
                self.last_click = (self.selected, event.time, event.x, event.y)
        else:
            self.last_click = None
        if e is not None and self.drag and self.drag[0] == 'size' and e['kind'] == 'text':
            self.fit_text(e)
        self.drag, self.guides = None, []
        self.draw_guides()

    #===== Встраивание текстового редактора поверх надписи =====
    def start_edit(self, index):
        if index >= len(self.template['elements']) or self.template['elements'][index]['kind'] != 'text':
            return
        self.end_edit()
        self.select(index)
        e = self.current()
        self.scale, ox, oy = self.geometry()
        self.editor = tk.Text(self.v.canvas, wrap='word', undo=True, borderwidth=1, relief='solid',
                              bg='white', fg='black', insertbackground='black',
                              highlightthickness=2, highlightbackground='#2563EB')
        self.editor.configure(font=self.canvas_font(e))
        self.editor.insert('1.0', e.get('text', ''))
        self.editor.place(x=ox+e['x']*self.scale, y=oy+e['y']*self.scale,
                          width=max(12, e['w']*self.scale), height=max(55, e['h']*self.scale))
        self.editor.lift()
        self.editor.bind('<KeyRelease>', self.changed_edit)
        self.editor.bind('<Control-Return>', lambda _: (self.end_edit(), 'break')[1])
        self.editor.focus_set()

    #===== Завершение редактирования при щелчке за пределами надписи =====
    def outside_edit(self, event):
        if self.editor is not None and event.widget is not self.editor:
            self.end_edit()

    #===== Открытие выделенной надписи по F2 =====
    def edit_selected(self, event=None):
        if self.current('text') is not None:
            self.start_edit(self.selected)
            return 'break'

    #===== Синхронизация введённого текста и автоподбор высоты =====
    def changed_edit(self, event=None):
        e = self.current('text')
        if self.editor is not None and e is not None:
            e['text'] = self.editor.get('1.0', 'end-1c')
            self.fit_text(e)
            self.editor.place_configure(height=max(55, e['h']*self.scale))
            self.v.text.delete('1.0', 'end')
            self.v.text.insert('1.0', e['text'])
            self.layers()

    #===== Закрытие встроенного редактора =====
    def end_edit(self):
        if self.editor is not None:
            editor = self.editor
            self.changed_edit()
            self.editor = None
            editor.destroy()
            self.redraw()

    #===== Сдвиг элемента стрелками =====
    def nudge(self, event, dx, dy):
        if self.current() is None or isinstance(event.widget, (tk.Entry, tk.Text)):
            return
        e = self.current()
        step = 0.1 if event.state & 0x0001 else 1
        for key, delta, limit in (('x', dx, 'width'), ('y', dy, 'height')):
            extent = 'w' if key == 'x' else 'h'
            e[key] = round(max(0, min(self.template[limit]-e[extent], e[key]+delta*step)), 2)
        self.select(self.selected)
        return 'break'

    #===== Изменение масштаба просмотра =====
    def change_zoom(self, factor):
        self.zoom = max(0.3, min(3, self.zoom*factor))
        self.redraw()

    #===== Чтение актуальных параметров листа =====
    def sheet_values(self):
        self.template.update(name=self.v.name.get().strip(),
                             width=float(self.v.width.get()), height=float(self.v.height.get()))
        self.border()

    #===== Сохранение шаблона по действующей схеме JSON =====
    def save_current(self):
        self.end_edit()
        try:
            self.sheet_values()
            self.service.save(self.template)
            self.v.saved.configure(values=list(self.service.all_templates()))
            self.v.saved.set(self.template['name'])
            messagebox.showinfo('Конструктор', 'Шаблон сохранён', parent=self.v)
        except Exception as exc:
            self.error('Сохранение', exc)

    #===== Восстановление сохранённого шаблона =====
    def load(self, name):
        self.end_edit()
        template = self.service.all_templates().get(name)
        if template is None:
            return
        self.template = copy.deepcopy(template)
        self.v.border_var.set(bool(template.get('border', 0)))
        self.v.set_entry(self.v.border_width, template.get('border') or 0.2)
        for key in ('name', 'width', 'height'):
            self.v.set_entry(getattr(self.v, key), template[key])
        for e in template['elements']:
            if e['kind'] == 'code' and e.get('fields'):
                self.update_code(e)
        self.deselect()

    #===== SVG-просмотр без второго механизма предпросмотра =====
    def preview(self):
        self.end_edit()
        try:
            self.sheet_values()
            source = self.service.render(copy.deepcopy(self.template), self.product_id)
            self.preview_callback(source, 'SVG_Custom',
                                  self.product_id if self.product_id is not None else 'sample',
                                  self.template['name'] or 'Пользовательская этикетка', owner=self.v)
        except Exception as exc:
            self.error('Предпросмотр', exc)
