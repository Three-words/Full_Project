"""Сценарии окон записей: связь форм с операциями приложения через callbacks."""
from tkinter import messagebox
from Interface.ColumnNames import display_name
from Interface.InterfaceRecord import AddRecordWindow, EditRecordWindow


class RecordFormController:
    #===== Получение обработчиков от главного контроллера =====
    def __init__(self, parent, form_data, document_names, type_fields, on_add, on_update, on_delete):
        self.parent, self.form_data, self.document_names = parent, form_data, document_names
        self.type_fields = type_fields
        self.on_add, self.on_update, self.on_delete = on_add, on_update, on_delete

    #===== Открытие формы добавления записи =====
    def open_add(self, table, columns):
        try:
            fields, type_rows, defaults = self.form_data(table, columns)
            types = {f'{name} (ID: {ident})': (ident, name, uyais, fnn)
                     for ident, name, uyais, fnn in type_rows}
            window = AddRecordWindow(
                self.parent, table,
                [(display_name(c), 'Введите ' + display_name(c), required)
                 for c, required in fields],
                lambda: self.save(window, table, columns, types),
                type_names=list(types) if table == 'Product' else None,
                on_type_select=lambda name: self.fill_type(window, types.get(name)))
            if table == 'Product':
                window.set_fields({display_name(c): v for c, v in defaults.items()})
                entry = window.entries.get(display_name('UYAIS'))
                if entry:
                    entry.bind('<KeyRelease>', lambda _: self.fill_docs(window))
        except Exception as error:
            messagebox.showerror('Ошибка добавления', str(error), parent=self.parent)

    #===== Автозаполнение вида изделия =====
    def fill_type(self, window, selected):
        window.set_fields({display_name(c): v for c, v in
                           zip(self.type_fields, selected[1:] if selected else ('', '', ''))},
                          disabled=selected is not None)
        self.fill_docs(window)

    #===== Автозаполнение документов по УЯИС =====
    def fill_docs(self, window):
        entry = window.entries.get(display_name('UYAIS'))
        if entry:
            window.set_fields({display_name(c): v or '' for c, v in
                               self.document_names(entry.get()).items()})

    #===== Открытие формы редактирования записи =====
    def open_edit(self, table, columns, record):
        data = dict(zip(columns, record))
        protected = {'cargo_year'} if table == 'Product' else set()
        values = {'id': data['id'], **{display_name(c): v for c, v in data.items()
                                     if c != 'id' and c not in protected}}
        window = EditRecordWindow(
            self.parent, table, values,
            lambda: self.save(window, table, columns),
            lambda: self.delete(window, table))

    #===== Сохранение формы через переданный обработчик =====
    def save(self, window, table, columns, types=None):
        try:
            names = {display_name(c): c for c in columns}
            adding = types is not None
            values = {names[name]: value or None for name, value in window.get_values().items()
                      if name in names and (value or not adding)}
            if adding:
                selected = types.get(window.type_menu.get()) if table == 'Product' else None
                self.on_add(table, values, selected)
            else:
                self.on_update(table, window.record_id, values)
            window.destroy()
        except Exception as error:
            messagebox.showerror('Ошибка сохранения', str(error), parent=window)

    #===== Удаление записи после подтверждения пользователем =====
    def delete(self, window, table):
        if not messagebox.askyesno('Удаление записи',
                                   f'Удалить запись ID: {window.record_id}?', parent=window):
            return
        try:
            self.on_delete(table, window.record_id)
            window.destroy()
        except Exception as error:
            messagebox.showerror('Ошибка удаления', str(error), parent=window)