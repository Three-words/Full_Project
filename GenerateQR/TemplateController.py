"""Комплекты этикеток: данные из БД, формирование и сохранение."""
from hashlib import sha256
from psycopg2.extras import Json
from Controllers.AlgorithmController import AlgorithmController as Algo
from Controllers.SQL import SQL
from GenerateQR.LabelRenderer import LabelRenderer, number, dimensions
from GenerateQR.QRController import QRController
from GenerateQR.DataMatrixController import DataMatrixController
from GenerateQR.PDF417Controller import PDF417Controller
from GenerateQR.Code128Controller import Code128Controller
from GenerateQR import SVGController as svg

LEGACY = ('SVG_UII', 'SVG_FNN')
STANDARD = ('SVG_Uniq_Marker', 'SVG_Single_Item_Package',
            'SVG_RE', 'SVG_RO', 'SVG_Passport')
DOCUMENTS = ('RE', 'RO', 'Passport')
TRANSPORT = 'SVG_Military_Cargo_Transport_Unit'
TRANSPORT_FIELDS = {
    'tkn': 'TKN', 'fnn': 'FNN', 'address': 'Address',
    'place_number': 'Cargo_place_number', 'place_count': 'Cargo_place_count',
    'sender': 'Organization_code', 'gross': 'Gross_weight', 'net': 'Net_weight'
}
DIMENSIONS = ('Width', 'Height', 'Depth')

#===== Данные только для демонстрации макетов =====
SAMPLE = dict(UII='1234567890', FNN='12345678', Serial_number='123456789',
              UYAIS='123456', Issuance_agency_code='45', Organization_code='123',
              Cargo_place_count='2', Items_per_package=1, RE_Translit='RE-1234',
              RO_Translit='RO-1234', Passport_Translit='PASS-1234')
TRANSPORT_SAMPLE = dict(tkn='1234567890', fnn='12345678', sender='123', recipient='456',
                        recipient_address='MOSCOW', place_number=1, place_count=2,
                        items_per_package=1, gross='12,5', net='11', dimensions='40x30x20')


class TemplateController:
    #===== Создание подсистемы генерации =====
    def __init__(self, bd):
        self.bd = bd
        self.renderer = LabelRenderer(QRController(), DataMatrixController(),
                                      PDF417Controller(), Code128Controller())
        self.skipped = []

    #===== Запись SVG и payload в одну запись Codes =====
    def save_product_codes(self, product_id, code_id, labels, payloads, replace=False):
        old = SQL.get_record(self.bd, 'Codes', code_id) if code_id else {}
        stored = {k: v for k, v in dict((old or {}).get('Payloads') or {}).items()
                  if k not in LEGACY}
        if replace:
            stored = {k: v for k, v in stored.items() if k not in STANDARD}
            labels = {**{k: None for k in STANDARD if k in (old or {})}, **labels}
        stored.update({k: v for k, v in payloads.items() if k not in LEGACY})
        return SQL.save_product_codes(self.bd, product_id, code_id,
                                      {**labels, 'Payloads': Json(stored)})

    #===== Генерация комплекта для выбранного изделия =====
    def generate_product_labels(self, product_id, master=None):
        product = SQL.get_record(self.bd, 'Product', product_id)
        if product is None:
            raise ValueError('Изделие не найдено')
        if any(product.get(k) for k in DOCUMENTS):
            chars, _ = Algo.translation_maps(SQL.get_translations(self.bd))
            for name in DOCUMENTS:
                if product.get(name):
                    product[name + '_Translit'] = ''.join(
                        chars.get(c, c) for c in str(product[name]))

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

    #===== Генерация только выбранного демонстрационного макета =====
    def preview_label(self, key, master=None):
        if key == 'transport':
            return self.renderer.render_transport(TRANSPORT_SAMPLE,
                                                  self.transport_fields(TRANSPORT_SAMPLE))
        if key == 'package_many':
            return self.renderer.render_package({**SAMPLE, 'Items_per_package': 5}, master)[0]
        labels, _, errors = self.renderer.render_product(SAMPLE, master, only=key)
        if key not in labels:
            raise ValueError('; '.join(errors) or 'Шаблон недоступен')
        return labels[key]

    #===== Постоянное имя столбца пользовательского шаблона =====
    @staticmethod
    def custom_column(name):
        return 'SVG_Custom_' + sha256(name.encode('utf-8')).hexdigest()[:24]

    #===== Создание и сохранение этикетки пользовательского шаблона =====
    def save_custom(self, service, name, product_id):
        template = service.all_templates().get(name)
        if template is None:
            raise ValueError('Шаблон не найден: ' + name)
        product = SQL.get_record(self.bd, 'Product', product_id)
        if not product:
            raise ValueError('Изделие не найдено')
        label = service.render(template, product_id)
        column = self.custom_column(name)
        payloads = [service.payload(e, product_id).hex() for e in template['elements']
                    if e['kind'] == 'code']
        try:
            SQL.ensure_custom_label_column(self.bd, column)
            self.save_product_codes(product_id, product['code_id'], {column: label},
                                    {column: payloads})
            self.bd.connection.commit()
        except Exception:
            self.bd.connection.rollback()
            raise
        return column

    #===== Получение ранее сохранённых этикеток =====
    def load_saved_labels(self, product_id):
        record = SQL.get_record(self.bd, 'Product', product_id, 'code_id')
        if not record or record['code_id'] is None:
            raise ValueError('У изделия нет сгенерированных этикеток')
        codes = SQL.get_record(self.bd, 'Codes', record['code_id']) or {}
        labels = {k: v for k, v in codes.items()
                  if k.startswith('SVG_') and k not in LEGACY
                  and isinstance(v, str) and '<svg' in v[:200]}
        if not labels:
            raise ValueError('В Codes не найдены SVG-этикетки')
        return labels

    #===== Экспорт SVG без повторной генерации =====
    def export_saved_labels(self, product_id, folder):
        return svg.export(self.load_saved_labels(product_id), folder, product_id)

    #===== Получение полей транспортной формы и справочников =====
    def get_transport_form(self, product_id):
        product = SQL.get_record(self.bd, 'Product', product_id)
        if product is None:
            raise ValueError('Изделие не найдено')
        columns, rows = SQL.get_table_data(self.bd, 'Recipient')

        #===== Значения справочника по названию поля =====
        def options(column):
            index = next((i for i, name in enumerate(columns)
                          if name.lower() == column.lower()
                          or column == 'Address' and 'address' in name.lower()), None)
            if index is None:
                raise ValueError('В Recipient нет столбца ' + column)
            return sorted({str(row[index]).strip() for row in rows if row[index]})

        values = {key: product.get(column) for key, column in TRANSPORT_FIELDS.items()}
        for key in ('gross', 'net'):
            if values[key] not in (None, ''):
                values[key] = number(values[key])
        sizes = [product.get(name) for name in DIMENSIONS]
        values['dimensions'] = dimensions(sizes) if all(
            x is not None and str(x).strip() for x in sizes) else ''
        return values, options('Address'), options('Code_organization')

    #===== Проверка введённых транспортных параметров перед записью =====
    @staticmethod
    def validate_transport(data, product):
        data = dict(data)
        required = ('tkn', 'recipient', 'address', 'sender', 'place_count',
                    'place_number', 'dimensions', 'gross', 'net')
        if any(data.get(k) is None or not str(data[k]).strip() for k in required):
            raise ValueError('Заполните все поля этикетки')
        try:
            count, place = int(data['place_count']), int(data['place_number'])
            if not 1 <= place <= count:
                raise ValueError('Некорректный номер места')
            sizes = [part.strip() for part in data['dimensions'].replace('×', 'x').split('x')]
            if len(sizes) != 3 or any(float(s.replace(',', '.')) <= 0 for s in sizes):
                raise ValueError('Некорректные габариты в Product')
            if any(float(str(data[k]).replace(',', '.')) < 0 for k in ('gross', 'net')):
                raise ValueError('Масса не может быть отрицательной')
        except (ValueError, TypeError) as error:
            raise ValueError('Неверные числовые параметры: ' + str(error)) from error
        data.update(gross=number(data['gross']), net=number(data['net']),
                    dimensions=dimensions(sizes), recipient_address=data['address'],
                    items_per_package=product.get('Items_per_package'))
        return data

    #===== Формирование полей транспортного штрихкода =====
    @staticmethod
    def transport_fields(data):
        value = data.get('items_per_package')
        quantity = int(1 if value is None or value == '' else value)
        if quantity < 1:
            raise ValueError('Количество изделий в упаковке должно быть больше нуля')
        fields = [('J', data['tkn']), ('34V', data['recipient']), ('Q', str(quantity)),
                  ('13Q', '{}/{}'.format(data['place_number'], data['place_count'])),
                  ('28L', data['recipient_address'])]
        if data.get('fnn') is not None and str(data['fnn']).strip():
            fields.append(('68P', data['fnn']))
        return fields + [('24V', data['sender'])]

    #===== Сохранение транспортной этикетки и её payload =====
    def save_transport(self, product_id, values):
        product = SQL.get_record(self.bd, 'Product', product_id)
        if product is None:
            raise ValueError('Изделие не найдено')
        data = self.validate_transport(values, product)
        fields = self.transport_fields(data)
        label = self.renderer.render_transport(data, fields)
        singles = [('J', data['tkn'])]
        if data.get('fnn') is not None and str(data['fnn']).strip():
            singles.append(('68P', data['fnn']))
        payloads = {TRANSPORT: [v for prefix, value in singles
                                for v in ((prefix + str(value)).encode().hex(),
                                          Algo.pack([(prefix, value)]).hex())]
                    + [Algo.pack(fields).hex()]}
        missing = {column: data[key].replace(',', '.') if key in ('gross', 'net') else data[key]
                   for key, column in TRANSPORT_FIELDS.items()
                   if column in product and data[key] not in (None, '')
                   and not str(product[column] or '').strip()}
        try:
            SQL.update_record(self.bd, 'Product', product_id, missing, commit=False)
            self.save_product_codes(product_id, product['code_id'], {TRANSPORT: label}, payloads)
            self.bd.connection.commit()
        except Exception:
            self.bd.connection.rollback()
            raise