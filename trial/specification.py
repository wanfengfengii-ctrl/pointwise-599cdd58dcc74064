from collections.abc import Mapping
from dataclasses import dataclass

from trial.roles import MAIN_CHANNEL, TrialRoles, require_identifier, validate_roles
from trial.units import UnitConvention, validate_unit_convention


@dataclass(frozen=True)
class TrialSpec:
    trial_id: str
    condition: str
    roles: TrialRoles
    units: tuple[tuple[str, UnitConvention], ...]

    def expected_channels(self):
        return (MAIN_CHANNEL, *self.roles.references)

    def unit_for(self, channel):
        for name, convention in self.units:
            if name == channel:
                return convention
        raise KeyError(channel)


def build_trial_spec(trial_id, condition, left_bench, right_bench, references, units):
    trial_id = require_identifier(trial_id, 'trial identifier')
    condition = require_identifier(condition, 'condition')
    roles = validate_roles(left_bench, right_bench, references)
    channels = (MAIN_CHANNEL, *roles.references)
    if not isinstance(units, Mapping) or set(units) != set(channels):
        raise ValueError('exactly one unit convention is required for each channel')
    conventions = []
    for name in channels:
        entry = units[name]
        if not isinstance(entry, Mapping) or set(entry) != {'unit', 'inputs'}:
            raise ValueError(f'invalid unit convention for {name}')
        conventions.append((name, validate_unit_convention(entry['unit'], entry['inputs'])))
    return TrialSpec(trial_id, condition, roles, tuple(conventions))
