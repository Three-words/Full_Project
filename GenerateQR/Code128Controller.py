
"""Code 128: оптимальный выбор наборов A/B/C, контрольная сумма и SVG."""
import heapq
import re
from itertools import count

from barcode.charsets import code128
from Controllers.AlgorithmController import AlgorithmController as Algo
from GenerateQR.SVGController import document


class Code128Controller:
    MODULE, HEIGHT, QUIET = 0.254, 13.0, 6.4
    PREFIX, SEP, SUFFIX = Algo.PREFIX, Algo.SEP, Algo.SUFFIX
    START = {'A': 103, 'B': 104, 'C': 105}
    SWITCH = {'A': {'B': 100, 'C': 99},
              'B': {'A': 101, 'C': 99}, 'C': {'A': 101, 'B': 100}}
    SETS = {'A': code128.A, 'B': code128.B}

    def _optimize(self, data):
        best, prev, queue, counter = {}, {}, [], count()
        for mode, start in self.START.items():
            state = (0, mode)
            best[state], prev[state] = 1, (None, (start,))
            heapq.heappush(queue, (1, next(counter), state))

        while queue:
            cost, _, state = heapq.heappop(queue)
            if cost != best[state]:
                continue
            pos, mode = state
            if pos == len(data):
                result = []
                while state is not None:
                    state, codes = prev[state]
                    result[:0] = codes
                return result

            choices = [((pos, target), (word,))
                       for target, word in self.SWITCH[mode].items()]
            if mode == 'C':
                pair = data[pos:pos + 2]
                if len(pair) == 2 and pair.isascii() and pair.isdigit():
                    choices.append(((pos + 2, mode), (int(pair),)))
            else:
                char = data[pos]
                if char in self.SETS[mode]:
                    choices.append(((pos + 1, mode), (self.SETS[mode][char],)))
                other = 'B' if mode == 'A' else 'A'
                if char not in self.SETS[mode] and char in self.SETS[other]:
                    choices.append(((pos + 1, mode), (98, self.SETS[other][char])))

            for target, codes in choices:
                new_cost = cost + len(codes)
                if new_cost < best.get(target, float('inf')):
                    best[target], prev[target] = new_cost, (state, codes)
                    heapq.heappush(queue, (new_cost, next(counter), target))
        raise ValueError('Не удалось закодировать данные Code 128')

    def create(self, fields):
        try:
            data = Algo.pack(fields, 'ascii').decode('ascii')
        except UnicodeEncodeError as error:
            raise ValueError('Code 128 поддерживает только ASCII и управляющие символы') from error
        words = self._optimize(data)
        checksum = (words[0] + sum(i * value for i, value in enumerate(words[1:], 1))) % 103
        bits = ''.join(code128.CODES[n] for n in words + [checksum]) + code128.STOP + '11'
        width = len(bits) * self.MODULE + 2 * self.QUIET
        parts = [f'<rect width="{width:g}" height="{self.HEIGHT:g}" fill="white"/>']
        for run in re.finditer('1+', bits):
            parts.append(f'<rect x="{self.QUIET + run.start() * self.MODULE:.6f}" y="0" '
                         f'width="{len(run.group()) * self.MODULE:.6f}" '
                         f'height="{self.HEIGHT:g}" fill="black"/>')
        return document(width, self.HEIGHT, parts)
