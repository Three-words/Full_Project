
"""Алгоритмы идентификаторов изделия и общий формат данных кодов."""


class AlgorithmController:
    PREFIX = b'[)>\x1e06\x1d'
    SEP = b'\x1d'
    SUFFIX = b'\x1e\x04'

    @staticmethod
    def pack(fields, encoding='utf-8'):
        """Формирует общую строку идентификаторов для штрихкодов."""
        items = list(fields)
        if not items or any(i is None or v is None or not str(i).strip()
                            or not str(v).strip() for i, v in items):
            raise ValueError('Не заполнен идентификатор или значение кода')
        return (AlgorithmController.PREFIX + AlgorithmController.SEP.join(
            (str(i) + str(v)).encode(encoding) for i, v in items)
            + AlgorithmController.SUFFIX)

    @staticmethod
    def crc16(text):
        crc = 0
        for byte in text.encode('utf-8'):
            crc ^= byte << 8
            for _ in range(8):
                crc = ((crc << 1) ^ (0xCAFE if crc & 0x8000 else 0)) & 0xFFFF
        return f'{crc:04X}'

    @staticmethod
    def control_digit(number):
        num = int(number)
        return num - (num // 11) * 11

    @staticmethod
    def generate_docs(uyais):
        name = str(uyais or '').strip()
        if name.endswith('ТУ'):
            name = name[:-2].rstrip()
        return {col: name + suffix if name else None
                for col, suffix in (('RE', 'РЭ'), ('RO', 'РО'), ('Passport', 'ПС'))}

    @staticmethod
    def translation_maps(rows):
        translit = {c: t for i, low, up, t in rows for c in (low, up) if c}
        ids = {str(c).upper(): str(i) for i, low, up, t in rows
               for c in (low, up, t) if c and len(str(c)) == 1}
        return translit, ids

    @staticmethod
    def generate_uii(uyais, serial, agency, organization, translit):
        text = ''.join(translit.get(c, c) for c in str(uyais)).replace('.', '').strip()
        if text.upper().endswith('TU'):
            text = text[:-2].rstrip()
        crc = int(AlgorithmController.crc16(text + str(serial)), 16)
        return f"{agency}{organization}{str(crc).rjust(7, '1')}"

    @staticmethod
    def generate_tkn(serial, agency, organization, ids, year):
        def convert(code):
            parts = [c if c.isdigit() else ids.get(c.upper()) for c in str(code)]
            if None in parts:
                raise ValueError(f'Буква из кода «{code}» отсутствует в Translate.')
            return ''.join(map(str, parts))

        serial = f'{int(serial):05d}'
        if len(serial) != 5:
            raise ValueError('Порядковый номер должен содержать 5 цифр.')
        suffix = str(year)[-1] + serial
        number = convert(agency) + convert(organization) + suffix
        digit = str(AlgorithmController.control_digit(number))[-1]
        return f'{agency}{organization}{suffix}{digit}'
