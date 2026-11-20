
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


#===== Форматирование числа для подписи =====
def number(value, trim=False):
    result = str(value).strip().replace('.', ',')
    if trim and ',' in result and set(result.split(',', 1)[1]) == {'0'}:
        return result.split(',', 1)[0]
    return result


#===== Форматирование габаритов =====
def dimensions(values):
    return 'x'.join(number(value, True) for value in values)


#===== Создание QR-этикетки с подписями =====
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
    #===== Подключение генераторов штрихкодов =====
    def __init__(self, qr, dm, pdf417, code128):
        self.qr, self.dm, self.pdf417, self.code128 = qr, dm, pdf417, code128

    #===== Формирование полного комплекта или выбранного макета =====
    def render_product(self, product, master=None, only=None):
        labels, groups, errors, matrices = {}, {}, [], {}

        #===== Добавление готовой этикетки и её данных =====
        def add(name, drawing, *variants):
            labels[name], groups[name] = drawing, variants

        for name, identifier, column, size in MATRIX:
            if only and only not in (name, 'SVG_Uniq_Marker'):
                continue
            try:
                value = product.get(column)
                if value is None or not str(value).strip():
                    raise ValueError('не заполнено значение')
                fields = [(identifier, str(value))]
                matrices[name] = self.dm.create(fields, size)
            except ValueError as error:
                if column != 'FNN' or product.get('FNN') not in (None, ''):
                    errors.append(f'{column}: {error}')

        if only in (None, 'SVG_Uniq_Marker'):
            try:
                if not product.get('FNN') or not str(product['FNN']).strip():
                    raise ValueError('для генерации необходимо заполнить ФНН')
                if not product.get('UII') or not str(product['UII']).strip():
                    raise ValueError('для генерации необходимо заполнить УИИ')
                if any(name not in matrices for name, _, _, _ in MATRIX):
                    raise ValueError('не удалось сформировать УИИ или ФНН')
                variants = [[(identifier, str(product[column]))]
                            for name, identifier, column, _ in MATRIX if name in matrices]
                add('SVG_Uniq_Marker', self.render_marker(product, matrices, master), *variants)
            except ValueError as error:
                errors.append('Общая этикетка УИИ/ФНН: ' + str(error))

        if only in (None, 'SVG_Single_Item_Package'):
            try:
                drawing, fields = self.render_package(product, master)
                add('SVG_Single_Item_Package', drawing, fields)
            except (ValueError, KeyError, TypeError) as error:
                errors.append('Упаковка: ' + str(error))

        for name in DOCUMENTS:
            if only and only != 'SVG_' + name:
                continue
            try:
                required = (('UII', 'УИИ'), (name + '_Translit', 'обозначение документа'),
                            ('FNN', 'ФНН'))
                missing = [title for key, title in required
                           if product.get(key) is None or not str(product[key]).strip()]
                if missing:
                    raise ValueError('необходимо заполнить ' + ', '.join(missing))
                values = [str(product[key]).strip() for key, _ in required]
                fields = list(zip(DOC_IDS, values))
                add('SVG_' + name, self.render_document(values, fields, master), fields)
            except (ValueError, KeyError, TypeError) as error:
                errors.append({'RE': 'QR РЭ', 'RO': 'QR РО', 'Passport': 'QR Паспорта'}[name] + ': ' + str(error))
        return labels, groups, errors

    #===== Общая этикетка УИИ/ФНН =====
    def render_marker(self, product, matrices, master):
        parts = svg.border(49.5, 29)
        captions = []
        for name, column, x, expected, baseline in (
                ('SVG_UII', 'UII', 15.2, 20, 22.4),
                ('SVG_FNN', 'FNN', 34.8, 18, 27.5)):
            if name not in matrices:
                continue
            code = matrices[name]
            if code.size != expected:
                raise ValueError('Матрица не помещается на общую этикетку')
            parts.append(svg.symbol(code, x - code.full_mm / 2, 2.25))
            captions.extend(((column, x, 17.3),
                             (column + ': ' + str(product[column]), 2.5, baseline)))
        for value, x, y in captions:
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
        multiple = quantity > 1
        batch = ''.join(re.findall(r'[0-9]', serial))[:3] if multiple else serial
        if multiple and len(batch) != 3:
            raise ValueError('Для 1T нужны три цифры серийного номера')
        fields = [('25P', code), ('Q', str(quantity if multiple else product['Cargo_place_count'])),
                  ('1T' if multiple else 'S', batch)]
        captions = [(code, 26, svg.FONT_SMALL_PT),
                    (('Пар. №: ' if multiple else 'Сер. №: ') + batch, 31.5, svg.FONT_PT)]
        if multiple:
            captions.append(('Кол. изд.: ' + str(quantity), 37, svg.FONT_PT))
        return qr_label(32, 42 if multiple else 36, self.qr.create(fields), 2.8,
                        captions, master), fields

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
        barcodes = ((self.code128.create([('J', data['tkn'])]), TRANSPORT_BARCODES[0], False),
                    (self.pdf417.create(fields), TRANSPORT_BARCODES[2], True))
        if data.get('fnn') is not None and str(data['fnn']).strip():
            barcodes += ((self.code128.create([('68P', data['fnn'])]),
                          TRANSPORT_BARCODES[1], False),)
        for code, bounds, pdf in barcodes:
            quiet = self.pdf417.QUIET if pdf else self.code128.QUIET
            parts.append(svg.embed(code, *bounds, quiet, quiet if pdf else 0))
        values = {**data, 'fnn': data.get('fnn') or '',
                  'place': '{}/{}'.format(data['place_number'], data['place_count']),
                  'gross': number(data['gross']), 'net': number(data['net']),
                  'dimensions': dimensions(data['dimensions'].replace('×', 'x').split('x'))}
        for template, x, y, size, align in TRANSPORT_TEXT:
            parts.append(svg.text(template.format_map(values), x, y, size * svg.PT, align))
        return svg.document(105, 108, parts)
