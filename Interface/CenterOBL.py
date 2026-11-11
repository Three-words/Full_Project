
"""Таблица tksheet и управление её отображением, без запросов к БД."""
import customtkinter as ctk
from tkinter import font
from tksheet import Sheet


class ColumnsMenu:
    """Выпадающее меню столбцов с двумя рядами кнопок."""

    def __init__(self, parent, card='#202938'):
        self.parent, self.card = parent, card
        self.popup = self.on_apply = None
        self.columns, self.selection = [], {}

    def set_columns(self, columns):
        self.close()
        self.columns = list(columns)
        self.selection = {c: ctk.BooleanVar(value=True) for c in columns}

    def toggle(self, button):
        if self.popup:
            return self.close()
        self.open(button)

    def open(self, button):
        self.parent.update_idletasks()
        y = button.winfo_rooty() - self.parent.winfo_rooty() + button.winfo_height() + 5
        available = self.parent.winfo_height() - y - 8
        height = min(max(230, min(210, len(self.columns) * 36) + 165), max(230, available))

        self.popup = ctk.CTkFrame(self.parent, width=280, height=height,
                                  fg_color=self.card, border_width=1,
                                  border_color='#46546A', corner_radius=10)
        self.popup.pack_propagate(False)
        ctk.CTkLabel(self.popup, text='Отображаемые столбцы',
                     font=('Segoe UI', 14, 'bold')).pack(anchor='w', padx=15, pady=(10, 6))

        scroll = ctk.CTkScrollableFrame(self.popup, fg_color='transparent')
        scroll.pack(fill='both', expand=True, padx=8)
        for column in self.columns:
            ctk.CTkCheckBox(scroll, text=column, variable=self.selection[column],
                            font=('Segoe UI', 13), checkbox_width=21,
                            checkbox_height=21, fg_color='#285DAC').pack(
                anchor='w', fill='x', padx=6, pady=4)

        self.draw_buttons((('Выбрать все', lambda: self.select_all(True), '#344256'),
                           ('Снять все', lambda: self.select_all(False), '#344256')),
                          pady=(8, 4))
        self.error = ctk.CTkLabel(self.popup, text='', height=18, text_color='#EF6464')
        self.error.pack()
        self.draw_buttons((('Применить', self.apply, '#285DAC'),
                           ('Отмена', self.close, '#344256')))
        self.popup.place(relx=1, x=-8, y=y, anchor='ne')
        self.popup.lift()

    def draw_buttons(self, buttons, pady=(0, 10)):
        row = ctk.CTkFrame(self.popup, fg_color='transparent')
        row.pack(fill='x', padx=10, pady=pady)
        for title, command, color in buttons:
            ctk.CTkButton(row, text=title, command=command, width=105,
                          height=30, fg_color=color).pack(
                side='left', fill='x', expand=True, padx=4)

    def select_all(self, value):
        for variable in self.selection.values():
            variable.set(value)

    def apply(self):
        selected = [c for c in self.columns if self.selection[c].get()]
        if not selected:
            return self.error.configure(text='Выберите хотя бы один столбец')
        if self.on_apply:
            self.on_apply(selected)
        self.close()

    def close(self):
        if self.popup:
            self.popup.destroy()
        self.popup = None


class CenterOBL:
    def __init__(self, parent, card='#202938'):
        self.parent, self.card = parent, card
        self.table = None
        self.columns, self.widths = [], {}
        self.columns_menu = ColumnsMenu(parent, card)
        self.columns_menu.on_apply = self.display_columns

    def draw(self):
        search = ctk.CTkFrame(self.parent, fg_color='transparent')
        search.grid(row=0, column=0, columnspan=2, sticky='ew', padx=12, pady=(12, 8))
        search.grid_columnconfigure(2, weight=1)
        ctk.CTkLabel(search, text='Поиск по:', font=('Segoe UI', 12)).grid(
            row=0, column=0, padx=(0, 6))
        self.search_column = ctk.CTkOptionMenu(search, values=['Столбец'],
                                                fg_color='#151F2D', width=110,
                                                button_color='#285DAC')
        self.search_column.grid(row=0, column=1, padx=(0, 6))
        self.search_entry = ctk.CTkEntry(search, height=34, placeholder_text='Введите значение')
        self.search_entry.grid(row=0, column=2, sticky='ew', padx=(0, 6))
        for index, (name, title) in enumerate((('find_button', 'Найти'),
                                                ('reset_button', 'Сброс'),
                                                ('columns_button', 'Столбцы ▾')), 3):
            button = ctk.CTkButton(search, text=title, height=34,
                                   width=112 if index == 5 else 64,
                                   fg_color='#285DAC' if index == 3 else '#344256')
            button.grid(row=0, column=index, padx=(0, 6))
            setattr(self, name, button)
        self.columns_button.configure(state='disabled',
                                      command=lambda: self.columns_menu.toggle(self.columns_button))

    @staticmethod
    def prepare_rows(rows):
        return [['' if value is None else '[SVG]' if isinstance(value, str) and
                 '<svg' in value[:200] else str(value) for value in row] for row in rows]

    @staticmethod
    def column_widths(columns, rows):
        normal = font.Font(family='Segoe UI', size=14)
        bold = font.Font(family='Segoe UI', size=14, weight='bold')
        return [max([bold.measure(c)] + [normal.measure(row[i]) for row in rows]) + 40
                for i, c in enumerate(columns)]

    def show_table(self, columns, rows):
        self.clear_table()
        self.columns = list(columns)
        data = self.prepare_rows(rows)
        self.widths = dict(zip(columns, self.column_widths(columns, data)))
        self.search_column.configure(values=columns or ['Столбец'])
        self.search_column.set(columns[0] if columns else 'Столбец')
        self.columns_menu.set_columns(columns)
        self.columns_button.configure(state='normal' if columns else 'disabled')
        self.table = Sheet(self.parent, data=data, headers=columns,
                           show_row_index=False, show_top_left=False,
                           default_row_height=40, default_header_height=42,
                           align='center', header_align='center',
                           table_bg=self.card, table_fg='#E2E8F0',
                           table_grid_fg='#46546A', alternate_color='#2A3546',
                           header_bg='#344256', header_fg='white',
                           header_grid_fg='#46546A', frame_bg=self.card,
                           outline_thickness=0)
        self.table.font(('Segoe UI', 14, 'normal'))
        self.table.header_font(('Segoe UI', 14, 'bold'))
        for i, column in enumerate(columns):
            self.table.column_width(i, width=self.widths[column], redraw=False)
        self.table.enable_bindings('single_select', 'column_select', 'arrowkeys',
                                   'column_width_resize', 'double_click_column_resize')
        self.table.grid(row=1, column=0, columnspan=2, sticky='nsew', padx=12, pady=(0, 12))
        self.table.refresh()

    def set_data(self, rows):
        if self.table:
            self.table.set_sheet_data(self.prepare_rows(rows), reset_col_positions=False,
                                      reset_row_positions=True, redraw=True)

    def display_columns(self, columns):
        if not self.table:
            return
        if len(columns) == len(self.columns):
            self.table.display_columns('all', redraw=False)
        else:
            self.table.display_columns([self.columns.index(c) for c in columns],
                                       all_columns_displayed=False,
                                       reset_col_positions=True, redraw=False)
        for i, column in enumerate(columns):
            self.table.column_width(i, width=self.widths[column], redraw=False)
        self.table.refresh()

    def clear_table(self):
        if self.table:
            self.table.destroy()
        self.table = None
