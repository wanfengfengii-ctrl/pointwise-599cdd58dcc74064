from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction


_MICROKELVIN = {'K': 1_000_000, 'mK': 1_000, 'uK': 1}


@dataclass(frozen=True)
class UnitConvention:
    unit: str
    inputs: tuple[str, ...]


def parse_rational(value):
    if isinstance(value, Fraction):
        return value
    if type(value) is int or isinstance(value, str):
        try:
            return Fraction(value)
        except (ValueError, ZeroDivisionError) as error:
            raise ValueError('invalid rational value') from error
    raise ValueError('expected an integer, Fraction or rational string')


def validate_unit_convention(unit, inputs):
    if not isinstance(unit, str) or unit not in _MICROKELVIN:
        raise ValueError('incompatible convention unit')
    if not isinstance(inputs, (list, tuple)):
        raise ValueError('input units must be an array')
    allowed = {unit}
    for name in inputs:
        if not isinstance(name, str) or name not in _MICROKELVIN:
            raise ValueError('incompatible input unit')
        allowed.add(name)
    return UnitConvention(unit, tuple(sorted(allowed)))


def normalize_reading(reading, convention):
    if not isinstance(reading, Mapping):
        return parse_rational(reading)
    if set(reading) != {'value', 'unit'}:
        raise ValueError('a reading with units needs value and unit')
    unit = reading['unit']
    if unit not in convention.inputs:
        raise ValueError('reading unit is outside the convention')
    scale = Fraction(_MICROKELVIN[unit], _MICROKELVIN[convention.unit])
    return parse_rational(reading['value']) * scale
