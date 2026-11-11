
"""Записи: формы, сохранение и вычисляемые идентификаторы изделия."""
from datetime import date
from tkinter import messagebox
from Controllers.AlgorithmController import AlgorithmController as Algo
from Controllers.SQL import SQL
from Interface.ColumnNames import display_name
from Interface.InterfaceRecord import AddRecordWindow, EditRecordWindow

#===== Настройки формы изделия =====
TYPE_FIELDS = ('Product_name', 'UYAIS', 'FNN')
DEFAULTS = {'Cargo_place_count': 1, 'Cargo_place_number': 1, 'Items_per_package': 1}
ORGANIZATION_NAME = ''  


class RecordController:
    def __init__(self, bd, parent, on_change):
        self.bd, self.parent, self.on_change = bd, parent, on_change

    #===== Чтение и примечания; вызываются из MainController =====
    def get_record(self, table, record_id):
        return SQL.get_record(self.bd, table, record_id)

    def save_notes(self, record_id, text):
        SQL.update_record(self.bd, 'Product', record_id, {'Notes': text or None})

    #===== Общая обработка форм; используется при сохранении любой таблицы =====
    @staticmethod
    def form_values(window, columns, adding=False):
        names = {display_name(column): column for column in columns}
        return {names[label]: value for label, value in window.get_values().items()
                if label in names and (value or not adding)}

    def finish_form(self, window):
        self.bd.connection.commit()
        window.destroy()
        self.on_change()

    #===== Открытие формы добавления; кнопка передаёт данные в save_record =====
    def open_add_record(self, table, columns):
        try:
            product = table == 'Product'
            excluded = {'id', 'product_type_id', 'product_serial_number'} if product else {'id'}
            required = set(SQL.get_required_columns(self.bd, table))
            fields = [(display_name(c), 'Введите ' + display_name(c),
                       c in required or product and c in TYPE_FIELDS)
                      for c in columns if c not in excluded]
            types = ({f'{name} (ID: {ident})': (ident, name, uyais, fnn)
                      for ident, name, uyais, fnn in SQL.get_product_types(self.bd)} if product else {})
            defaults = dict(DEFAULTS) if product else {}
            if product and ORGANIZATION_NAME:
                codes = SQL.get_record(self.bd, 'Recipient', ORGANIZATION_NAME,
                                       ('Code_organization', 'Issuing_agency_code'),
                                       key='Name_of_organization')
                if not codes or any(value is None for value in codes.values()):
                    raise ValueError('Организация не найдена или её коды не заполнены')
                defaults.update(Organization_code=codes['Code_organization'],
                                Issuance_agency_code=codes['Issuing_agency_code'])
            window = AddRecordWindow(self.parent, table, fields,
                                     lambda: self.save_record(window, table, columns, types),
                                     type_names=list(types) if product else None,
                                     on_type_select=lambda name: self.fill_type(window, types.get(name)))
            if product:
                window.set_fields({display_name(c): value for c, value in defaults.items() if c in columns})
                entry = window.entries.get(display_name('UYAIS'))
                if entry:
                    entry.bind('<KeyRelease>', lambda _: self.fill_docs(window))
        except Exception as error:
            self.bd.connection.rollback()
            messagebox.showerror('Ошибка', f'Не удалось открыть добавление записи:\n{error}')

    #===== Автозаполнение; вызывается при выборе ProductType и изменении УЯИС =====
    def fill_type(self, window, data=None):
        window.set_fields({display_name(key): value for key, value in
                           zip(TYPE_FIELDS, data[1:] if data else ('', '', ''))},
                          disabled=data is not None)
        self.fill_docs(window)

    @staticmethod
    def fill_docs(window):
        entry = window.entries.get(display_name('UYAIS'))
        if entry:
            window.set_fields({display_name(key): value or ''
                               for key, value in Algo.generate_docs(entry.get()).items()})

    #===== Редактирование: вызывается двойным кликом по строке =====
    def open_edit_record(self, table, columns, record):
        row = dict(zip(columns, record))
        values = {'id': row['id'], **{display_name(key): value for key, value in row.items()
                                    if key != 'id'}}
        window = EditRecordWindow(self.parent, table, values,
                                  lambda: self.save_record(window, table, columns),
                                  lambda: self.save_record(window, table, columns, delete=True))

    #===== Единый обработчик добавления, редактирования и удаления записей =====
    def save_record(self, window, table, columns, types=None, delete=False):
        adding = types is not None
        try:
            if delete:
                if table == 'Product':
                    self.delete_product(window.record_id)
                else:
                    SQL.delete_record(self.bd, table, window.record_id, commit=False)
            else:
                values = self.form_values(window, columns, adding)
                if adding:
                    if table == 'Product':
                        self.add_product(values, types.get(window.type_menu.get()))
                    else:
                        SQL.add_record(self.bd, table, values, commit=False)
                else:
                    values = {key: value or None for key, value in values.items()}
                    if table == 'Product':
                        self.update_product(window.record_id, values)
                    else:
                        SQL.update_record(self.bd, table, window.record_id, values, commit=False)
            self.finish_form(window)
        except Exception as error:
            self.bd.connection.rollback()
            action = 'удалить' if delete else 'добавить' if adding else 'обновить'
            messagebox.showerror('Ошибка', f'Не удалось {action} запись:\n{error}')

    #===== УИИ, ТКН и документы; вызывается после создания и изменения изделия =====
    def recalculate_product(self, record_id, year=None):
        columns = ('UYAIS', 'Serial_number', 'product_serial_number',
                   'Issuance_agency_code', 'Organization_code', 'TKN')
        row = SQL.get_record(self.bd, 'Product', record_id, columns)
        if row is None:
            raise ValueError('Изделие не найдено')
        uyais, serial, number, agency, org, old_tkn = (row[key] for key in columns)
        values = Algo.generate_docs(uyais)
        if agency and org:
            chars, ids = Algo.translation_maps(SQL.get_translations(self.bd))
            digit = str(year)[-1] if year else (old_tkn[-7] if old_tkn and len(old_tkn) >= 7
                                               else str(date.today().year)[-1])
            values['UII'] = Algo.generate_uii(uyais, serial, agency, org, chars) if uyais and serial else None
            values['TKN'] = Algo.generate_tkn(number, agency, org, ids, digit) if number else None
        else:
            values.update(UII=None, TKN=None)
        SQL.update_record(self.bd, 'Product', record_id, values, commit=False)

    #===== Product и ProductType; используются единым обработчиком save_record =====
    def add_product(self, values, selected_type=None):
        if selected_type is not None:
            type_id = selected_type[0]
            data = SQL.get_record(self.bd, 'ProductType', type_id, TYPE_FIELDS)
            if data is None:
                raise ValueError('Выбранный вид изделия не найден')
            values.update(data)
        else:
            data = [values.get(name) for name in TYPE_FIELDS]
            if not all(data):
                raise ValueError('Укажите наименование, УЯИС и ФНН')
            type_id = SQL.get_or_create_product_type(self.bd, data)
        year = date.today().year
        number = SQL.next_serial(self.bd, year)
        if number > 99999:
            raise ValueError('На этот год закончились пятизначные номера')
        values.update(product_type_id=type_id, product_serial_number=f'{number:05d}')
        for name in ('UII', 'TKN'):
            values.pop(name, None)
        ident = SQL.add_record(self.bd, 'Product', values, commit=False)
        self.recalculate_product(ident, year)
        return ident

    def update_product(self, record_id, values):
        old = SQL.get_record(self.bd, 'Product', record_id)
        if old is None:
            raise ValueError('Изделие не найдено')
        for name in ('UII', 'TKN'):
            values.pop(name, None)
        if any(key in values and values[key] != old.get(key) for key in TYPE_FIELDS):
            fields = [values.get(key, old.get(key)) for key in TYPE_FIELDS]
            if not all(fields):
                raise ValueError('Укажите наименование, УЯИС и ФНН')
            values['product_type_id'] = SQL.get_or_create_product_type(self.bd, fields)
        SQL.update_record(self.bd, 'Product', record_id, values, commit=False)
        self.recalculate_product(record_id)
        old_type = old.get('product_type_id')
        if old_type and old_type != values.get('product_type_id', old_type):
            SQL.delete_unused_type(self.bd, old_type)

    def delete_product(self, record_id, commit=False):
        row = SQL.get_record(self.bd, 'Product', record_id, 'product_type_id')
        SQL.delete_record(self.bd, 'Product', record_id, commit=False)
        if row and row['product_type_id'] is not None:
            SQL.delete_unused_type(self.bd, row['product_type_id'])
        if commit:
            self.bd.connection.commit()
