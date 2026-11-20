
"""Просмотр таблиц, поиск и операции с их структурой."""
import re
from tkinter import messagebox

from Controllers.SQL import SQL
from Interface.ColumnNames import (display_name, english_name, table_name, real_table,
                                   read_names, write_names)
from Interface.InterfaceTable import AddTableWindow, AddColumnWindow


class TableController:
    TYPE_COLUMNS = {'Product_name', 'UYAIS', 'FNN'}

    #===== Инициализация таблицы и событий интерфейса =====
    def __init__(self, bd, panel, view, on_select, on_edit):
        self.bd, self.panel, self.view = bd, panel, view
        self.on_select, self.on_edit = on_select, on_edit
        self.table_name = self.selected_column = None
        self.columns, self.raw_rows = [], []
        self.row_lookup = {}
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
        view.sort_order.configure(command=lambda _: self.search())

    #===== Откат транзакции и показ ошибки =====
    def _error(self, text, error):
        self.bd.connection.rollback()
        messagebox.showerror('Ошибка', f'{text}:\n{error}')

    #===== Загрузка списка таблиц и счётчика изделий =====
    def load_tables(self):
        try:
            tables = SQL.get_tables(self.bd)
            self.panel.table_menu.configure(values=[table_name(t) for t in tables] or ['Нет таблиц'])
            self.panel.table_menu.set('Выбрать таблицу' if tables else 'Нет таблиц')
            self.update_products_count()
        except Exception as error:
            self._error('Не удалось получить таблицы', error)

    #===== Выбор таблицы и категории изделий =====
    def select_table(self, table, category_id=None):
        if table in ('Выбрать таблицу', 'Нет таблиц'):
            return
        table = real_table(table)
        try:
            self.panel.table_menu.set(table_name(table))
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
        self.columns, self.raw_rows = SQL.get_table_data(
            self.bd, table, self.category_id if table == 'Product' else None)
        self.table_name, self.selected_column = table, None
        id_index = self.columns.index('id')
        self.row_lookup = {str(row[id_index]): (i, row) for i, row in enumerate(self.raw_rows)}
        self.view.show_table([display_name(c) for c in self.columns], self.raw_rows)
        visible = [display_name(c) for c in self.columns if not c.endswith('_id') and c != 'cargo_year']
        self.view.columns_menu.set_columns(visible)
        self.view.display_columns(visible)
        self.view.search_column.configure(text='Все столбцы')
        self.view.sort_order.set('Без сортировки')
        self.view.table.bind('<ButtonRelease-1>', self.handle_click)
        self.view.table.bind('<Double-Button-1>', self.handle_double_click)
        self.column_selected(None)
        self.on_select(table)
        if restore_id is not None:
            selected = self.row_lookup.get(str(restore_id))
            if selected is not None:
                self.view.table.select_row(selected[0])
                self.on_select(table, restore_id)

    #===== Точечное обновление видимой строки и исходных данных =====
    def update_row(self, changes):
        if self.table_name != 'Product' or not changes or 'id' not in changes:
            return
        id_column = self.columns.index('id')
        record_id = str(changes['id'])
        selected = self.row_lookup.get(record_id)
        if selected is None:
            return
        index, old = selected
        data = dict(zip(self.columns, old))
        data.update(changes)
        self.raw_rows[index] = tuple(data[c] for c in self.columns)
        self.row_lookup[record_id] = (index, self.raw_rows[index])
        sheet = self.view.table
        if sheet is None:
            return
        formatted = self.view.prepare_rows([self.raw_rows[index]])[0]
        for row_index, row in enumerate(sheet.data):
            if str(row[id_column]) != record_id:
                continue
            changed = False
            for column, value in enumerate(formatted):
                if row[column] != value:
                    sheet.set_cell_data(row_index, column, value, redraw=False)
                    changed = True
            if changed:
                sheet.refresh()
            break

    #===== Фильтр по виду изделия =====
    def get_categories(self):
        return [(ident, f'{name or "Без названия"} (ID: {ident})')
                for ident, name, *_ in SQL.get_product_types(self.bd)]

    #===== Отображение изделий выбранной категории =====
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
        selected = self.row_lookup.get(str(record_id))
        return (row, selected[1][index], selected[1]) if selected else None

    #===== Одиночное нажатие: не блокирует второй клик запросом к БД =====
    def handle_click(self, event):
        if self._skip_release:
            self._skip_release = False
            return

        sheet = self.view.table
        if sheet.identify_region(event) == 'header':
            index = sheet.identify_column(event, allow_end=False)
            index = sheet.data_c(index) if index is not None else None
            if index is not None and 0 <= index < len(self.columns):
                column = self.columns[index]
                if column.endswith('_id') or column == 'cargo_year':
                    return
                self.selected_column = None if self.selected_column == column else column
                self.view.search_column.configure(
                    text=display_name(self.selected_column) if self.selected_column else 'Все столбцы')
                self.column_selected(self.selected_column)
                self.search()
        else:
            selected = self._clicked_record(event)
            if selected:
                sheet.select_row(selected[0])
                if self._click_job:
                    self.view.parent.after_cancel(self._click_job)
                table, record_id = self.table_name, selected[1]
                self._click_job = self.view.parent.after(
                    350, lambda: self.on_select(table, record_id))

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

    #===== Поиск по фрагменту и сортировка результатов =====
    def search(self):
        if not self.table_name:
            return
        try:
            value = self.view.search_entry.get().strip()
            column = self.selected_column
            rows = (SQL.search_records(self.bd, self.table_name, column, value, self.category_id)
                    if value else list(self.raw_rows))
            order = self.view.sort_order.get()
            if column is not None and order != 'Без сортировки':
                index = self.columns.index(column)
                # Пустые значения всегда идут в конце; числа сортируются как числа.
                filled = [row for row in rows if row[index] is not None and row[index] != '']
                empty = [row for row in rows if row[index] is None or row[index] == '']
                filled.sort(key=lambda row: (row[index].casefold() if isinstance(row[index], str)
                                             else row[index]),
                            reverse=order == 'По убыванию')
                rows = filled + empty
            self.view.set_data(rows)
            self.on_select(self.table_name)
        except Exception as error:
            self._error('Не удалось выполнить поиск или сортировку', error)

    #===== Поиск по штрихкоду в Product и связанных справочниках =====
    def find_product(self, code):
        parts = [p.casefold().strip() for p in re.split(r'[\x00-\x1f]+', code)
                 if len(p.strip()) >= 3 and p.strip() != '[)>']
        if not parts:
            return messagebox.showwarning('Поиск', 'Введите код')
        try:
            self.select_table('Product')
            if self.table_name != 'Product':
                return
            hits = [set() for _ in parts]
            for table in SQL.get_tables(self.bd):
                cols, rows = ((self.columns, self.raw_rows) if table == 'Product'
                              else SQL.get_table_data(self.bd, table))
                name = table.lower().rstrip('s')
                link = next((c for c in self.columns if c.endswith('_id')
                             and c[:-3].replace('_', '').lower() == name), None)
                if table != 'Product' and 'product_id' not in cols and not link:
                    continue
                references = {}
                if link:
                    ref_index, id_index = self.columns.index(link), self.columns.index('id')
                    for product in self.raw_rows:
                        references.setdefault(product[ref_index], set()).add(product[id_index])
                for row in rows:
                    item = dict(zip(cols, row))
                    values = [str(v).strip().casefold() for c, v in item.items()
                              if v is not None and c != 'id' and not c.endswith('_id')
                              and not c.lower().startswith('svg_')]
                    ids = ({item['id']} if table == 'Product' else
                           {item['product_id']} if item.get('product_id') is not None else
                           references.get(item['id'], set()))
                    for i, part in enumerate(parts):
                        if any(len(v) >= 3 and part.endswith(v) for v in values):
                            hits[i].update(ids)
            found = set.intersection(*hits) if all(hits) else set()
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

    #===== Сброс поиска и сортировки =====
    def reset_search(self):
        self.view.search_entry.delete(0, 'end')
        self.selected_column = None
        self.view.search_column.configure(text='Все столбцы')
        self.view.sort_order.set('Без сортировки')
        self.column_selected(None)
        self.view.set_data(self.raw_rows)
        if self.table_name:
            self.on_select(self.table_name)

    #===== Обновление счётчика изделий =====
    def update_products_count(self):
        self.panel.products_count.set(SQL.get_product_count(self.bd))

    #===== Проверка доступности удаления столбца =====
    def column_selected(self, column):
        protected = (column == 'id' or
                     self.table_name in ('Product', 'ProductType') and column in self.TYPE_COLUMNS or
                     self.table_name == 'Product' and column in ('product_type_id', 'code_id', 'Notes'))
        self.panel.buttons['delete_column'].configure(
            state='normal' if column and not protected else 'disabled')

    #===== Изменение структуры таблиц; используется левой панелью =====
    def open_add_table(self):
        try:
            window = AddTableWindow(self.view.parent, lambda: self.create_table(window))
        except Exception as error:
            self._error('Не удалось открыть создание таблицы', error)

    #===== Создание таблицы с сохранением русского обозначения =====
    def create_table(self, window):
        previous = None
        try:
            data = window.get_values()
            if not data['table_name'] or not data['columns']:
                return messagebox.showwarning('Ошибка', 'Укажите название и хотя бы один столбец.')
            original = data['table_name']
            table = english_name(original)
            if table.lower() in {t.lower() for t in SQL.get_tables(self.bd)}:
                raise ValueError('Таблица с таким английским именем уже существует: ' + table)
            columns = []
            original_names = {}
            for item in data['columns']:
                name = english_name(item['name'])
                if name.lower() in {'id', *(c['name'].lower() for c in columns)}:
                    raise ValueError('Столбец с таким именем уже указан: ' + name)
                columns.append({**item, 'name': name})
                if name != item['name']:
                    original_names[name.lower()] = item['name']
            previous = read_names()
            updated = {key: dict(value) for key, value in previous.items()}
            if table != original:
                updated['tables'][table] = original
            for name, title in original_names.items():
                if name in updated['columns'] and updated['columns'][name] != title:
                    raise ValueError('Название столбца уже используется с другой подписью: ' + name)
                updated['columns'][name] = title
            SQL.create_table(self.bd, table, columns, commit=False)
            write_names(updated)
            try:
                self.bd.connection.commit()
            except Exception:
                write_names(previous)
                raise
            window.destroy()
            self.load_tables()
            self.select_table(table)
        except Exception as error:
            self._error('Не удалось создать таблицу', error)

    #===== Открытие формы нового столбца =====
    def open_add_column(self):
        if self.table_name:
            AddColumnWindow(self.view.parent, self.create_column)

    #===== Добавление столбца с сохранением русского обозначения =====
    def create_column(self, name, data_type, window):
        if not name:
            return messagebox.showwarning('Ошибка', 'Укажите имя столбца.')
        try:
            translated = english_name(name)
            if translated.lower() in {c.lower() for c in self.columns}:
                raise ValueError('Столбец уже существует: ' + translated)
            previous = read_names()
            updated = {key: dict(value) for key, value in previous.items()}
            if translated != name:
                old = updated['columns'].get(translated.lower())
                if old and old != name:
                    raise ValueError('Английское имя уже соответствует другому названию: ' + old)
                updated['columns'][translated.lower()] = name
            SQL.add_column(self.bd, self.table_name, translated, data_type, commit=False)
            write_names(updated)
            try:
                self.bd.connection.commit()
            except Exception:
                write_names(previous)
                raise
            window.destroy()
            self.load_table(self.table_name)
        except Exception as error:
            self._error('Не удалось добавить столбец', error)

    #===== Удаление выбранного столбца =====
    def delete_column(self):
        column = self.selected_column
        if not column or not messagebox.askyesno(
                'Удаление столбца',
                f'Удалить «{display_name(column)}»?\nДанные будут удалены!'):
            return
        try:
            SQL.delete_column(self.bd, self.table_name, column)
            self.load_table(self.table_name)
        except Exception as error:
            self._error('Не удалось удалить столбец', error)

    #===== Удаление выбранной таблицы =====
    def delete_table(self):
        table = self.table_name
        if not table or not messagebox.askyesno(
                'Удаление таблицы', f'Удалить таблицу «{table}» и все её данные?'):
            return
        try:
            SQL.delete_table(self.bd, table)
            self.table_name, self.columns, self.raw_rows = None, [], []
            self.row_lookup.clear()
            self.view.clear_table()
            self.load_tables()
            self.on_select(table)
            for name in ('delete_table', 'add_record', 'add_column', 'delete_column'):
                self.panel.buttons[name].configure(state='disabled')
        except Exception as error:
            self._error('Не удалось удалить таблицу', error)
