import math
from bisect import bisect_right
from dataclasses import dataclass
from itertools import accumulate


def number(value):
    try:
        return float(str(value).replace(',', '.'))
    except (ValueError, TypeError):
        return float('nan')


def visibility(value, span):
    if value is None or value == '':
        return None
    length = number(value)
    if not math.isfinite(length) or not 0 < length <= span + 1e-7:
        raise ValueError('La duración visible debe ser mayor que cero y caber antes del siguiente verso.')
    return min(length, span)


@dataclass(frozen=True)
class ReelClock:
    starts: tuple
    total: float

    @classmethod
    def lyrics(cls, durations, intro, hold):
        running = list(accumulate(durations, initial=intro))
        return cls(tuple(running[:-1]), running[-1] + hold)

    @classmethod
    def ascii(cls, duration):
        return cls((), duration)

    def row_at(self, seconds):
        return max(0, bisect_right(self.starts, seconds + 1e-9) - 1)

    def sample(self, position):
        return min(max(0, position), max(0, self.total - 1 / 30))


def visible_at(elapsed, length):
    return elapsed >= -1e-8 and (length is None or elapsed < length - 1e-8)
