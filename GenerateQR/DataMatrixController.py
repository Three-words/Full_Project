
"""Универсальный генератор Data Matrix ECC200."""
from PIL import Image, ImageOps
from pylibdmtx.pylibdmtx import encode
from pylibdmtx.pylibdmtx_error import PyLibDMTXError

from Controllers.AlgorithmController import AlgorithmController as Algo
from GenerateQR.SVGController import MatrixCode


class DataMatrixController:
    PREFIX, SEP, SUFFIX = Algo.PREFIX, Algo.SEP, Algo.SUFFIX
    SIZES = (18, 20, 22, 24, 26, 32, 36, 40, 44, 48, 52,
             64, 72, 80, 88, 96, 104, 120, 132, 144)
    MODULE, QUIET = 0.381, 4

    @staticmethod
    def payload(fields):
        return Algo.pack(fields)

    def create(self, fields, preferred=18):
        data = self.payload(fields)
        if preferred not in self.SIZES:
            raise ValueError('Недопустимый размер DataMatrix')

        for size in self.SIZES[self.SIZES.index(preferred):]:
            try:
                encoded = encode(data, size='{}x{}'.format(size, size))
                break
            except PyLibDMTXError as error:
                if 'image is not large enough' not in str(error):
                    raise
        else:
            raise ValueError('Данные не помещаются в DataMatrix')

        image = Image.frombytes('RGB', (encoded.width, encoded.height), encoded.pixels).convert('L')
        bounds = ImageOps.invert(image).getbbox()
        if not bounds:
            raise ValueError('Не удалось построить DataMatrix')
        image = image.crop(bounds).resize((size, size), getattr(Image, 'Resampling', Image).NEAREST)
        cells = [(x, y) for y in range(size) for x in range(size) if image.getpixel((x, y)) < 128]
        return MatrixCode(size, cells, module=self.MODULE, quiet=self.QUIET)
