
"""Левая панель управления и выпадающие списки."""
from pathlib import Path
import tkinter as tk
import customtkinter as ctk
from PIL import Image


class ControlPanelUser:
    SECTIONS = (
        ('ИЗДЕЛИЯ', (('products', 'Изделия'), ('categories', 'Категории'),
                     ('warehouse', 'Склады'))),
        ('СКАНИРОВАНИЕ', (('scanner', 'Сканер'), ('history', 'История'))),
        ('ГЕНЕРАЦИЯ КОДОВ', (('generate', 'Генерация кодов'),
                            ('templates', 'Шаблоны'), ('new_template', 'Новый шаблон'))),
        ('СИСТЕМА', (('users', 'Пользователи'), ('settings', 'Настройки'),
                     ('log', 'Журнал изменений'))))

    def __init__(self, parent, status_var):
        self.parent, self.status_var = parent, status_var
        self.buttons, self.popup, self.popup_button = {}, None, None
        self.products_count = ctk.IntVar(value=0)
        self.scanner_status_label = None
        names = [name for _, section in self.SECTIONS for name, _ in section]
        self.icons = self.load_icons(names)

    @staticmethod
    def load_icons(names):
        folder = Path(__file__).resolve().parent.parent / 'icons'
        return {name: ctk.CTkImage(Image.open(folder / f'{name}.png'), size=(22, 22))
                for name in names if (folder / f'{name}.png').is_file()}

    @staticmethod
    def header(parent, title, size=12):
        ctk.CTkLabel(parent, text=title, font=('Segoe UI', size, 'bold'),
                     text_color='#7F8EA3' if size == 12 else '#E7EDF6').pack(
            anchor='w', padx=14, pady=(11, 4))

    def draw_button(self, parent, name, title, state='normal'):
        row = ctk.CTkFrame(parent, fg_color='transparent')
        row.pack(fill='x', padx=7, pady=1)
        button = ctk.CTkButton(row, text=title, image=self.icons.get(name),
                               compound='left', anchor='w', height=38,
                               fg_color='transparent', hover_color='#2A3546',
                               text_color='#E7EDF6', corner_radius=6, state=state)
        button.pack(side='left', fill='x', expand=True)
        self.buttons[name] = button
        if name == 'products':
            ctk.CTkLabel(row, textvariable=self.products_count, width=28,
                         fg_color='#344256', corner_radius=11).pack(side='right', padx=4)
        if name == 'scanner':
            self.scanner_status_label = ctk.CTkLabel(
                row, text='●', width=28, text_color='#EF6464', font=('Segoe UI', 18))
            self.scanner_status_label.pack(side='right', padx=4)

    def draw_sections(self, parent):
        self.header(parent, 'Панель управления', 18)
        for title, buttons in self.SECTIONS:
            self.header(parent, title)
            for name, label in buttons:
                self.draw_button(parent, name, label)

    def draw_status(self, parent):
        self.status_label = ctk.CTkLabel(parent, textvariable=self.status_var,
                                         text_color='#EF6464', anchor='w')
        self.status_label.pack(side='bottom', fill='x', padx=14, pady=(10, 18))

    def draw(self):
        self.draw_sections(self.parent)
        self.draw_status(self.parent)

    def close_popup(self):
        if self.popup and self.popup.winfo_exists():
            self.popup.destroy()
        self.popup = self.popup_button = None

    def close_on_outside(self, event):
        if not self.popup or not self.popup.winfo_exists():
            return
        for widget in (self.popup, self.popup_button):
            x, y = widget.winfo_rootx(), widget.winfo_rooty()
            if x <= event.x_root < x + widget.winfo_width() and y <= event.y_root < y + widget.winfo_height():
                return
        self.close_popup()

    def show_popup(self, button, choices, on_select, below=False):
        same = self.popup and self.popup.winfo_exists() and self.popup_button == button
        self.close_popup()
        if same:
            return

        count = max(1, len(choices))
        popup = ctk.CTkFrame(button.winfo_toplevel(), width=max(235, button.winfo_width()),
                             height=16 + 36 * min(count, 8), bg_color='#202938',
                             fg_color='#202938', corner_radius=10,
                             border_width=1, border_color='#52647C')
        self.popup, self.popup_button = popup, button
        popup.pack_propagate(False)
        popup.place(in_=button, relx=0 if below else 1, rely=1 if below else 0,
                    y=4 if below else 0, anchor='nw')
        popup.lift()

        frame = (ctk.CTkScrollableFrame(popup, fg_color='transparent', corner_radius=0,
                                        scrollbar_button_color='#465C76',
                                        scrollbar_button_hover_color='#6885A7')
                 if count > 8 else ctk.CTkFrame(popup, fg_color='transparent', corner_radius=0))
        frame.pack(fill='both', expand=True, padx=8, pady=8)

        for value, title in choices:
            ctk.CTkButton(frame, text=title, height=32, anchor='w', corner_radius=6,
                          font=('Segoe UI', 13), fg_color='transparent', hover_color='#315781',
                          command=lambda v=value: (self.close_popup(), on_select(v))).pack(
                fill='x', pady=2)
        if not choices:
            ctk.CTkLabel(frame, text='Нет данных', height=32).pack(fill='x', pady=2)

    def show_categories(self, categories, on_select):
        self.show_popup(self.buttons['categories'], categories, on_select)

    def set_scanner_status(self, connected):
        self.scanner_status_label.configure(text_color='#4ADE80' if connected else '#EF6464')


class TablePopupMenu(ctk.CTkButton):
    """Единая кнопка выбора таблицы, совместимая с TableController."""

    def __init__(self, parent, show_popup):
        self.values, self.on_select, self.show_popup = [], None, show_popup
        super().__init__(parent, text='Выбрать таблицу', anchor='w', height=36,
                         fg_color='#151F2D', hover_color='#151F2D',
                         corner_radius=7, font=('Segoe UI', 13), command=self.open)
        arrow = tk.Label(self, text='▾', font=('Segoe UI', 14),
                         bg='#151F2D', fg='#E7EDF6', bd=0, cursor='hand2')
        arrow.place(relx=1, x=-16, rely=0.5, anchor='center')
        arrow.bind('<Button-1>', lambda _: self.open())

    def configure(self, **kwargs):
        self.values = kwargs.pop('values', self.values)
        self.on_select = kwargs.pop('command', self.on_select)
        return super().configure(**kwargs)

    def set(self, value):
        super().configure(text=value)

    def open(self):
        self.show_popup(self, [(v, v) for v in self.values], self.choose, below=True)

    def choose(self, value):
        self.set(value)
        if self.on_select:
            self.on_select(value)


class AdminControlPanel(ControlPanelUser):
    ADMIN_BUTTONS = (('add_table', 'Добавить таблицу'),
                     ('delete_table', 'Удалить таблицу'),
                     ('add_record', 'Добавить запись'),
                     ('add_column', 'Добавить столбец'),
                     ('delete_column', 'Удалить столбец'))

    def __init__(self, parent, status_var):
        super().__init__(parent, status_var)
        self.icons.update(self.load_icons(name for name, _ in self.ADMIN_BUTTONS))

    def draw(self):
        footer = ctk.CTkFrame(self.parent, fg_color='#202938', corner_radius=0)
        footer.pack(side='bottom', fill='x')
        self.draw_status(footer)
        scroll = ctk.CTkScrollableFrame(self.parent, fg_color='transparent', corner_radius=0)
        scroll.pack(fill='both', expand=True)
        self.header(scroll, 'Панель управления', 18)
        self.header(scroll, 'РЕДАКТИРОВАНИЕ ТАБЛИЦ')
        self.table_menu = TablePopupMenu(scroll, self.show_popup)
        self.table_menu.pack(fill='x', padx=14, pady=5)
        for name, title in self.ADMIN_BUTTONS:
            self.draw_button(scroll, name, title, 'normal' if name == 'add_table' else 'disabled')
        for title, buttons in self.SECTIONS:
            self.header(scroll, title)
            for name, label in buttons:
                self.draw_button(scroll, name, label)
        root = self.parent.winfo_toplevel()
        root.bind('<ButtonPress-1>', self.close_on_outside, add='+')
        root.bind('<Escape>', lambda _: self.close_popup(), add='+')
