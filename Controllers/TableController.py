
"""Просмотр таблиц, поиск и операции с их структурой."""
import re
from tkinter import messagebox

from Controllers.SQL import SQL
from Interface.ColumnNames import display_name
from Interface.InterfaceTable import AddTableWindow, AddColumnWindow


class TableController:
    TYPE_COLUMNS = {'Product_name', 'UYAIS', 'FNN'}

    def __init__(self, bd, panel, view, on_select, on_edit):
        self.bd, self.panel, self.view = bd, panel, view
        self.on_select, self.on_edit = on_select, on_edit
        self.table_name = self.selected_column = None
        self.columns, self.raw_rows = [], []
        self.category_id = None
        self._click_job = None
        self._skip_release = False
        panel.table_menu.configure(command=self.select_table)
        actions = {'add_table': self.open_add_table, 'delete_table': self.delete_table,
                   'add_column': self.open_add_column, 'delete_column': self.delete_column}
        for name, handler in actions.items():
            panel.buttons[name].configure(command=handler)
        view.find_button.configure(command=self.search)
        view.reset_button.configure(command=self.reset_search)
        view.search_entry.bind('<Return>', lambda _: self.search())

    def _error(self, text, error):
        self.bd.connection.rollback()
        messagebox.showerror('Ошибка', f'{text}:\n{error}')

    def load_tables(self):
        try:
            tables = SQL.get_tables(self.bd)
            self.panel.table_menu.configure(values=tables or ['Нет таблиц'])
            self.panel.table_menu.set('Выбрать таблицу' if tables else 'Нет таблиц')
            self.update_products_count()
        except Exception as error:
            self._error('Не удалось получить таблицы', error)

    def select_table(self, table, category_id=None):
        if table in ('Выбрать таблицу', 'Нет таблиц'):
            return
        try:
            self.panel.table_menu.set(table)
            self.category_id = category_id if table == 'Product' else None
            self.load_table(table)
            for name in ('delete_table', 'add_record', 'add_column'):
                self.panel.buttons[name].configure(state='normal')
        except Exception as error:
            self._error('Не удалось загрузить таблицу', error)

    #===== Загрузка и восстановление выделения после изменения записи =====
    def load_table(self, table, restore_id=None):
        if self._click_job:
            self.view.parent.after_cancel(self._click_job)
            self._click_job = None
        self.columns, self.raw_rows = SQL.get_table_data(self.bd, table)
        if table == 'Product' and self.category_id is not None:
            index = self.columns.index('product_type_id')
            self.raw_rows = [row for row in self.raw_rows if row[index] == self.category_id]
        self.table_name, self.selected_column = table, None
        self.view.show_table([display_name(c) for c in self.columns], self.raw_rows)
        self.view.table.bind('<ButtonRelease-1>', self.handle_click)
        self.view.table.bind('<Double-Button-1>', self.handle_double_click)
        self.column_selected(None)
        self.on_select(table)
        if restore_id is not None:
            index = self.columns.index('id')
            row = next((i for i, values in enumerate(self.raw_rows)
                        if values[index] == restore_id), None)
            if row is not None:
                self.view.table.select_row(row)
                self.on_select(table, restore_id)

    #===== Фильтр по виду изделия =====
    def get_categories(self):
        return [(ident, f'{name or "Без названия"} (ID: {ident})')
                for ident, name, *_ in SQL.get_product_types(self.bd)]

    def show_category(self, category_id):
        self.select_table('Product', category_id)

    #===== Поиск исходной записи по строке на экране =====
    def _clicked_record(self, event):
        sheet = self.view.table
        if sheet.identify_region(event) != 'table':
            return None
        row = sheet.identify_row(event, allow_end=False)
        if row is None or not 0 <= row < len(sheet.data):
            return None
        index = self.columns.index('id')
        record_id = sheet.data[row][index]
        record = next((r for r in self.raw_rows if str(r[index]) == str(record_id)), None)
        return (row, record[index], record) if record else None

    #===== Одиночное нажатие: не блокирует второй клик запросом к БД =====
    def handle_click(self, event):
        if self._skip_release:
            self._skip_release = False
            return

        sheet = self.view.table
        column = None
        if sheet.identify_region(event) == 'header':
            index = sheet.identify_column(event, allow_end=False)
            index = sheet.data_c(index) if index is not None else None
            if index is not None and 0 <= index < len(self.columns):
                column = self.columns[index]
        else:
            selected = self._clicked_record(event)
            if selected:
                sheet.select_row(selected[0])
                if self._click_job:
                    self.view.parent.after_cancel(self._click_job)
                table, record_id = self.table_name, selected[1]
                self._click_job = self.view.parent.after(
                    350, lambda: self.on_select(table, record_id))

        self.selected_column = column
        self.column_selected(column)

    #===== Двойное нажатие: отменяем отложенную загрузку и открываем редактор =====
    def handle_double_click(self, event):
        if self._click_job:
            self.view.parent.after_cancel(self._click_job)
            self._click_job = None

        selected = self._clicked_record(event)
        if selected:
            self._skip_release = True
            self.view.parent.after(150, lambda: setattr(self, '_skip_release', False))
            self.on_edit(self.table_name, tuple(self.columns), tuple(selected[2]))

    def search(self):
        value = self.view.search_entry.get().strip()
        if not value:
            return self.reset_search()
        if not self.table_name:
            return
        try:
            column = next(c for c in self.columns
                          if display_name(c) == self.view.search_column.get())
            rows = SQL.search_records(self.bd, self.table_name, column, value)
            if self.table_name == 'Product' and self.category_id is not None:
                index = self.columns.index('id')
                allowed = {row[index] for row in self.raw_rows}
                rows = [row for row in rows if row[index] in allowed]
            self.view.set_data(rows)
            self.on_select(self.table_name)
        except Exception as error:
            self._error('Не удалось выполнить поиск', error)

    #===== Поиск по штрихкоду в Product и связанных справочниках =====
    def find_product(self, code):
        parts = [p.casefold().strip() for p in re.split(r'[\x00-\x1f]+', code)
                 if len(p.strip()) >= 3 and p.strip() != '[)>']
        if not parts:
            return messagebox.showwarning('Поиск', 'Введите код')
        try:
            self.panel.table_menu.set('Product')
            self.select_table('Product')
            if self.table_name != 'Product':
                return
            products = [dict(zip(self.columns, row)) for row in self.raw_rows]
            hits = [set() for _ in parts]
            for table in SQL.get_tables(self.bd):
                cols, rows = ((self.columns, self.raw_rows) if table == 'Product'
                              else SQL.get_table_data(self.bd, table))
                name = table.lower().rstrip('s')
                link = next((c for c in self.columns if c.endswith('_id')
                             and c[:-3].replace('_', '').lower() == name), None)
                if table != 'Product' and 'product_id' not in cols and not link:
                    continue
                for row in rows:
                    item = dict(zip(cols, row))
                    values = [str(v).strip().casefold() for c, v in item.items()
                              if v is not None and c != 'id' and not c.endswith('_id')
                              and not c.lower().startswith('svg_')]
                    ids = ({item['id']} if table == 'Product' else
                           {item['product_id']} if item.get('product_id') is not None else
                           {p['id'] for p in products if link and p.get(link) == item['id']})
                    for i, part in enumerate(parts):
                        if any(len(v) >= 3 and part.endswith(v) for v in values):
                            hits[i].update(ids)
            found = set.intersection(*(hits_ for hits_ in hits if hits_)) if any(hits) else set()
            index = self.columns.index('id')
            rows = [row for row in self.raw_rows if row[index] in found]
            self.view.set_data(rows)
            self.on_select('Product')
            if len(rows) == 1:
                self.view.table.select_row(0)
                self.on_select('Product', rows[0][index])
            else:
                messagebox.showinfo('Поиск', 'Изделие не найдено' if not rows
                                    else f'Найдено {len(rows)} изделий')
        except Exception as error:
            self._error('Не удалось найти изделие', error)

    def reset_search(self):
        self.view.search_entry.delete(0, 'end')
        self.view.set_data(self.raw_rows)
        if self.table_name:
            self.on_select(self.table_name)

    def update_products_count(self):
        self.panel.products_count.set(SQL.get_product_count(self.bd))

    def column_selected(self, column):
        protected = (column == 'id' or
                     self.table_name in ('Product', 'ProductType') and column in self.TYPE_COLUMNS or
                     self.table_name == 'Product' and column in ('product_type_id', 'code_id', 'Notes'))
        self.panel.buttons['delete_column'].configure(
            state='normal' if column and not protected else 'disabled')

    #===== Изменение структуры таблиц; используется левой панелью =====
    def open_add_table(self):
        try:
            window = AddTableWindow(self.view.parent, SQL.get_data_types(self.bd),
                                    lambda: self.create_table(window))
        except Exception as error:
            self._error('Не удалось открыть создание таблицы', error)

    def create_table(self, window):
        try:
            data = window.get_values()
            if not data['table_name'] or not data['columns']:
                return messagebox.showwarning('Ошибка', 'Укажите название и хотя бы один столбец.')
            SQL.create_table(self.bd, data['table_name'], data['columns'])
            window.destroy()
            self.load_tables()
            self.panel.table_menu.set(data['table_name'])
            self.select_table(data['table_name'])
        except Exception as error:
            self._error('Не удалось создать таблицу', error)

    def open_add_column(self):
        if self.table_name:
            AddColumnWindow(self.view.parent, self.create_column)

    def create_column(self, name, data_type, window):
        if not name:
            return messagebox.showwarning('Ошибка', 'Укажите имя столбца.')
        try:
            SQL.add_column(self.bd, self.table_name, name, data_type)
            window.destroy()
            self.load_table(self.table_name)
        except Exception as error:
            self._error('Не удалось добавить столбец', error)

    def delete_column(self):
        column = self.selected_column
        if not column or not messagebox.askyesno(
                'Удаление столбца', f'Удалить «{display_name(column)}»?\nДанные будут удалены!'):
            return
        try:
            SQL.delete_column(self.bd, self.table_name, column)
            self.load_table(self.table_name)
        except Exception as error:
            self._error('Не удалось добавить столбец', error)

    def delete_table(self):
        table = self.table_name
        if not table or not messagebox.askyesno('Удаление таблицы',
                                                f'Удалить таблицу «{table}» и все её данные?'):
            return
        try:
            SQL.delete_table(self.bd, table)
            self.table_name, self.columns, self.raw_rows = None, [], []
            self.view.clear_table()
            self.load_tables()
            self.on_select(table)
            for name in ('delete_table', 'add_record', 'add_column', 'delete_column'):
                self.panel.buttons[name].configure(state='disabled')
        except Exception as error:
            self._error('Не удалось удалить таблицу', error)
