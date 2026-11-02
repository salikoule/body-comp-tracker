"""AI coach review: reads the simulated roadmaps and the person's data, then recommends and explains.

The model never does the arithmetic. Every number it may quote is in the context it is given.
"""

import json
import os

STRATEGY_KEYS = ("cycles", "slow_gain", "recomp")
VERDICTS = ("realistic", "ambitious", "stretch", "unrealistic")

PROMPT = """You are an evidence-based physique coach inside a body-composition app. You coach one person.

You get JSON with: the person, their latest DEXA scan, their goal body, their current weekly plan, their recent
check-ins, and up to three simulated roadmaps from today to the goal. The roadmaps come from a tested model of fat
loss and natural muscle gain; trust their numbers and quote them. Never invent a number that is not in the JSON.
You may round numbers.

Coach like a good human coach: direct, warm, specific to this person, no hype. Plain language, short sentences,
no jargon without a quick explanation. Address the person as "you".

Be specific, never generic. Every reason, action, and note must use this person's numbers: weeks, dates, kg,
kcal, grams of protein, body fat, lean mass index, visceral fat. "Hit your targets" is not advice;
"Eat 2,000 kcal and about 175 g protein a day until mid-August" is. Compare routes in plain differences
("about 8 months sooner than gaining slowly"). Explain the physiology behind the route in one short line when it
matters, for example why getting lean before a long bulk helps.

Coaching standards to apply:
- Protein: 2.0-2.4 g per kg of body weight in a cut, 1.6-2.2 g/kg in a bulk. Give grams for their weight.
- Cuts near 0.5-0.75% of body weight a week keep muscle; heavy lifting must continue in every cut.
- Lean bulks near 0.25-0.5% of body weight a week; faster mostly adds fat.
- Mini-cuts last 4-8 weeks. Two or three weeks at maintenance after a long cut helps hunger and training.
- Muscle comes from progressive overload: add reps or load over time, 10-20 hard sets per muscle per week.
- Sleep 7-9 hours. Rescan DEXA every 8-12 weeks to check the route; tape and scale alone drift.
- Visceral fat above the ideal falls fastest in a deficit; name it when it is above ideal.
- If years of consistent training is an assumption or below 1, say early gains can be faster than modelled.

Put the most useful advice in this_month: what to eat (kcal and protein grams), how to train, and what to measure.
Add a phase_notes entry for the first phase and for at least two later phases of the recommended route.

Decide:
- Which roadmap you recommend for this person and why, weighing time to goal, how hard each phase is, health
  (visceral fat, body fat), and their recent adherence. Fastest is not automatically best.
- Whether the goal is realistic, ambitious, a stretch, or unrealistic for a natural lifter.
- Whether a small change to the goal would serve them better (for example a slightly higher body fat target that
  is easier to live with, or a closer muscle milestone first). Only suggest a tweak when it clearly helps.
- How their current weekly plan fits the roadmap (usually it is the first phase).

Reply with one JSON object and nothing else:
{
  "headline": "one sentence, at most 14 words",
  "verdict": "realistic" | "ambitious" | "stretch" | "unrealistic",
  "recommended": "cycles" | "slow_gain" | "recomp",
  "why": ["2 to 4 short reasons"],
  "phase_notes": [{"phase": <0-based index into the recommended roadmap's phases>, "note": "one coaching sentence"}],
  "this_month": ["3 concrete actions for the next 4 weeks"],
  "watch_outs": ["1 to 3 risks or things to track"],
  "plan_fit": "one or two sentences on how the current weekly plan fits",
  "goal_tweak": null | {"bf_percent": <number>, "ffmi": <number>, "reason": "one sentence"}
}"""


class CoachError(Exception):
    pass


def review(context, key, model=None):
    if not key:
        raise CoachError("Add your OpenAI key in Settings → AI to get a coach review.")
    raw = _ask(context, key, model or os.environ.get("OPENAI_COACH_MODEL") or "gpt-4.1")
    return clean(raw, context)


def clean(raw, context):
    """Keep only well-formed fields so the page never renders junk."""
    if not isinstance(raw, dict):
        raise CoachError("The coach reply was not readable. Try again.")
    plans = {plan["key"]: plan for plan in context.get("roadmaps") or []}
    recommended = raw.get("recommended") if raw.get("recommended") in plans else (next(iter(plans), None))
    phase_count = len(plans[recommended]["phases"]) if recommended in plans else 0
    notes = []
    for item in raw.get("phase_notes") or []:
        if isinstance(item, dict) and isinstance(item.get("phase"), int) and 0 <= item["phase"] < phase_count:
            notes.append({"phase": item["phase"], "note": _text(item.get("note"), 240)})
    tweak = raw.get("goal_tweak")
    if isinstance(tweak, dict) and _number(tweak.get("bf_percent")) and _number(tweak.get("ffmi")):
        tweak = {"bf_percent": round(float(tweak["bf_percent"]), 1), "ffmi": round(float(tweak["ffmi"]), 1),
                 "reason": _text(tweak.get("reason"), 240)}
    else:
        tweak = None
    return {
        "headline": _text(raw.get("headline"), 140) or "Here is your roadmap.",
        "verdict": raw.get("verdict") if raw.get("verdict") in VERDICTS else "ambitious",
        "recommended": recommended,
        "why": _texts(raw.get("why"), 4),
        "phase_notes": notes,
        "this_month": _texts(raw.get("this_month"), 3),
        "watch_outs": _texts(raw.get("watch_outs"), 3),
        "plan_fit": _text(raw.get("plan_fit"), 400),
        "goal_tweak": tweak,
    }


def _ask(context, key, model):
    import urllib.error
    import urllib.request

    body = {
        "model": model,
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": json.dumps(context, default=str)},
        ],
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer %s" % key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as err:
        if err.code == 401:
            raise CoachError("OpenAI rejected the key in Settings → AI.") from err
        if err.code == 429:
            raise CoachError("OpenAI is rate limiting this key or it has no credit left. Try again later.") from err
        raise CoachError("OpenAI could not answer (HTTP %s). Try again." % err.code) from err
    except Exception as err:
        raise CoachError("The coach took too long to answer. Try again.") from err
    try:
        return json.loads(payload["choices"][0]["message"]["content"])
    except (KeyError, IndexError, ValueError) as err:
        raise CoachError("The coach reply was not readable. Try again.") from err


def _text(value, limit):
    return str(value).strip()[:limit] if isinstance(value, str) and value.strip() else ""


def _texts(values, limit):
    return [text for text in (_text(value, 300) for value in (values or []) if isinstance(values, list)) if text][:limit]


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)
