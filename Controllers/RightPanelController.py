
"""События правой панели: редактирование, коды, примечания и сворачивание."""
from tkinter import filedialog, messagebox
from Controllers.SQL import SQL
from Controllers.PreviewController import SVGPreviewController
from GenerateQR import SVGController as svg
from Interface.ColumnNames import display_name


class RightPanelController:
    LOCKED = {'id', 'code_id', 'product_type_id', 'UII', 'TKN'}
    DECIMALS = {'Gross_weight', 'Net_weight', 'Width', 'Height', 'Depth'}

    def __init__(self, bd, records, table, details, notes, templates, parent):
        self.bd, self.records, self.table = bd, records, table
        self.details, self.notes, self.templates, self.parent = details, notes, templates, parent
        self.viewer = SVGPreviewController(parent)
        self.record_id, self.labels, self.editing = None, {}, None
        details.tabs.configure(command=self.change_tab)
        notes.save_button.configure(command=self.save_notes)

    #===== Выбор записи и обработчики параметров =====
    def show_record(self, table, record_id, record):
        self.finish_edit()
        self.record_id = record_id if table == 'Product' else None
        title = (record.get('Product_name') or record.get('product_serial_number') or
                 f'Изделие № {record_id}') if record else None
        self.details.set_title(str(title) if title is not None else None)
        attributes = {display_name(k): v for k, v in record.items()
                      if k != 'Notes' and not k.startswith('SVG_')} if record else None
        self.details.set_attributes(attributes)
        self.notes.set_notes(record.get('Notes') if record else None, self.record_id is not None)
        for row, left, right in self.details.attribute_rows:
            row.bind('<Configure>', lambda e, a=left, b=right: self.wrap_labels(e, a, b))
        if self.record_id is not None:
            for column in record:
                if column in self.LOCKED or column == 'Notes' or column.startswith('SVG_'):
                    continue
                name = display_name(column)
                label = self.details.value_labels.get(name)
                if label:
                    label.configure(cursor='hand2')
                    label.bind('<Button-1>', lambda _, key=name: self.edit_attribute(key))
                    label.bind('<Enter>', lambda _, w=label: w.configure(fg='#90BEF5'))
                    label.bind('<Leave>', lambda _, w=label: w.configure(fg='#F2F6FC'))
        self.labels = {}
        self.details.set_codes(None)
        self.refresh_codes()

    #===== Перенос текста при изменении ширины =====
    @staticmethod
    def wrap_labels(event, left, right):
        for label, width in ((left, max(40, (event.width - 40) * 2 // 5)),
                             (right, max(55, (event.width - 40) * 3 // 5))):
            if int(label.cget('wraplength')) != width:
                label.configure(wraplength=width)

    #===== Редактирование: Enter — сохранить, Esc — отменить =====
    def edit_attribute(self, name):
        self.finish_edit()
        label = self.details.value_labels[name]
        entry = self.details.show_editor(label)
        self.editing = (name, label, entry, entry.get())
        entry.bind('<Return>', lambda _: self.finish_edit(True))
        entry.bind('<Escape>', lambda _: self.finish_edit())

    def finish_edit(self, save=False):
        if self.editing is None:
            return 'break'
        name, label, entry, old = self.editing
        if save and entry.winfo_exists():
            value = entry.get().strip()
            if value != old.strip() and not self.save_attribute(name, value):
                return 'break'
        self.editing = None
        self.details.hide_editor(label, entry)
        return 'break'

    #===== Сохранение одного параметра =====
    def save_attribute(self, title, text):
        if self.record_id is None or self.table.table_name != 'Product':
            return False
        try:
            record = SQL.get_record(self.bd, 'Product', self.record_id)
            column = next((k for k in record if display_name(k) == title), None) if record else None
            if column is None or column in self.LOCKED:
                raise ValueError('Этот параметр нельзя редактировать напрямую')
            value = text.strip() or None
            if value is not None and column in self.DECIMALS:
                value = value.replace(',', '.')
            self.records.update_product(self.record_id, {column: value})
            updated = SQL.get_record(self.bd, 'Product', self.record_id)
            self.bd.connection.commit()
        except Exception as error:
            self.bd.connection.rollback()
            messagebox.showerror('Ошибка изменения параметра', str(error), parent=self.parent)
            return False
        self.sync_record(updated)
        return True

    #===== Обновление видимых значений без перестроения интерфейса =====
    def sync_record(self, record):
        title = record.get('Product_name') or record.get('product_serial_number') or f'Изделие № {self.record_id}'
        self.details.set_title(str(title))
        for key, value in record.items():
            label = self.details.value_labels.get(display_name(key))
            if label and label.winfo_exists():
                label.configure(text='—' if value is None or value == '' else str(value))
        if 'id' not in self.table.columns:
            return
        id_col = self.table.columns.index('id')
        values = tuple(record.get(k) for k in self.table.columns)
        for i, row in enumerate(self.table.raw_rows):
            if str(row[id_col]) == str(self.record_id):
                self.table.raw_rows[i] = values
                break
        sheet = self.table.view.table
        if sheet is None:
            return
        formatted = self.table.view.prepare_rows([values])[0]
        for i, row in enumerate(sheet.data):
            if str(row[id_col]) == str(self.record_id):
                for j, value in enumerate(formatted):
                    if row[j] != value:
                        sheet.set_cell_data(i, j, value, redraw=False)
                sheet.refresh()
                break

    #===== Сохранение примечаний =====
    def save_notes(self):
        if self.record_id is None:
            return
        try:
            SQL.update_record(self.bd, 'Product', self.record_id,
                              {'Notes': self.notes.get_notes()}, commit=False)
            record = SQL.get_record(self.bd, 'Product', self.record_id)
            self.bd.connection.commit()
        except Exception as error:
            self.bd.connection.rollback()
            messagebox.showerror('Ошибка сохранения примечаний', str(error), parent=self.parent)
            return
        self.sync_record(record)

    #===== Сохранённые SVG: вкладка, просмотр и экспорт =====
    def change_tab(self, name):
        self.finish_edit()
        self.details.show_section(name)
        self.refresh_codes()

    def refresh_codes(self):
        if self.details.get_tab() != 'Коды':
            return
        if self.record_id is None:
            return self.details.set_codes(None)
        try:
            self.labels = self.templates.load_saved_labels(self.record_id)
            self.details.set_codes(self.labels)
            for name, button in self.details.code_buttons.items():
                button.configure(command=lambda key=name: self.open_svg(key))
            for row, label in self.details.code_rows:
                row.bind('<Configure>', lambda e, w=label:
                         w.configure(wraplength=max(65, e.width - 110)))
        except ValueError:
            self.labels = {}
            self.details.set_codes({})
        except Exception as error:
            self.bd.connection.rollback()
            messagebox.showerror('Ошибка этикеток', str(error), parent=self.parent)

    def open_svg(self, name):
        try:
            self.viewer.open(self.labels[name], name, self.record_id,
                             self.details.LABEL_NAMES.get(name, name))
        except Exception as error:
            messagebox.showerror('Просмотр SVG', str(error), parent=self.parent)

    def save_labels(self):
        if self.record_id is None:
            return
        folder = filedialog.askdirectory(title='Выберите папку для этикеток', parent=self.parent)
        if not folder:
            return
        try:
            labels = self.templates.load_saved_labels(self.record_id)
            paths = svg.export(labels, folder, self.record_id)
            messagebox.showinfo('Сохранение', f'Сохранено этикеток: {len(paths)}\nПапка: {folder}')
        except Exception as error:
            self.bd.connection.rollback()
            messagebox.showerror('Ошибка сохранения', str(error), parent=self.parent)

    #===== Сворачивание правой панели =====
    def bind_layout(self, panes, right, tab, close_button):
        self.panes, self.right, self.tab = panes, right, tab
        self.is_open = True
        close_button.configure(command=self.toggle_panel)
        tab.bind('<Button-1>', lambda _: self.toggle_panel())
        tab.bind('<Enter>', lambda _: tab.itemconfigure('tab', fill='#3C5878'))
        tab.bind('<Leave>', lambda _: tab.itemconfigure('tab', fill='#30445D'))

    def toggle_panel(self):
        if self.is_open:
            self.finish_edit()
            self.right_width = max(240, self.right.winfo_width())
            self.panes.forget(self.right)
            self.tab.grid(row=0, column=1, sticky='n')
        else:
            self.tab.grid_remove()
            self.panes.add(self.right, minsize=240, width=self.right_width, stretch='never')
        self.is_open = not self.is_open
