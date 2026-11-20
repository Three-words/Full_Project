"""Окно конструктора: только виджеты и их представление."""
import tkinter as tk
import customtkinter as ctk


class CustomTemplateWindow(ctk.CTkToplevel):
    BG, PANEL = '#141A23', '#202938'
    SETTINGS = (('MODULE', 'Модуль, мм'), ('QUIET', 'Тихая зона'),
                ('HEIGHT', 'Высота, мм'), ('COLUMNS', 'Столбцы PDF417'),
                ('ECC', 'ECC PDF417'), ('ERROR', 'Коррекция QR'))

    #===== Создание окна и подключение контроллера =====
    def __init__(self, parent, controller, on_preview, product_id):
        super().__init__(parent)
        self.withdraw()
        self.title('Конструктор этикеток')
        self.geometry('1360x820')
        self.minsize(1050, 650)
        self.configure(fg_color=self.BG)
        self.sections = {}
        self.tools = {}
        self.draw()
        self.editor_controller = controller.open_editor(self, on_preview, product_id)

    #===== Создание инструмента ленты =====
    def tool(self, parent, key, title, width=80):
        button = ctk.CTkButton(parent, text=title, width=width, height=32,
                               fg_color='#344256', corner_radius=5)
        button.pack(side='left', padx=2, pady=3)
        self.tools[key] = button
        return button

    #===== Создание подписанного поля =====
    def entry(self, parent, title, default='', width=105):
        row = ctk.CTkFrame(parent, fg_color='transparent')
        row.pack(fill='x', pady=3)
        ctk.CTkLabel(row, text=title, width=width, anchor='w').pack(side='left')
        widget = ctk.CTkEntry(row, height=30)
        widget.pack(side='left', fill='x', expand=True)
        widget.insert(0, str(default))
        return widget

    #===== Создание кнопки в инспекторе =====
    def action(self, parent, key, title):
        button = ctk.CTkButton(parent, text=title, height=31, fg_color='#344256')
        button.pack(fill='x', pady=4)
        self.tools[key] = button

    #===== Создание сворачиваемой секции =====
    def section(self, parent, key, title, expanded=True):
        frame = ctk.CTkFrame(parent, fg_color='#273346', corner_radius=7)
        frame.pack(fill='x', pady=5)
        head = ctk.CTkButton(frame, text=('▾  ' if expanded else '▸  ') + title,
                             anchor='w', height=35, fg_color='transparent', hover_color='#344256')
        head.pack(fill='x')
        content = ctk.CTkFrame(frame, fg_color='transparent')
        if expanded:
            content.pack(fill='x', padx=9, pady=(0, 9))
        self.sections[key] = (frame, head, content, title)
        return content

    #===== Создание ленты, холста, слоёв и свойств =====
    def draw(self):
        ribbon = ctk.CTkFrame(self, fg_color=self.PANEL, corner_radius=0)
        ribbon.pack(fill='x')
        top = ctk.CTkFrame(ribbon, fg_color='transparent')
        top.pack(fill='x', padx=8, pady=5)
        groups = (
            ('ФАЙЛ', (('new', 'Создать'), ('save', 'Сохранить'), ('preview', 'SVG-просмотр'))),
            ('ВСТАВКА', tuple((name, name) for name in ('QR', 'DataMatrix', 'PDF417', 'Code128')) +
             (('text', 'Текст'), ('line', 'Линия'))),
            ('ПРАВКА', (('remove', 'Удалить'), ('duplicate', 'Копировать'),
                        ('zoom_out', '−'), ('zoom_in', '+')))
        )
        for title, buttons in groups:
            group = ctk.CTkFrame(top, fg_color='transparent')
            group.pack(side='left', padx=6)
            ctk.CTkLabel(group, text=title, font=('Segoe UI', 10, 'bold'),
                         text_color='#8CA5C1').pack(anchor='w')
            row = ctk.CTkFrame(group, fg_color='transparent')
            row.pack()
            for key, label in buttons:
                self.tool(row, key, label, 36 if key.startswith('zoom') else 80)
        controls = ctk.CTkFrame(ribbon, fg_color='transparent')
        controls.pack(fill='x', padx=12, pady=(0, 4))
        self.snap_var = ctk.BooleanVar(value=True)
        self.snap = ctk.CTkCheckBox(controls, text='Привязки и направляющие', variable=self.snap_var)
        self.snap.pack(anchor='w')
        font_slot = ctk.CTkFrame(ribbon, fg_color='transparent', height=66)
        font_slot.pack(fill='x', padx=12, pady=(0, 5))
        font_slot.pack_propagate(False)
        ctk.CTkLabel(font_slot, text='ШРИФТ', font=('Segoe UI', 10, 'bold'),
                     text_color='#8CA5C1').pack(anchor='w')
        font_bar = ctk.CTkFrame(font_slot, fg_color='transparent')
        font_bar.pack(anchor='w')
        self.font = ctk.CTkComboBox(font_bar, width=140,
                                    values=['Gost Type A', 'Arial', 'Segoe UI', 'Times New Roman'])
        self.font.pack(side='left', padx=2)
        self.font_size = ctk.CTkEntry(font_bar, width=50)
        self.font_size.pack(side='left', padx=2)
        self.bold_var, self.italic_var = ctk.BooleanVar(), ctk.BooleanVar(value=True)
        self.bold = ctk.CTkCheckBox(font_bar, text='Ж', variable=self.bold_var, width=42)
        self.bold.pack(side='left', padx=3)
        self.italic = ctk.CTkCheckBox(font_bar, text='К', variable=self.italic_var, width=42)
        self.italic.pack(side='left', padx=3)
        self.align = ctk.CTkSegmentedButton(font_bar, values=['Слева', 'Центр', 'Справа'], width=180)
        self.align.pack(side='left', padx=5)
        self.align.set('Слева')
        self.tool(font_bar, 'font_apply', 'Применить')

        body = ctk.CTkFrame(self, fg_color='transparent')
        body.pack(fill='both', expand=True, padx=9, pady=9)
        left = ctk.CTkFrame(body, fg_color=self.PANEL, width=190)
        left.pack(side='left', fill='y', padx=(0, 8))
        left.pack_propagate(False)
        ctk.CTkLabel(left, text='Слои', font=('Segoe UI', 15, 'bold')).pack(pady=(13, 7))
        self.layers = tk.Listbox(left, bg='#151F2D', fg='#E7EDF6', selectbackground='#285DAC',
                                 borderwidth=0, highlightthickness=0, exportselection=False,
                                 activestyle='none', font=('Segoe UI', 11))
        self.layers.pack(fill='both', expand=True, padx=9, pady=(0, 9))
        middle = ctk.CTkFrame(body, fg_color='#1B2431')
        middle.pack(side='left', fill='both', expand=True)
        bar = ctk.CTkFrame(middle, fg_color='transparent')
        bar.pack(fill='x', padx=12, pady=(9, 0))
        ctk.CTkLabel(bar, text='ЛИСТ · координаты в миллиметрах',
                     font=('Segoe UI', 12, 'bold'), text_color='#AFC0D4').pack(side='left')
        self.zoom_label = ctk.CTkLabel(bar, text='100%')
        self.zoom_label.pack(side='right')
        self.canvas = tk.Canvas(middle, bg='#1B2431', highlightthickness=0, cursor='crosshair')
        self.canvas.pack(fill='both', expand=True, padx=10, pady=10)
        right = ctk.CTkScrollableFrame(body, fg_color=self.PANEL, width=320)
        right.pack(side='right', fill='y', padx=(8, 0))
        ctk.CTkLabel(right, text='Параметры листа', font=('Segoe UI', 16, 'bold')).pack(pady=(12, 5))
        self.element_title = ctk.CTkLabel(right, text='')
        self.element_title.pack()
        self.inspector(right)

    #===== Создание параметров с контекстными секциями =====
    def inspector(self, parent):
        box = self.section(parent, 'template', 'Шаблон')
        self.saved = ctk.CTkOptionMenu(box, values=['Новый шаблон'])
        self.saved.pack(fill='x', pady=4)
        self.name = self.entry(box, 'Название')
        self.width = self.entry(box, 'Ширина, мм', 70)
        self.height = self.entry(box, 'Высота, мм', 50)
        self.border_var = ctk.BooleanVar()
        self.border_check = ctk.CTkCheckBox(box, text='Обводка по контуру', variable=self.border_var)
        self.border_check.pack(anchor='w', pady=(8, 3))
        self.border_width = self.entry(box, 'Толщина, мм', 0.2)
        self.action(box, 'sheet_apply', 'Применить параметры листа')

        box = self.section(parent, 'text', 'Текст и оформление')
        ctk.CTkLabel(box, text='Подпись (Enter — новая строка)', anchor='w').pack(fill='x')
        self.text = ctk.CTkTextbox(box, height=94, wrap='word')
        self.text.pack(fill='x', pady=4)
        self.text_stroke = self.entry(box, 'Обводка букв, мм', 0)
        self.line_spacing = self.entry(box, 'Межстрочный интервал', 1.2)
        self.action(box, 'text_apply', 'Применить текст и шрифт')

        box = self.section(parent, 'text_data', 'Значение из базы данных')
        ctk.CTkLabel(box, text='После подписи добавится значение столбца.',
                     wraplength=275, text_color='#AFC0D4').pack(anchor='w')
        self.text_table, self.text_column = self.source(box)
        self.action(box, 'text_bind', 'Привязать столбец к подписи')
        self.binding_label = ctk.CTkLabel(box, text='Сейчас: без привязки')
        self.binding_label.pack(anchor='w')
        self.action(box, 'text_unbind', 'Убрать привязку')

        box = self.section(parent, 'line', 'Линия')
        self.line_stroke = self.entry(box, 'Толщина, мм', 0.3)
        self.action(box, 'line_apply', 'Применить толщину')

        box = self.section(parent, 'code', 'Состав и порядок строки')
        ctk.CTkLabel(box, text='Компоненты кодируются сверху вниз.',
                     text_color='#AFC0D4').pack(anchor='w')
        self.field_list = tk.Listbox(box, height=6, bg='#151F2D', fg='white',
                                     selectbackground='#285DAC', exportselection=False, borderwidth=0)
        self.field_list.pack(fill='x', pady=4)
        order = ctk.CTkFrame(box, fg_color='transparent')
        order.pack(fill='x')
        for key, title in (('up', '↑ Выше'), ('down', '↓ Ниже'), ('field_remove', 'Удалить')):
            self.tool(order, key, title, 86)
        ctk.CTkLabel(box, text='Идентификатор', anchor='w').pack(fill='x', pady=(10, 2))
        self.identifier = ctk.CTkOptionMenu(box, values=['Нет идентификаторов'])
        self.identifier.pack(fill='x', pady=3)
        self.source_mode = ctk.CTkSegmentedButton(box, values=['Из столбца', 'Вручную'])
        self.source_mode.pack(fill='x', pady=4)
        self.source_mode.set('Из столбца')
        self.code_source = ctk.CTkFrame(box, fg_color='transparent')
        self.code_source.pack(fill='x')
        self.table, self.column = self.source(self.code_source)
        self.literal_frame = ctk.CTkFrame(box, fg_color='transparent')
        self.literal = self.entry(self.literal_frame, 'Значение')
        self.translit_var = ctk.BooleanVar()
        self.translit = ctk.CTkCheckBox(box, text='Транслитерация через Translate', variable=self.translit_var)
        self.translit.pack(anchor='w', pady=8)
        for key, text in (('field_add', 'Добавить компонент в конец строки'),
                          ('field_replace', 'Заменить выбранный компонент'),
                          ('payload', 'Показать итоговую строку')):
            self.action(box, key, text)

        box = self.section(parent, 'code_settings', 'Параметры штрихкода', False)
        self.settings = {key: self.entry(box, title) for key, title in self.SETTINGS}
        self.action(box, 'code_apply', 'Применить параметры кода')
        box = self.section(parent, 'position', 'Расположение и размер', False)
        self.x = self.entry(box, 'X, мм', 2)
        self.y = self.entry(box, 'Y, мм', 2)
        self.w = self.entry(box, 'Ширина, мм', 22)
        self.h = self.entry(box, 'Высота, мм', 22)
        self.action(box, 'position_apply', 'Применить координаты')

    #===== Создание списка таблиц и столбцов =====
    def source(self, parent):
        table = ctk.CTkOptionMenu(parent, values=['Product'])
        table.pack(fill='x', pady=3)
        column = ctk.CTkOptionMenu(parent, values=['id'])
        column.pack(fill='x', pady=3)
        return table, column

    #===== Заполнение поля без изменения его обработчиков =====
    @staticmethod
    def set_entry(widget, value):
        widget.configure(state='normal')
        widget.delete(0, 'end')
        widget.insert(0, str(value))

    #===== Показ только нужных секций =====
    def show_sections(self, kind):
        visible = {'template', 'position'} if kind else {'template'}
        if kind:
            visible.add(kind)
        if kind == 'text':
            visible.add('text_data')
        if kind == 'code':
            visible.add('code_settings')
        for key, (frame, _, _, _) in self.sections.items():
            if key in visible:
                frame.pack(fill='x', pady=5)
            else:
                frame.pack_forget()
        for widget in (self.w, self.h):
            widget.configure(state='disabled' if kind == 'code' else 'normal')

    #===== Раскрытие раздела свойств =====
    def toggle(self, key):
        _, head, content, title = self.sections[key]
        if content.winfo_manager():
            content.pack_forget()
            head.configure(text='▸  ' + title)
        else:
            content.pack(fill='x', padx=9, pady=(0, 9))
            head.configure(text='▾  ' + title)
