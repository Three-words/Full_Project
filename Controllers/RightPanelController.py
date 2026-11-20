
"""События правой панели: редактирование, коды, примечания и сворачивание."""
from tkinter import filedialog, messagebox
from Interface.ColumnNames import display_name


class RightPanelController:
    LOCKED = {'id', 'code_id', 'product_type_id', 'UII', 'TKN', 'cargo_year'}
    DECIMALS = {'Gross_weight', 'Net_weight', 'Width', 'Height', 'Depth'}

    #===== Инициализация панели и подключение событий =====
    def __init__(self, details, notes, parent, on_attribute, on_notes,
                 on_load_labels, on_preview, on_export):
        self.details, self.notes, self.parent = details, notes, parent
        self.on_attribute, self.on_notes = on_attribute, on_notes
        self.on_load_labels, self.on_preview, self.on_export = on_load_labels, on_preview, on_export
        self.record_id, self.labels, self.editing = None, {}, None
        self.loaded_codes_for = None
        self.current_record = {}
        details.tabs.configure(command=self.change_tab)
        notes.save_button.configure(command=self.save_notes)

    #===== Выбор записи и обработчики параметров =====
    def show_record(self, table, record_id, record):
        self.finish_edit()
        self.record_id = record_id if table == 'Product' else None
        self.current_record = record or {}
        title = (record.get('Product_name') or record.get('product_serial_number') or
                 f'Изделие № {record_id}') if record else None
        self.details.set_title(str(title) if title is not None else None)
        attributes = {display_name(k): v for k, v in record.items()
                      if k not in ('Notes', 'cargo_year') and not k.startswith('SVG_') and not k.endswith('_id')} if record else None
        self.details.set_attributes(attributes)
        self.notes.set_notes(record.get('Notes') if record else None, self.record_id is not None)
        for row, left, right in self.details.attribute_rows:
            row.bind('<Configure>', lambda e, a=left, b=right: self.wrap_labels(e, a, b))
        if self.record_id is not None:
            for column in record:
                if column in self.LOCKED or column == 'Notes' or column.startswith('SVG_') or column.endswith('_id'):
                    continue
                name = display_name(column)
                label = self.details.value_labels.get(name)
                if label:
                    label.configure(cursor='hand2')
                    label.bind('<Button-1>', lambda _, key=name: self.edit_attribute(key))
                    label.bind('<Enter>', lambda _, w=label: w.configure(fg='#90BEF5'))
                    label.bind('<Leave>', lambda _, w=label: w.configure(fg='#F2F6FC'))
        self.labels = {}
        self.loaded_codes_for = None
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

    #===== Сохранение или отмена редактирования поля =====
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

    #===== Сохранение отдельного параметра через обратный вызов =====
    def save_attribute(self, title, text):
        if self.record_id is None:
            return False
        try:
            column = next((c for c in self.current_record if display_name(c) == title), None)
            if column is None or column in self.LOCKED:
                raise ValueError('Этот параметр нельзя редактировать напрямую')
            value = text.strip() or None
            if value is not None and column in self.DECIMALS:
                value = value.replace(',', '.')
            updated = self.on_attribute(self.record_id, column, value)
            self.sync_record(updated)
            return True
        except Exception as error:
            messagebox.showerror('Ошибка изменения параметра', str(error), parent=self.parent)
            return False

    #===== Обновление надписей без пересоздания виджетов =====
    def sync_record(self, record):
        self.current_record = record
        title = record.get('Product_name') or record.get('product_serial_number') or f'Изделие № {self.record_id}'
        self.details.set_title(str(title))
        for key, value in record.items():
            label = self.details.value_labels.get(display_name(key))
            if label and label.winfo_exists():
                label.configure(text='—' if value is None or value == '' else str(value))

    #===== Сохранение примечаний без перестроения панели =====
    def save_notes(self):
        if self.record_id is None:
            return
        try:
            text = self.notes.get_notes()
            self.on_notes(self.record_id, text)
            self.current_record['Notes'] = text
        except Exception as error:
            messagebox.showerror('Ошибка сохранения примечаний', str(error), parent=self.parent)

    #===== Сохранённые SVG: вкладка, просмотр и экспорт =====
    def change_tab(self, name):
        self.finish_edit()
        self.details.show_section(name)
        if name == 'Коды' and self.loaded_codes_for != self.record_id:
            self.refresh_codes()

    #===== Загрузка сохранённых этикеток на вкладку =====
    def refresh_codes(self):
        if self.details.get_tab() != 'Коды':
            return
        if self.record_id is None:
            return self.details.set_codes(None)
        try:
            self.labels = self.on_load_labels(self.record_id)
            self.loaded_codes_for = self.record_id
            self.details.set_codes(self.labels)
            for name, button in self.details.code_buttons.items():
                button.configure(command=lambda key=name: self.open_svg(key))
            for row, label in self.details.code_rows:
                row.bind('<Configure>', lambda e, w=label:
                         w.configure(wraplength=max(65, e.width - 110)))
        except ValueError:
            self.loaded_codes_for = self.record_id
            self.labels = {}
            self.details.set_codes({})
        except Exception as error:
            messagebox.showerror('Ошибка этикеток', str(error), parent=self.parent)

    #===== Открытие отдельного окна просмотра SVG =====
    def open_svg(self, name):
        try:
            self.on_preview(self.labels[name], name, self.record_id,
                             self.details.LABEL_NAMES.get(name, name))
        except Exception as error:
            messagebox.showerror('Просмотр SVG', str(error), parent=self.parent)

    #===== Экспорт этикеток в выбранную папку =====
    def save_labels(self):
        if self.record_id is None:
            return
        folder = filedialog.askdirectory(title='Выберите папку для этикеток', parent=self.parent)
        if not folder:
            return
        try:
            paths = self.on_export(self.record_id, folder)
            messagebox.showinfo('Сохранение', f'Сохранено этикеток: {len(paths)}\nПапка: {folder}')
        except Exception as error:
            messagebox.showerror('Ошибка сохранения', str(error), parent=self.parent)

    #===== Сворачивание правой панели =====
    def bind_layout(self, panes, right, tab, close_button):
        self.panes, self.right, self.tab = panes, right, tab
        self.is_open = True
        close_button.configure(command=self.toggle_panel)
        tab.bind('<Button-1>', lambda _: self.toggle_panel())
        tab.bind('<Enter>', lambda _: tab.itemconfigure('tab', fill='#3C5878'))
        tab.bind('<Leave>', lambda _: tab.itemconfigure('tab', fill='#30445D'))

    #===== Сворачивание или разворачивание правой панели =====
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
