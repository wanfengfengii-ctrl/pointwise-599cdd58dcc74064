from trial.specification import build_trial_spec


def register(registry, trial_id, condition, left_bench, right_bench, references, units):
    spec = build_trial_spec(trial_id, condition, left_bench, right_bench, references, units)
    return registry.save(spec)


def get_trial(registry, trial_id):
    return registry.get(trial_id)
