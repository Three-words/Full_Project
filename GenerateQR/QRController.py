
"""Кодирование QR: сегментация, выбор версии и матрица."""
import segno
from segno import consts
from segno.encoder import DataOverflowError
from Controllers.AlgorithmController import AlgorithmController as Algo
from GenerateQR.SVGController import MatrixCode


class QRController:
    PREFIX, SEP, SUFFIX = Algo.PREFIX, Algo.SEP, Algo.SUFFIX
    ALPHA = set(b'0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:')
    MODES = {'N': consts.MODE_NUMERIC, 'A': consts.MODE_ALPHANUMERIC,
             'B': consts.MODE_BYTE}
    MODULE, QUIET, ERROR = 0.381, 4, 'H'

    @staticmethod
    def payload(fields):
        return Algo.pack((str(i).strip(), str(v).strip()) for i, v in fields)

    @staticmethod
    def _cost(mode, length, version):
        group = (version > 9) + (version > 26)
        counters = {'N': (10, 12, 14), 'A': (9, 11, 13), 'B': (8, 16, 16)}
        if mode == 'B':
            bits = length * 8
        else:
            q, r = divmod(length, 3 if mode == 'N' else 2)
            bits = q * (10 if mode == 'N' else 11) + (
                (0, 4, 7)[r] if mode == 'N' else r * 6)
        return 4 + counters[mode][group] + bits

    def _segment(self, identifier, value, version):
        """Находит минимальное разбиение поля на Numeric, Alphanumeric, Byte."""
        data = (identifier + value).encode('utf-8')
        best = [float('inf')] * (len(data) + 1)
        prev = [None] * (len(data) + 1)
        best[0] = 0
        for start in range(len(data)):
            if best[start] == float('inf'):
                continue
            for mode in self.MODES:
                for end in range(start + 1, len(data) + 1):
                    byte = data[end - 1]
                    if ((mode == 'N' and not 48 <= byte <= 57) or
                            (mode == 'A' and byte not in self.ALPHA)):
                        break
                    cost = best[start] + self._cost(mode, end - start, version)
                    if cost < best[end]:
                        best[end], prev[end] = cost, (start, mode)

        parts, pos = [], len(data)
        while pos:
            start, mode = prev[pos]
            part = data[start:pos]
            parts.append((part if mode == 'B' else part.decode('ascii'),
                          self.MODES[mode], None))
            pos = start
        return parts[::-1]

    def create(self, fields):
        """Генерирует минимальную QR-версию с уровнем коррекции H."""
        fields = [(str(i).strip(), str(v).strip()) for i, v in fields]
        self.payload(fields)
        for identifier, _ in fields:
            identifier.encode('ascii')

        for version in range(1, 41):
            if version in (1, 10, 27):
                segments = [(self.PREFIX, consts.MODE_BYTE, None)]
                for i, (identifier, value) in enumerate(fields):
                    segments.extend(self._segment(identifier, value, version))
                    if i < len(fields) - 1:
                        segments.append((self.SEP, consts.MODE_BYTE, None))
                segments.append((self.SUFFIX, consts.MODE_BYTE, None))
            try:
                qr = segno.make_qr(segments, version=version, error=self.ERROR,
                                   mask=None, boost_error=False, eci=False)
                cells = [(x, y) for y, row in enumerate(qr.matrix)
                         for x, dark in enumerate(row) if dark]
                return MatrixCode(len(qr.matrix), cells, version=qr.version, mask=qr.mask,
                                  module=self.MODULE, quiet=self.QUIET)
            except DataOverflowError:
                continue
        raise ValueError('Данные слишком большие для QR Code')
