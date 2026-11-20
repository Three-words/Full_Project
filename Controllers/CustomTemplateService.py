"""Данные, сохранение и SVG пользовательских этикеток, без зависимостей от окна."""
import json
from html import escape
from pathlib import Path
from tkinter import font as tkfont
from xml.etree import ElementTree as ET

from Controllers.SQL import SQL
from Controllers.AlgorithmController import AlgorithmController as Algo
from GenerateQR import SVGController as svg
from GenerateQR.QRController import QRController
from GenerateQR.DataMatrixController import DataMatrixController
from GenerateQR.PDF417Controller import PDF417Controller
from GenerateQR.Code128Controller import Code128Controller


class CustomTemplateService:
    TYPES = {'QR': QRController, 'DataMatrix': DataMatrixController,
             'PDF417': PDF417Controller, 'Code128': Code128Controller}
    FILE = Path(__file__).resolve().parents[1] / 'JSON' / 'custom_label_templates.json'
    DOCUMENTS = ('RE', 'RO', 'Passport')
    SETTINGS = {'QR': ('MODULE', 'QUIET', 'ERROR'),
                'DataMatrix': ('MODULE', 'QUIET'),
                'PDF417': ('MODULE', 'QUIET', 'HEIGHT', 'COLUMNS', 'ECC'),
                'Code128': ('MODULE', 'QUIET', 'HEIGHT')}

    #===== Подключение БД и генераторов =====
    def __init__(self, bd):
        self.bd = bd
        self.generators = {name: cls() for name, cls in self.TYPES.items()}

    #===== Получение списка столбцов из схемы БД =====
    def columns(self, table):
        if table not in SQL.get_tables(self.bd):
            raise ValueError('Таблица недоступна: ' + table)
        query = ('SELECT column_name FROM information_schema.columns '
                 'WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position')
        return [row[0] for row in SQL._query(self.bd, query, ('public', table)).fetchall()]

    #===== Чтение идентификаторов из Document_Ident =====
    def identifiers(self):
        columns, rows = SQL.get_table_data(self.bd, 'Document_Ident')
        names = [column for column in columns if column.lower() != 'id']
        if len(names) < 2:
            raise ValueError('Document_Ident должна содержать описание и идентификатор')
        description, identifier = names[0], names[1]
        return [(str(row[columns.index(identifier)]), str(row[columns.index(description)]))
                for row in rows if row[columns.index(identifier)] is not None]

    #===== Список сохранённых шаблонов =====
    def all_templates(self):
        if not self.FILE.exists():
            return {}
        data = json.loads(self.FILE.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}

    #===== Проверка размеров и размещения элементов =====
    def validate(self, template):
        width, height = float(template['width']), float(template['height'])
        if not 10 <= width <= 500 or not 10 <= height <= 500:
            raise ValueError('Размер этикетки должен быть от 10 до 500 мм')
        if not template['elements']:
            raise ValueError('Добавьте хотя бы один элемент')
        for element in template['elements']:
            x, y = float(element['x']), float(element['y'])
            w, h = float(element['w']), float(element['h'])
            if min(x, y, w, h) < 0 or x + w > width or y + h > height:
                raise ValueError('Элемент выходит за пределы этикетки')
            if element['kind'] == 'code' and (not element.get('fields') or not w or not h):
                raise ValueError('Заполните поля каждого штрихкода и рассчитайте его размер')
            if element['kind'] == 'text' and (not w or not h):
                raise ValueError('Размер текстового блока должен быть положительным')
            if element['kind'] == 'line' and not (w or h):
                raise ValueError('Линия должна иметь длину')
            if element['kind'] in ('text', 'line') and float(element.get('stroke', 0)) < 0:
                raise ValueError('Толщина линий не может быть отрицательной')
        return width, height

    #===== Сохранение шаблона в JSON без изменений БД =====
    def save(self, template):
        self.validate(template)
        name = str(template['name']).strip()
        if not name:
            raise ValueError('Укажите название шаблона')
        templates = self.all_templates()
        templates[name] = template
        temp = self.FILE.with_suffix('.tmp')
        temp.write_text(json.dumps(templates, ensure_ascii=False, indent=2), encoding='utf-8')
        temp.replace(self.FILE)

    #===== Получение значений выбранной таблицы для изделия =====
    def record(self, table, product):
        if table == 'Product':
            return product
        columns = self.columns(table)
        if 'product_id' in columns:
            return SQL.get_record(self.bd, table, product['id'], key='product_id') or {}
        key = next((c for c in product if c.endswith('_id') and
                    c[:-3].replace('_', '').casefold() == table.replace('_', '').casefold()), None)
        if key and product.get(key) is not None:
            return SQL.get_record(self.bd, table, product[key]) or {}
        raise ValueError('Для таблицы {} нет связи с Product'.format(table))

    #===== Демонстрационное значение без обращения к БД =====
    @staticmethod
    def sample_value(column):
        samples = {'FNN': '1234567890123', 'UII': '1234567',
                   'TKN': '1234567890123', 'Serial_number': '123456',
                   'product_serial_number': '00001', 'UYAIS': '123456',
                   'Product_name': 'ОБРАЗЕЦ', 'Notes': 'ПРИМЕР'}
        return samples.get(column, '123456')

    #===== Получение компонентов и транслитерация значений =====
    def fields(self, product_id, fields):
        if product_id is None:
            return [(f['identifier'], str(f['literal']) if f.get('literal') is not None
                     else self.sample_value(f['column'])) for f in fields]
        product = SQL.get_record(self.bd, 'Product', product_id)
        if not product:
            raise ValueError('Выберите существующее изделие')
        records, mapping, result = {'Product': product}, None, []
        for field in fields:
            if field.get('literal') is not None:
                value = str(field['literal'])
                translit = field.get('translit', False)
            else:
                table, column = field['table'], field['column']
                if table not in records:
                    records[table] = self.record(table, product)
                value = records[table].get(column)
                if value is None or not str(value).strip():
                    raise ValueError('Нет значения: {}.{}'.format(table, column))
                value = str(value).strip()
                translit = field.get('translit', column in self.DOCUMENTS)
            if translit:
                if mapping is None:
                    mapping, _ = Algo.translation_maps(SQL.get_translations(self.bd))
                value = ''.join(mapping.get(char, char) for char in value)
            result.append((field['identifier'], value))
        return result

    #===== Формирование строки стандартным алгоритмом с разделителями =====
    def payload(self, element, product_id):
        return Algo.pack(self.fields(product_id, element['fields']))

    #===== Настройка существующего генератора без изменения общих классов =====
    def generator(self, element):
        kind = element['code_type']
        generator = self.TYPES[kind]()
        settings = element.get('settings') or {}
        for key in self.SETTINGS[kind]:
            if key not in settings or settings[key] in ('', None):
                continue
            value = settings[key]
            if key in ('QUIET', 'COLUMNS', 'ECC') and kind != 'Code128' and (key != 'QUIET' or kind in ('QR', 'DataMatrix')):
                value = int(value)
            elif key == 'ERROR':
                if str(value) not in ('L', 'M', 'Q', 'H'):
                    raise ValueError('Недопустимый уровень коррекции QR')
                value = str(value)
            else:
                value = float(value)
            if isinstance(value, (int, float)) and value <= 0 and key != 'ECC':
                raise ValueError('Параметр {} должен быть положительным'.format(key))
            setattr(generator, key, value)
        if kind == 'PDF417' and not 0 <= generator.ECC <= 8:
            raise ValueError('PDF417 ECC: допустимо от 0 до 8')
        return generator

    #===== Генерация кода и получение его естественных размеров =====
    def build_code(self, element, product_id):
        fields = element.get('fields', [])
        if not fields:
            raise ValueError('Добавьте хотя бы одно поле штрихкода')
        prepared = self.fields(product_id, fields)
        generator = self.generator(element)
        kind = element['code_type']
        code = generator.create(prepared)
        if kind in ('QR', 'DataMatrix'):
            return code, code.full_mm, code.full_mm
        _, _, width, height = map(float, ET.fromstring(code).get('viewBox').split())
        return code, width, height

    #===== Перенос текста по ширине с сохранением ручных переносов =====
    @staticmethod
    def wrap_text(text, width, measure):
        lines = []
        for paragraph in str(text).split('\n'):
            if not paragraph:
                lines.append('')
                continue
            line = ''
            for word in paragraph.split(' '):
                candidate = (line + ' ' + word) if line else word
                if measure(candidate) <= width:
                    line = candidate
                    continue
                if line:
                    lines.append(line)
                    line = ''
                for char in word:
                    if line and measure(line + char) > width:
                        lines.append(line)
                        line = ''
                    line += char
            lines.append(line)
        return lines

    #===== Получение произвольного значения для текстовой подписи =====
    def text_value(self, product_id, field):
        if product_id is None:
            return self.sample_value(field['column'])
        product = SQL.get_record(self.bd, 'Product', product_id)
        if not product:
            raise ValueError('Выберите существующее изделие')
        table, column = field['table'], field['column']
        record = self.record(table, product)
        value = record.get(column)
        return '' if value is None else str(value)

    #===== Обновление размера элемента без масштабирования штрихкода =====
    def size_code(self, element, product_id):
        _, width, height = self.build_code(element, product_id)
        element['w'], element['h'] = round(width, 6), round(height, 6)

    #===== Создание SVG по правилам выбранного шаблона =====
    def render(self, template, product_id=None):
        # Размеры кодов пересчитываются по актуальным данным до проверки геометрии.
        codes = {}
        for index, element in enumerate(template['elements']):
            if element['kind'] == 'code':
                codes[index] = self.build_code(element, product_id)
                if product_id is not None:
                    _, element['w'], element['h'] = codes[index]
                elif not element['w'] or not element['h']:
                    _, element['w'], element['h'] = codes[index]
        width, height = self.validate(template)
        parts = [f'<rect width="{width:g}" height="{height:g}" fill="white"/>']
        border = float(template.get('border', 0))
        if border < 0 or border >= min(width, height):
            raise ValueError('Некорректная толщина обводки этикетки')
        if border:
            inset = border / 2
            parts.append(f'<rect x="{inset:g}" y="{inset:g}" '
                         f'width="{width-border:g}" height="{height-border:g}" '
                         f'fill="none" stroke="black" stroke-width="{border:g}"/>')
        for index, element in enumerate(template['elements']):
            x, y = float(element['x']), float(element['y'])
            w, h = float(element['w']), float(element['h'])
            if element['kind'] == 'code':
                code, _, _ = codes[index]
                if product_id is None:
                    source = code.svg if element['code_type'] in ('QR', 'DataMatrix') else code
                    parts.append(svg.embed(source, x, y, w, h))
                elif element['code_type'] in ('QR', 'DataMatrix'):
                    parts.append(svg.symbol(code, x, y))
                else:
                    parts.append(svg.embed(code, x, y, w, h))
            elif element['kind'] == 'line':
                parts.append(f'<line x1="{x:g}" y1="{y:g}" x2="{x+w:g}" y2="{y+h:g}" '
                             f'stroke="black" stroke-width="{float(element.get("stroke", 0.3)):g}"/>')
            else:
                text = element.get('text', '')
                if element.get('field'):
                    text += self.text_value(product_id, element['field'])
                if not text:
                    continue
                parts.append(self.render_text(element, text, x, y, w, h))
        return svg.document(width, height, parts)

    #===== SVG-текст с подбором размера при переполнении блока =====
    def render_text(self, element, text, x, y, w, h):
        size = float(element.get('font_size', 14)) * svg.PT
        stroke = float(element.get('stroke', 0))
        spacing = float(element.get('line_spacing', 1.2))
        if size <= 0 or spacing <= 0 or stroke < 0:
            raise ValueError('Некорректные параметры шрифта')
        family = element.get('font', svg.FONT)
        weight = 'bold' if element.get('bold') else 'normal'
        style = 'italic' if element.get('italic', True) else 'normal'
        anchor, px = {'Слева': ('start', x), 'Центр': ('middle', x+w/2),
                      'Справа': ('end', x+w)}.get(element.get('align', 'Слева'), ('start', x))

        # Сначала пробуем исходный шрифт, затем уменьшаем только при переполнении.
        minimum = min(size, 6 * svg.PT)
        candidate = size
        while True:
            font = tkfont.Font(family=family, size=-max(1, round(candidate * svg.SCALE)),
                               weight=weight, slant='italic' if style == 'italic' else 'roman')
            lines = self.wrap_text(text, w * svg.SCALE, font.measure)
            height = candidate * (1 + (len(lines) - 1) * spacing)
            if height <= h + 0.01:
                break
            if candidate <= minimum:
                raise ValueError('Текст «{}» не помещается в блок {:.1f} × {:.1f} мм '
                                 'даже при шрифте 6 pt'.format(text[:35], w, h))
            candidate = max(minimum, candidate - 0.5 * svg.PT)
        attributes = (f'<text x="{px:g}" y="{y+candidate:g}" font-family="{escape(family, quote=True)}" '
                      f'font-size="{candidate:g}" font-style="{style}" font-weight="{weight}" '
                      f'text-anchor="{anchor}" fill="black" ')
        if stroke:
            attributes += (f'stroke="black" stroke-width="{stroke:g}" '
                           'stroke-linejoin="round" paint-order="stroke fill" ')
        spans = ''.join(f'<tspan x="{px:g}" dy="{0 if i == 0 else candidate*spacing:g}">'
                        f'{escape(line)}</tspan>' for i, line in enumerate(lines))
        return attributes + '>' + spans + '</text>'
