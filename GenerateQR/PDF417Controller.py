
from pdf417gen import encode
from pdf417gen.rendering import barcode_size, modules
from GenerateQR.SVGController import document
from Controllers.AlgorithmController import AlgorithmController as Algo


class PDF417Controller:
    """Кодирование PDF417 и преобразование в SVG."""

    MODULE, HEIGHT, QUIET = 0.423, 18.0, 1.0
    COLUMNS, ECC = 8, 5
    PREFIX, SEP, SUFFIX = Algo.PREFIX, Algo.SEP, Algo.SUFFIX

    def create(self, fields):
        """Генерирует SVG PDF417."""
        data = Algo.pack(fields)

        codes = encode(data, columns=self.COLUMNS, security_level=self.ECC)
        width, rows = barcode_size(codes)

        if not 3 <= rows <= 90 or rows * self.COLUMNS > 928:
            raise ValueError("Данные не помещаются в PDF417")

        row_h = max(self.HEIGHT / rows, 3 * self.MODULE)
        w, h = width * self.MODULE + 2 * self.QUIET, rows * row_h + 2 * self.QUIET

        parts = [f'<rect width="{w:g}" height="{h:g}" fill="white"/>']
        parts += [
            f'<rect x="{self.QUIET + x * self.MODULE:.8f}" '
            f'y="{self.QUIET + y * row_h:.8f}" width="{self.MODULE:g}" '
            f'height="{row_h:.8f}" fill="black"/>'
            for x, y in modules(codes)
        ]
        return document(w, h, parts)
