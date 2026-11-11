
"""Макеты этикеток: состав, размеры и расположение элементов."""
import re
from math import ceil
from GenerateQR import SVGController as svg

#===== Состав комплекта и транспортный макет =====
MATRIX = (('SVG_UII', '25S', 'UII', 20), ('SVG_FNN', '68P', 'FNN', 18))
DOCUMENTS = ('RE', 'RO', 'Passport')
DOC_IDS = ('25S', '69P', '68P')
TRANSPORT_GRID = ('M0 22 H105 M0 43 H105 M0 62 H105 M0 79 H105 '
                  'M80.8 22 V43 M52.5 43 V62 M35 62 V79 M70 62 V79')
TRANSPORT_BARCODES = ((14.525, 7, 75.95, 13), (6.62, 28.2, 67.56, 13), (9.11, 87.5, 86.78, 18))
TRANSPORT_TEXT = (
    ('ТКН  {tkn}', 3, 5.2, svg.FONT_PT, 'start'), ('ФНН  {fnn}', 3, 27.2, svg.FONT_PT, 'start'),
    ('№ места/', 92.9, 27.8, svg.FONT_PT, 'middle'), ('/кол. мест', 92.9, 33, svg.FONT_PT, 'middle'),
    ('{place}', 92.9, 40.3, svg.FONT_LARGE_PT, 'middle'),
    ('Грузоотправитель', 3, 48.3, svg.FONT_PT, 'start'), ('{sender}', 26.25, 56.8, svg.FONT_LARGE_PT, 'middle'),
    ('Грузополучатель', 55.5, 48.3, svg.FONT_PT, 'start'), ('{recipient}', 78.75, 56.8, svg.FONT_LARGE_PT, 'middle'),
    ('Масса брутто, кг', 2.5, 67, svg.FONT_PT, 'start'), ('{gross}', 17.5, 74.3, svg.FONT_LARGE_PT, 'middle'),
    ('Масса нетто, кг', 37.5, 67, svg.FONT_PT, 'start'), ('{net}', 52.5, 74.3, svg.FONT_LARGE_PT, 'middle'),
    ('Габариты, см', 72.5, 67, svg.FONT_PT, 'start'), ('{dimensions}', 87.5, 74.3, svg.FONT_LARGE_PT, 'middle'),
    ('Блок логистических данных', 52.5, 84.6, svg.FONT_PT, 'middle'))


def number(value, trim=False):
    result = str(value).strip().replace('.', ',')
    if trim and ',' in result and set(result.split(',', 1)[1]) == {'0'}:
        return result.split(',', 1)[0]
    return result


def dimensions(values):
    return 'x'.join(number(value, True) for value in values)


#===== QR-этикетка с подписями =====
def qr_label(width, height, code, y, captions, master=None, margin=1.4, left_text=False):
    x = (width - code.full_mm) / 2
    if min(x - margin, y - margin, height - margin - y - code.full_mm) < 0:
        raise ValueError('QR не помещается на этикетке')
    parts = svg.border(width, height) + [svg.symbol(code, x, y)]
    text_x, align = (x, 'start') if left_text else (width / 2, 'middle')
    available = width - x - margin if left_text else width - 2 * margin
    for value, baseline, pt in captions:
        face = svg.font(pt * svg.PT, master)
        ascent, descent = (face.metrics(key) / svg.SCALE for key in ('ascent', 'descent'))
        if baseline - ascent < y + code.full_mm + svg.QR_TEXT_GAP or baseline + descent > height - margin:
            raise ValueError('QR и подписи не помещаются на этикетке')
        parts.append(svg.text(value, text_x, baseline, pt * svg.PT, align, available, master))
    return svg.document(width, height, parts)


class LabelRenderer:
    def __init__(self, qr, dm, pdf417, code128):
        self.qr, self.dm, self.pdf417, self.code128 = qr, dm, pdf417, code128

    #===== Стандартный комплект =====
    def render_product(self, product, master=None):
        labels, groups, errors, matrices = {}, {}, [], {}

        def add(name, drawing, *variants):
            labels[name], groups[name] = drawing, variants

        for name, identifier, column, size in MATRIX:
            try:
                value = product.get(column)
                if value is None or not str(value).strip():
                    raise ValueError('не заполнено значение')
                fields = [(identifier, str(value))]
                matrices[name] = self.dm.create(fields, size)
                add(name, matrices[name].svg, fields)
            except ValueError as error:
                errors.append(f'{column}: {error}')

        try:
            if len(matrices) != 2:
                raise ValueError('нужны оба кода')
            add('SVG_Uniq_Marker', self.render_marker(product, matrices, master),
                [('25S', str(product['UII']))], [('68P', str(product['FNN']))])
        except ValueError as error:
            errors.append('Общая этикетка УИИ/ФНН: ' + str(error))

        try:
            drawing, fields = self.render_package(product, master)
            add('SVG_Single_Item_Package', drawing, fields)
        except (ValueError, KeyError, TypeError) as error:
            errors.append('Упаковка: ' + str(error))

        for name in DOCUMENTS:
            try:
                values = [product.get('UII'), product.get(name + '_Translit'), product.get('FNN')]
                if any(value is None or not str(value).strip() for value in values):
                    raise ValueError('Не заполнены данные документа')
                values = [str(value).strip() for value in values]
                fields = list(zip(DOC_IDS, values))
                add('SVG_' + name, self.render_document(values, fields, master), fields)
            except (ValueError, KeyError, TypeError) as error:
                errors.append(name + ': ' + str(error))
        return labels, groups, errors

    #===== Общая этикетка УИИ/ФНН =====
    def render_marker(self, product, matrices, master):
        parts = svg.border(49.5, 29)
        for name, x, expected in (('SVG_UII', 15.2, 20), ('SVG_FNN', 34.8, 18)):
            code = matrices[name]
            if code.size != expected:
                raise ValueError('Матрица не помещается на общую этикетку')
            parts.append(svg.symbol(code, x - code.full_mm / 2, 2.25))
        for value, x, y in (('УИИ', 15.2, 17.3), ('ФНН', 34.8, 17.3),
                            ('УИИ: ' + str(product['UII']), 2.5, 22.4),
                            ('ФНН: ' + str(product['FNN']), 2.5, 27.5)):
            start = x == 2.5
            width = 49.5 - x - 1 if start else 2 * min(x - 1, 48.5 - x)
            parts.append(svg.text(value, x, y, svg.FONT_PT * svg.PT,
                                  'start' if start else 'middle', width, master))
        return svg.document(49.5, 29, parts)

    #===== Этикетка упаковки =====
    def render_package(self, product, master):
        count = product.get('Items_per_package')
        quantity = int(1 if count is None or count == '' else count)
        if quantity < 1:
            raise ValueError('Число изделий в упаковке должно быть больше нуля')
        required = ('Serial_number', 'UYAIS', 'Issuance_agency_code', 'Organization_code', 'Cargo_place_count')
        if any(product.get(key) is None or not str(product[key]).strip() for key in required):
            raise ValueError('Не заполнены данные упаковки')
        serial = str(product['Serial_number']).strip()
        uyais = re.sub(r'УЯИС|ТУ|[\s.]', '', str(product['UYAIS']), flags=re.I)
        if not uyais:
            raise ValueError('После очистки УЯИС пустой')
        code = str(product['Issuance_agency_code']) + str(product['Organization_code']) + uyais
        if quantity == 1:
            fields = [('25P', code), ('Q', str(product['Cargo_place_count'])), ('S', serial)]
            captions = ((code, 26, svg.FONT_SMALL_PT), ('Сер. №: ' + serial, 31.5, svg.FONT_PT))
        else:
            batch = ''.join(re.findall(r'[0-9]', serial))[:3]
            if len(batch) != 3:
                raise ValueError('Для 1T нужны три цифры серийного номера')
            fields = [('25P', code), ('Q', str(quantity)), ('1T', batch)]
            captions = ((code, 26, svg.FONT_SMALL_PT), ('Пар. №: ' + batch, 31.5, svg.FONT_PT),
                        ('Кол. изд.: ' + str(quantity), 37, svg.FONT_PT))
        return qr_label(32, 42 if quantity > 1 else 36, self.qr.create(fields), 2.8, captions, master), fields

    #===== Документы: перенос по ширине шрифта =====
    def render_document(self, values, fields, master):
        qr = self.qr.create(fields)
        face = svg.font(svg.FONT_DOCUMENT_PT * svg.PT, master)
        ascent, descent = (face.metrics(key) / svg.SCALE for key in ('ascent', 'descent'))
        x = (30 - qr.full_mm) / 2
        available = 30 - x - 0.4
        if x < 0.4 or available <= 0:
            raise ValueError('QR шире этикетки 30 мм')
        lines = []
        for value in values:
            line = ''
            for char in value:
                if line and face.measure(line + char) > available * svg.SCALE:
                    lines.append(line)
                    line = char
                else:
                    line += char
            lines.append(line)
        first = max(16.8, 0.6 + qr.full_mm + svg.QR_TEXT_GAP + ascent)
        step = ascent + descent + 0.05
        height = max(29, first + (len(lines) - 1) * step + descent + 0.4)
        captions = [(line, first + i * step, svg.FONT_DOCUMENT_PT) for i, line in enumerate(lines)]
        return qr_label(30, ceil(height * 10) / 10, qr, 0.6, captions, master, margin=0.4, left_text=True)

    #===== Транспортная этикетка =====
    def render_transport(self, data, fields):
        parts = svg.border(105, 108)
        parts.append(f'<path d="{TRANSPORT_GRID}" fill="none" stroke="black" '
                     f'stroke-width="{svg.GRID_STROKE:g}"/>')
        barcodes = (self.code128.create([('J', data['tkn'])]),
                    self.code128.create([('68P', data['fnn'])]), self.pdf417.create(fields))
        for index, (code, bounds) in enumerate(zip(barcodes, TRANSPORT_BARCODES)):
            quiet = self.pdf417.QUIET if index == 2 else self.code128.QUIET
            parts.append(svg.embed(code, *bounds, quiet, quiet if index == 2 else 0))
        values = {**data, 'place': '{}/{}'.format(data['place_number'], data['place_count']),
                  'gross': number(data['gross']), 'net': number(data['net']),
                  'dimensions': dimensions(data['dimensions'].replace('×', 'x').split('x'))}
        for template, x, y, size, align in TRANSPORT_TEXT:
            content = svg.text(template.format_map(values), 0, 0, size * svg.PT, align)
            parts.append(f'<g transform="translate({x:g} {y:g}) scale(0.77 1)">{content}</g>')
        return svg.document(105, 108, parts)
