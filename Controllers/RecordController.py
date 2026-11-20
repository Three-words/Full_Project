"""Операции с записями: правила изделий, идентификаторы и работа с БД."""
from datetime import date
import re
from Controllers.AlgorithmController import AlgorithmController as Algo
from Controllers.SQL import SQL

TYPE_FIELDS = ('Product_name', 'UYAIS', 'FNN')
DEFAULTS = {'Cargo_place_count': 1, 'Cargo_place_number': 1, 'Items_per_package': 1}
HIDDEN = {'id', 'UII', 'TKN', 'code_id', 'product_type_id', 'cargo_year'}
RECALC_FIELDS = {'UYAIS', 'Serial_number', 'product_serial_number',
                 'Issuance_agency_code', 'Organization_code', 'cargo_year'}
ORGANIZATION_NAME = 'АО Аэроэлектромаш'


class RecordController:
    #===== Подключение источника данных =====
    def __init__(self, bd):
        self.bd = bd

    #===== Получение записи =====
    def get_record(self, table, record_id):
        return SQL.get_record(self.bd, table, record_id)

    #===== Подготовка полей, типов и значений для формы =====
    def form_data(self, table, columns):
        product = table == 'Product'
        excluded = HIDDEN | ({'product_serial_number'} if product else set())
        required = set(SQL.get_required_columns(self.bd, table)) - {'FNN', 'Serial_number'}
        fields = [(name, name in required or product and name in TYPE_FIELDS[:2])
                  for name in columns if name not in excluded and not name.endswith('_id')]
        types = SQL.get_product_types(self.bd) if product else []
        defaults = {k: v for k, v in DEFAULTS.items() if k in columns} if product else {}
        if product and ORGANIZATION_NAME:
            codes = SQL.get_record(self.bd, 'Recipient', ORGANIZATION_NAME,
                                   ('Code_organization', 'Issuing_agency_code'),
                                   key='Name_of_organization')
            if not codes or any(v is None for v in codes.values()):
                raise ValueError('Организация не найдена или её коды не заполнены')
            defaults.update(Organization_code=codes['Code_organization'],
                            Issuance_agency_code=codes['Issuing_agency_code'])
        return fields, types, defaults

    #===== Проверка точной длины числовых идентификаторов =====
    @staticmethod
    def validate_numbers(values):
        lengths = {'Serial_number': 6, 'FNN': 13, 'product_serial_number': 5}
        for key, length in lengths.items():
            if key not in values:
                continue
            value = values[key]
            if value is None or value == '':
                if key in ('FNN', 'Serial_number'):
                    values[key] = None
                    continue
                if key == 'product_serial_number':
                    raise ValueError('Номер груза должен содержать ровно 5 цифр')
                raise ValueError('Серийный номер должен содержать ровно 6 цифр')
            if not re.fullmatch(r'[0-9]{%d}' % length, str(value)):
                title = {'Serial_number': 'Серийный номер', 'FNN': 'ФНН',
                         'product_serial_number': 'Номер груза'}[key]
                raise ValueError('{} должен содержать ровно {} цифр'.format(title, length))

    #===== Расчёт названий документов по УЯИС =====
    @staticmethod
    def document_names(uyais):
        return Algo.generate_docs(uyais)

    #===== Добавление записи в выбранную таблицу =====
    def add_record(self, table, values, selected_type=None):
        if table == 'Product':
            return self.add_product(values, selected_type)
        if table == 'ProductType':
            values = dict(values)
            self.validate_numbers(values)
        return SQL.add_record(self.bd, table, values, commit=False)

    #===== Изменение записи в выбранной таблице =====
    def update_record(self, table, record_id, values):
        if table == 'Product':
            return self.update_product(record_id, values)
        if table == 'ProductType':
            values = dict(values)
            self.validate_numbers(values)
        SQL.update_record(self.bd, table, record_id, values, commit=False)

    #===== Удаление записи в выбранной таблице =====
    def delete_record(self, table, record_id):
        if table == 'Product':
            return self.delete_product(record_id)
        SQL.delete_record(self.bd, table, record_id, commit=False)

    #===== Сохранение примечаний отдельно от идентификаторов =====
    def save_notes(self, record_id, text):
        SQL.update_record(self.bd, 'Product', record_id, {'Notes': text or None}, commit=False)

    #===== Расчёт идентификаторов и документов изделия =====
    def recalculate_product(self, record_id, year=None, product=None):
        columns = ('UYAIS', 'Serial_number', 'product_serial_number',
                   'Issuance_agency_code', 'Organization_code', 'TKN', 'cargo_year')
        row = product if product is not None else SQL.get_record(self.bd, 'Product', record_id)
        if row is None:
            raise ValueError('Изделие не найдено')
        uyais, serial, number, agency, org, old_tkn, cargo_year = (row.get(c) for c in columns)
        result = Algo.generate_docs(uyais)
        if agency and org:
            chars, ids = Algo.translation_maps(SQL.get_translations(self.bd))
            digit = str(cargo_year or year)[-1] if cargo_year or year else None
            if number and digit is None:
                raise ValueError('У изделия не указан год присвоения номера груза')
            result['UII'] = Algo.generate_uii(uyais, serial, agency, org, chars) if uyais and serial else None
            result['TKN'] = Algo.generate_tkn(number, agency, org, ids, digit) if number else None
        else:
            result.update(UII=None, TKN=None)
        SQL.update_record(self.bd, 'Product', record_id, result, commit=False)

    #===== Создание изделия без автоматического номера груза =====
    def add_product(self, values, selected_type=None):
        values = dict(values)
        values.pop('UII', None)
        values.pop('TKN', None)
        values.pop('cargo_year', None)
        if selected_type is not None:
            type_id = selected_type[0]
            data = SQL.get_record(self.bd, 'ProductType', type_id, TYPE_FIELDS)
            if data is None:
                raise ValueError('Выбранный вид изделия не найден')
            values.update(data)
        else:
            data = [values.get(name) for name in TYPE_FIELDS]
            if not all(data[:2]):
                raise ValueError('Укажите наименование и УЯИС')
            values['FNN'] = values.get('FNN') or None
        values['Serial_number'] = values.get('Serial_number') or None
        self.validate_numbers(values)
        if selected_type is None:
            type_id = SQL.get_or_create_product_type(self.bd,
                [values.get(name) for name in TYPE_FIELDS])
        # Номер груза и год присваиваются только отдельной командой.
        values.pop('product_serial_number', None)
        ident = SQL.add_record(self.bd, 'Product',
                               {**values, 'product_type_id': type_id,
                                'product_serial_number': None, 'cargo_year': None}, commit=False)
        self.recalculate_product(ident)
        return ident

    #===== Однократное присвоение номера груза выбранному изделию =====
    def assign_cargo_number(self, record_id):
        # Блокировка строки защищает от повторного присвоения в другом сеансе.
        query = 'SELECT id FROM public."Product" WHERE id=%s FOR UPDATE'
        if not SQL._query(self.bd, query, (record_id,)).fetchone():
            raise ValueError('Изделие не найдено')
        product = SQL.get_record(self.bd, 'Product', record_id)
        if product.get('product_serial_number') is not None:
            raise ValueError('Номер груза уже присвоен этому изделию')
        year = date.today().year
        agency, org = product.get('Issuance_agency_code'), product.get('Organization_code')
        if not agency or not org:
            raise ValueError('Для присвоения номера заполните коды организации и органа выдачи')
        _, identifiers = Algo.translation_maps(SQL.get_translations(self.bd))
        number = 0
        while True:
            number = SQL.next_serial(self.bd, year, after=number)
            if number is None:
                raise ValueError('В {} году не осталось свободных номеров груза'.format(year))
            tkn = Algo.generate_tkn(number, agency, org, identifiers, str(year)[-1])
            if not SQL.tkn_exists(self.bd, product['UYAIS'], tkn):
                break
        SQL.update_record(self.bd, 'Product', record_id,
                          {'product_serial_number': '{:05d}'.format(number),
                           'cargo_year': year}, commit=False)
        self.recalculate_product(record_id)
        return '{:05d}'.format(number)

    #===== Обновление только изменённых полей и зависимых идентификаторов =====
    def update_product(self, record_id, values):
        old = self.get_record('Product', record_id)
        if old is None:
            raise ValueError('Изделие не найдено')
        changes = {k: v for k, v in values.items() if k not in ('UII', 'TKN', 'cargo_year')
                   and str(v if v is not None else '') != str(old.get(k) if old.get(k) is not None else '')}
        if not changes:
            return
        if 'product_serial_number' in changes:
            number = changes['product_serial_number']
            if number in (None, ''):
                changes.update(product_serial_number=None, cargo_year=None)
            else:
                changes['cargo_year'] = old.get('cargo_year') or date.today().year
        self.validate_numbers(changes)
        if any(k in changes for k in TYPE_FIELDS):
            fields = [changes.get(k, old.get(k)) for k in TYPE_FIELDS]
            if not all(fields[:2]):
                raise ValueError('Укажите наименование и УЯИС')
            changes['product_type_id'] = SQL.get_or_create_product_type(self.bd, fields)
        SQL.update_record(self.bd, 'Product', record_id, changes, commit=False)
        if RECALC_FIELDS.intersection(changes):
            self.recalculate_product(record_id, product={**old, **changes})
        old_type = old.get('product_type_id')
        if old_type and old_type != changes.get('product_type_id', old_type):
            SQL.delete_unused_type(self.bd, old_type)

    #===== Удаление изделия и неиспользуемого вида =====
    def delete_product(self, record_id):
        row = SQL.get_record(self.bd, 'Product', record_id, 'product_type_id')
        SQL.delete_record(self.bd, 'Product', record_id, commit=False)
        if row and row['product_type_id'] is not None:
            SQL.delete_unused_type(self.bd, row['product_type_id'])