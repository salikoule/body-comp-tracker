"""Long-range physique roadmap: simulate week by week from today's body to a goal body.

Body fat here is fat / total weight, the same definition the weekly plan uses.
Fat-free mass changes only through the lean-gain model; cuts are assumed to keep it.
"""

from datetime import date, timedelta

WEEKS_PER_MONTH = 4.345
MAX_WEEKS = 520
CUT_RATE = 0.005
MINI_CUT_RATE = 0.0075
RESET_WEEKS = 2
KCAL_PER_KG_FAT = 7700
KCAL_PER_KG_LEAN = 4000

LEAN_FLOOR = {"male": 12.0, "female": 22.0}
BULK_CEILING = {"male": 16.0, "female": 26.0}
NATURAL_FFMI = {"male": 25.0, "female": 21.5}
UNTRAINED_FFMI = {"male": 18.0, "female": 14.5}
LEAN_KG_PER_MONTH = {"male": 1.0, "female": 0.5}
EXPERIENCE_FACTOR = (1.1, 1.0, 0.9, 0.8)
SLOW_GAIN_FACTOR = 0.7
RECOMP_LEAN_FACTOR = 0.5

STRATEGIES = (
    ("cycles", "Cut, then lean-bulk cycles",
     "Get lean first, then build muscle in surplus blocks and trim back with short mini-cuts."),
    ("slow_gain", "Cut to goal, then gain slowly",
     "Cut straight to your goal body fat, then add muscle with a small surplus that keeps body fat level."),
    ("recomp", "Recomp at maintenance",
     "Eat at maintenance and train hard. Fat comes down and muscle goes up at the same time, slowly."),
)


def experience_index(years):
    return max(0, min(3, int(years or 0)))


def headroom(sex, ffmi):
    """Share of the untrained-to-ceiling distance still left, from 1 (untrained) to 0 (at the ceiling)."""
    span = NATURAL_FFMI[sex] - UNTRAINED_FFMI[sex]
    return max(0.0, min(1.0, (NATURAL_FFMI[sex] - ffmi) / span))


def lean_gain_per_week(sex, years, ffmi):
    """Muscle the body can add per week in a surplus. It slows with the square of the headroom left."""
    monthly = LEAN_KG_PER_MONTH[sex] * headroom(sex, ffmi) ** 2 * EXPERIENCE_FACTOR[experience_index(years)]
    return max(monthly, 0.02) / WEEKS_PER_MONTH


def lean_share(sex, ffmi):
    """Share of bulk weight gain that is lean mass: higher with more headroom."""
    return 0.35 + 0.25 * headroom(sex, ffmi)


class _Body:
    def __init__(self, sex, height_cm, weight_kg, ffm_kg, years, start):
        self.sex = sex
        self.h2 = (height_cm / 100.0) ** 2
        self.ffm = ffm_kg
        self.fat = weight_kg - ffm_kg
        self.years = years
        self.week = 0
        self.start = start

    @property
    def weight(self):
        return self.ffm + self.fat

    @property
    def bf(self):
        return self.fat / self.weight * 100

    @property
    def ffmi(self):
        return self.ffm / self.h2

    def snapshot(self):
        return {
            "week": self.week,
            "date": (self.start + timedelta(days=7 * self.week)).isoformat(),
            "weight_kg": round(self.weight, 1),
            "bf_percent": round(self.bf, 1),
            "ffm_kg": round(self.ffm, 1),
            "fat_kg": round(self.fat, 1),
            "ffmi": round(self.ffmi, 2),
            "fmi": round(self.fat / self.h2, 2),
        }

    def tick(self):
        self.week += 1
        self.years += 1 / 52.0

    def lean_rate(self):
        return lean_gain_per_week(self.sex, self.years, self.ffmi)


class _Run:
    def __init__(self, body):
        self.body = body
        self.phases = []

    def phase(self, kind, label, step, until):
        body = self.body
        start = body.snapshot()
        energy = 0.0
        while not until() and body.week < MAX_WEEKS:
            energy += step()
            body.tick()
        weeks = body.week - start["week"]
        if weeks <= 0:
            return
        end = body.snapshot()
        self.phases.append({
            "kind": kind,
            "label": label,
            "weeks": weeks,
            "start": start,
            "end": end,
            "kcal_per_day": int(round(energy / (weeks * 7) / 10.0) * 10),
            "kg_per_week": round((end["weight_kg"] - start["weight_kg"]) / weeks, 2),
        })

    def cut(self, label, rate, to_bf):
        """Lose a fixed share of the starting weight each week, as the weekly plan does."""
        body = self.body
        weekly = rate * body.weight

        def step():
            loss = min(weekly, body.fat - _fat_for(body.ffm, to_bf))
            body.fat -= loss
            return -loss * KCAL_PER_KG_FAT

        self.phase("cut", label, step, lambda: body.bf <= to_bf + 0.05)

    def bulk(self, label, until, slow=False, hold_bf=None):
        body = self.body

        def step():
            lean = body.lean_rate() * (SLOW_GAIN_FACTOR if slow else 1)
            if hold_bf is not None:
                fat = lean * hold_bf / (100 - hold_bf)
            else:
                share = lean_share(body.sex, body.ffmi)
                fat = lean * (1 - share) / share
            body.ffm += lean
            body.fat += fat
            return lean * KCAL_PER_KG_LEAN + fat * KCAL_PER_KG_FAT

        self.phase("bulk", label, step, until)

    def hold(self, label, weeks):
        body = self.body
        stop = body.week + weeks
        self.phase("maintain", label, lambda: 0.0, lambda: body.week >= stop)


def _fat_for(ffm, bf):
    return ffm * bf / (100.0 - bf)


def simulate(strategy, *, sex, height_cm, weight_kg, ffm_kg, goal_bf, goal_ffmi, training_years, start=None):
    sex = "female" if sex == "female" else "male"
    body = _Body(sex, height_cm, weight_kg, ffm_kg, training_years or 0, start or date.today())
    run = _Run(body)
    start_bf = body.bf
    goal_ffm = goal_ffmi * body.h2
    floor = min(LEAN_FLOOR[sex], goal_bf - 1.5)
    ceiling = max(BULK_CEILING[sex], goal_bf + 1.5)
    need_muscle = lambda: body.ffm < goal_ffm - 0.05

    if strategy != "recomp" and not need_muscle():
        if body.bf > goal_bf + 0.5:
            run.cut("Cut to %s%%" % _num(goal_bf), CUT_RATE, goal_bf)
            run.hold("Back to maintenance", 3)
    elif strategy == "cycles":
        if body.bf > floor + 1:
            run.cut("Cut to %s%%" % _num(floor), CUT_RATE, floor)
            run.hold("Back to maintenance", 3)
        while need_muscle() and body.week < MAX_WEEKS:
            run.bulk("Lean bulk", lambda: body.bf >= ceiling or not need_muscle())
            if not need_muscle() or body.week >= MAX_WEEKS:
                break
            run.cut("Mini-cut to %s%%" % _num(floor), MINI_CUT_RATE, floor)
            run.hold("Reset at maintenance", RESET_WEEKS)
        if body.bf > goal_bf + 0.5:
            run.cut("Finish at %s%%" % _num(goal_bf), CUT_RATE, goal_bf)
    elif strategy == "slow_gain":
        if body.bf > goal_bf + 0.5:
            run.cut("Cut to %s%%" % _num(goal_bf), CUT_RATE, goal_bf)
            run.hold("Back to maintenance", 3)
        if need_muscle():
            run.bulk("Slow gain at %s%%" % _num(goal_bf), lambda: not need_muscle(), slow=True,
                     hold_bf=max(goal_bf, body.bf))
    elif strategy == "recomp":
        _recomp(run, body, goal_bf, need_muscle)
    else:
        raise ValueError("Unknown strategy %r" % strategy)

    end = body.snapshot()
    phases = run.phases
    return {
        "key": strategy,
        "phases": phases,
        "weeks": body.week,
        "end": end,
        "reaches_goal": not need_muscle() and body.bf <= goal_bf + 0.6,
        "peak_bf": round(max([p["end"]["bf_percent"] for p in phases] + [start_bf]), 1),
        "low_bf": round(min([p["end"]["bf_percent"] for p in phases] + [end["bf_percent"]]), 1),
        "path": [_point(phases[0]["start"])] + [_point(p["end"]) for p in phases] if phases else [_point(end)],
    }


def _recomp(run, body, goal_bf, need_muscle):
    def step():
        lean = body.lean_rate() * RECOMP_LEAN_FACTOR
        body.ffm += lean
        if body.bf > goal_bf:
            loss = min(_recomp_fat_loss(body.bf) / WEEKS_PER_MONTH, body.fat - _fat_for(body.ffm, goal_bf))
            body.fat -= max(0.0, loss)
        else:
            body.fat = _fat_for(body.ffm, goal_bf)
        return 0.0

    run.phase("recomp", "Recomp at maintenance", step, lambda: not need_muscle() and body.bf <= goal_bf + 0.05)


def _recomp_fat_loss(bf):
    return 0.8 if bf > 22 else 0.5 if bf > 16 else 0.3


def _point(snapshot):
    return [snapshot["fmi"], snapshot["ffmi"]]


def _num(value):
    return ("%.1f" % value).rstrip("0").rstrip(".")


def roadmaps(*, sex, height_cm, weight_kg, ffm_kg, goal_bf, goal_ffmi, training_years, start=None):
    """All strategies, fastest first, each tagged with its name and pitch."""
    results = []
    for key, name, pitch in STRATEGIES:
        result = simulate(key, sex=sex, height_cm=height_cm, weight_kg=weight_kg, ffm_kg=ffm_kg,
                          goal_bf=goal_bf, goal_ffmi=goal_ffmi, training_years=training_years, start=start)
        result.update({"name": name, "pitch": pitch})
        results.append(result)
    return results


def goal_check(sex, goal_ffmi):
    """A warning when the muscle goal sits at or past the natural ceiling, else None."""
    sex = "female" if sex == "female" else "male"
    ceiling = NATURAL_FFMI[sex]
    if goal_ffmi >= ceiling:
        return "A lean mass index of %s is at or past the natural ceiling (about %s). Expect it to take many years, if it is reachable at all." % (
            _num(goal_ffmi), _num(ceiling))
    if goal_ffmi >= ceiling - 1.5:
        return "A lean mass index of %s is close to the natural ceiling (about %s). Progress near it is very slow." % (
            _num(goal_ffmi), _num(ceiling))
    return None
