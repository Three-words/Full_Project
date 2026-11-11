
"""Данные этикеток: подготовка, проверка и сохранение в БД."""
from psycopg2.extras import Json
from Controllers.AlgorithmController import AlgorithmController as Algo
from Controllers.SQL import SQL
from GenerateQR.LabelRenderer import LabelRenderer, number, dimensions

#===== Схема БД и наборы этикеток =====
STANDARD = ('SVG_UII', 'SVG_FNN', 'SVG_Uniq_Marker', 'SVG_Single_Item_Package',
            'SVG_RE', 'SVG_RO', 'SVG_Passport')
DOCUMENTS = ('RE', 'RO', 'Passport')
TRANSPORT = 'SVG_Military_Cargo_Transport_Unit'
TRANSPORT_FIELDS = {
    'tkn': 'TKN', 'fnn': 'FNN', 'address': 'Address',
    'place_number': 'Cargo_place_number', 'place_count': 'Cargo_place_count',
    'sender': 'Organization_code', 'gross': 'Gross_weight', 'net': 'Net_weight'
}
DIMENSIONS = ('Width', 'Height', 'Depth')


class TemplateController:
    def __init__(self, bd, qr, dm, pdf417, code128):
        self.bd = bd
        self.renderer = LabelRenderer(qr, dm, pdf417, code128)
        self.skipped = []

    #===== Сохранение в Codes; используется обеими операциями генерации =====
    def save_product_codes(self, product_id, code_id, labels, payloads, replace=False):
        old = SQL.get_record(self.bd, 'Codes', code_id) if code_id else {}
        stored = dict((old or {}).get('Payloads') or {})
        if replace:
            stored = {name: codes for name, codes in stored.items() if name not in STANDARD}
            labels = {**{name: None for name in STANDARD if name in (old or {})}, **labels}
        stored.update(payloads)
        return SQL.save_product_codes(self.bd, product_id, code_id,
                                      {**labels, 'Payloads': Json(stored)})

    #===== Стандартный комплект; вызывается из MainController.generate =====
    def generate_product_labels(self, product_id, master=None):
        product = SQL.get_record(self.bd, 'Product', product_id)
        if product is None:
            raise ValueError('Изделие не найдено')
        if any(product.get(name) for name in DOCUMENTS):
            chars, _ = Algo.translation_maps(SQL.get_translations(self.bd))
            for name in DOCUMENTS:
                if product.get(name):
                    product[name + '_Translit'] = ''.join(
                        chars.get(char, char) for char in str(product[name]))
        labels, groups, self.skipped = self.renderer.render_product(product, master)
        if not labels:
            raise ValueError('Не удалось сформировать ни одного кода:\n' + '\n'.join(self.skipped))
        payloads = {name: [Algo.pack(fields).hex() for fields in variants]
                    for name, variants in groups.items()}
        try:
            self.save_product_codes(product_id, product['code_id'], labels, payloads, replace=True)
            self.bd.connection.commit()
        except Exception:
            self.bd.connection.rollback()
            raise
        return list(labels)

    #===== Загрузка готовых SVG; используется при просмотре и экспорте =====
    def load_saved_labels(self, product_id):
        record = SQL.get_record(self.bd, 'Product', product_id, 'code_id')
        if not record or record['code_id'] is None:
            raise ValueError('У изделия нет сгенерированных этикеток')
        codes = SQL.get_record(self.bd, 'Codes', record['code_id']) or {}
        labels = {name: content for name, content in codes.items()
                  if name.startswith('SVG_') and isinstance(content, str) and '<svg' in content[:200]}
        if not labels:
            raise ValueError('В Codes не найдены SVG-этикетки')
        return labels

    #===== Данные транспортной формы; MainController создаёт само окно =====
    def get_transport_form(self, product_id):
        product = SQL.get_record(self.bd, 'Product', product_id)
        if product is None:
            raise ValueError('Изделие не найдено')
        columns, rows = SQL.get_table_data(self.bd, 'Recipient')

        def options(column):
            index = next((i for i, name in enumerate(columns) if name.lower() == column.lower()
                          or column == 'Address' and 'address' in name.lower()), None)
            if index is None:
                raise ValueError('В Recipient нет столбца ' + column)
            return sorted({str(row[index]).strip() for row in rows if row[index]})

        values = {key: number(product[column]) if key in ('gross', 'net')
                  and product.get(column) not in (None, '') else product.get(column)
                  for key, column in TRANSPORT_FIELDS.items()}
        sizes = [product.get(name) for name in DIMENSIONS]
        values['dimensions'] = (dimensions(sizes) if all(
            value is not None and str(value).strip() for value in sizes) else '')
        return values, options('Address'), options('Code_organization')

    #===== Проверка полей; используется из generate_transport =====
    @staticmethod
    def validate_transport(data, product):
        data = dict(data)
        if not all(data.values()):
            raise ValueError('Заполните все поля этикетки')
        try:
            count, place = int(data['place_count']), int(data['place_number'])
            if not 1 <= place <= count:
                raise ValueError('Некорректный номер места')
            sizes = [value.strip() for value in data['dimensions'].replace('×', 'x').split('x')]
            if len(sizes) != 3 or any(float(value.replace(',', '.')) <= 0 for value in sizes):
                raise ValueError('Некорректные габариты в Product')
            if any(float(data[key].replace(',', '.')) < 0 for key in ('gross', 'net')):
                raise ValueError('Масса не может быть отрицательной')
        except (ValueError, TypeError) as error:
            raise ValueError('Неверные числовые параметры: ' + str(error)) from error
        data.update(gross=number(data['gross']), net=number(data['net']),
                    dimensions=dimensions(sizes), recipient_address=data['address'],
                    items_per_package=product.get('Items_per_package'))
        return data

    #===== Поля транспортного штрихкода для генерации и каталога =====
    @staticmethod
    def transport_fields(data):
        count = data.get('items_per_package')
        quantity = int(1 if count is None or count == '' else count)
        if quantity < 1:
            raise ValueError('Количество изделий в упаковке должно быть больше нуля')
        return [('J', data['tkn']), ('34V', data['recipient']), ('Q', str(quantity)),
                ('13Q', '{}/{}'.format(data['place_number'], data['place_count'])),
                ('28L', data['recipient_address']), ('68P', data['fnn']), ('24V', data['sender'])]

    #===== Генерация транспорта; вызывается из MainController.generate_transport =====
    def save_transport(self, product_id, values):
        product = SQL.get_record(self.bd, 'Product', product_id)
        if product is None:
            raise ValueError('Изделие не найдено')
        data = self.validate_transport(values, product)
        fields = self.transport_fields(data)
        label = self.renderer.render_transport(data, fields)
        payloads = {TRANSPORT: [('J' + str(data['tkn'])).encode().hex(),
                                Algo.pack([('J', data['tkn'])]).hex(),
                                ('68P' + str(data['fnn'])).encode().hex(),
                                Algo.pack([('68P', data['fnn'])]).hex(), Algo.pack(fields).hex()]}
        missing = {column: data[key].replace(',', '.') if key in ('gross', 'net') else data[key]
                   for key, column in TRANSPORT_FIELDS.items()
                   if column in product and not str(product[column] or '').strip()}
        try:
            SQL.update_record(self.bd, 'Product', product_id, missing, commit=False)
            self.save_product_codes(product_id, product['code_id'], {TRANSPORT: label}, payloads)
            self.bd.connection.commit()
        except Exception:
            self.bd.connection.rollback()
            raise
