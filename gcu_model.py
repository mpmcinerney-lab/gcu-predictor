"""
GCU Pace Predictor — Model & Analysis Reference
=================================================
Giant's Cup Uncut 2026 (61.4km mountain ultra, Drakensberg, South Africa)
Race date: Saturday 25 April 2026, start 06:00

This module contains all data, calibration workings, and prediction logic
that underpin the GCU pace predictor web tool.

Data sources:
  - Course GPX:   GCU62.V2.Dec03.gpx (Strava route by Stuart McConnachie)
  - Race PDF:     "GCU Route and Aid Stations.pdf" (official 2026 race info)
  - Race results: tan.sportraxs.com/events/517/races/1255 (2025 GCU actual results)
  - Strava MCP:   Segment details for named sub-segments on the course
"""

from dataclasses import dataclass, field
from typing import Optional

# =============================================================================
# 1. COURSE DATA
# =============================================================================

RACE_NAME = "Giant's Cup Uncut 2026"
RACE_DATE = "2026-04-25"
RACE_START_HOUR = 6  # 06:00
TOTAL_KM = 61.4
TOTAL_ASCENT_M = 2071  # from race PDF


@dataclass
class Checkpoint:
    name: str
    km: float
    elevation_m: int
    cutoff_minutes: Optional[int]  # elapsed minutes from start, or None


CHECKPOINTS = [
    Checkpoint("Silverstreams", 0, 1757, None),
    Checkpoint("Swiman", 14.3, 1836, None),
    Checkpoint("Castleburn", 28.2, 1615, 360),       # 6h cutoff
    Checkpoint("Mzimkulwana Hut", 39.6, 1629, 570),  # 9h30 cutoff
    Checkpoint("Cobham", 48.2, 1635, None),
    Checkpoint("Sani", 61.4, 1537, 870),              # 14h30 cutoff
]


@dataclass
class Segment:
    """Data for the segment ARRIVING at the corresponding checkpoint (index 1-5)."""
    distance_km: float
    ascent_m: int
    descent_m: int
    peak_m: int
    technicality: float   # 0-1, how technical (affects weather modifier)
    climb_weight: float   # 0-1, proportion of segment character that is climbing
    description: str


SEGMENTS = [
    # Seg 1: Start -> Swiman
    Segment(
        distance_km=14.3, ascent_m=596, descent_m=515, peak_m=2148,
        technicality=0.9, climb_weight=0.7,
        description="Langalibalele Pass 4km at 9% (max 46%). Peak 2148m. Technical descent."
    ),
    # Seg 2: Swiman -> Castleburn
    Segment(
        distance_km=13.9, ascent_m=326, descent_m=534, peak_m=2007,
        technicality=0.9, climb_weight=0.3,
        description="Black Eagle Pass 2.7km at 13% (max 47%). 3.6km descent at -9%."
    ),
    # Seg 3: Castleburn -> Mzimkulwana Hut
    Segment(
        distance_km=11.4, ascent_m=489, descent_m=534, peak_m=1973,
        technicality=1.0, climb_weight=0.7,
        description="Hardest climbing. Umzimkhulu 0.9km at 17% (max 50%). Crane Tarn. 3.7km descent."
    ),
    # Seg 4: Mzimkulwana Hut -> Cobham
    Segment(
        distance_km=8.6, ascent_m=309, descent_m=302, peak_m=1841,
        technicality=0.5, climb_weight=0.3,
        description="Shortest segment. Rolling, then Cobham Descent 2.4km at -9%."
    ),
    # Seg 5: Cobham -> Sani
    Segment(
        distance_km=13.2, ascent_m=351, descent_m=440, peak_m=1852,
        technicality=0.7, climb_weight=0.35,
        description="Cobham climb 3.7km at 5%. River section. Sani Hotel Descent 1km at -18%."
    ),
]


# =============================================================================
# 2. STRAVA SEGMENT DETAIL
# =============================================================================
# Sourced via Strava MCP (explore-segments + get-segment) for named sub-segments
# on the GCU course. These reveal the true terrain character that averaged
# checkpoint-to-checkpoint stats obscure.

STRAVA_SEGMENTS = {
    # Segment ID: (name, distance_km, avg_grade_pct, max_grade_pct, elev_gain_m, elev_high_m)
    28160669: ("Langalibalele Pass",         4.04,   9.3, 46.3, 387, 2152),
    18666524: ("Black Eagle Pass (climb)",   2.70,  13.4, 47.1, 387, 1999),
    25725630: ("Black Eagle Pass (descent)", 3.60,  -8.7, 23.2,  27, 1987),
    23461953: ("Umzimkhulu Ascent",          0.86,  17.0, 49.5, 151, 1789),
    20483888: ("Crane Tarn Climb",           3.65,   9.0, 40.9, 337, 1963),
    23220647: ("Picnic Falls to Crane Tarn", 1.60,   9.6, 47.0, 155, 1966),
    28218543: ("Cobham Descent",             2.42,  -8.7,  7.1,   4, 1845),
    20438253: ("DV Up the Gxailingenwa",     4.12,   5.0, 44.6, 275, 1777),
    22633290: ("Sani Hotel Descent",         1.05, -18.0, -2.0,   0, 1763),
    28200545: ("UTD Final sprint",           4.29,  -3.5, 35.8,  42, 1729),
}

# Key insight: max grades of 40-50% on multiple sub-segments means this is
# scrambling terrain, not runnable trail. These features dictate pace in ways
# that averaged segment stats completely miss.


# =============================================================================
# 3. REFERENCE PACE PROFILES
# =============================================================================
# Cumulative elapsed minutes at each checkpoint [Start, Swiman, Castleburn,
# Mzimkulwana, Cobham, Finish].
#
# Profiles 0-5 are from 2025 GCU actual race data (tan.sportraxs.com).
# Profile 6 is the 2026 race PDF back-runner estimate.
#
# Source: Individual athlete pages on sportraxs for the 2025 GCU 65km race.
# Note: 2025 race started at 05:00, distances differ slightly from 2026 PDF
# (63.6km vs 61.4km). Splits are mapped to 2026 checkpoint structure.

@dataclass
class ReferenceRunner:
    name: str
    finish_time: str
    position: str
    source: str
    splits_minutes: list  # [Start, Swiman, Castleburn, Mzimkulwana, Cobham, Finish]


REFERENCE_RUNNERS = [
    ReferenceRunner(
        "Admire Muzopambwa", "6:01:44", "#1 overall",
        "sportraxs athlete/96033",
        [0, 73, 139, 212, 266, 362]
    ),
    ReferenceRunner(
        "Olivia Dubern", "7:08:28", "#6 overall, #1 female",
        "sportraxs athlete/96041",
        [0, 85, 164, 248, 311, 429]
    ),
    ReferenceRunner(
        "Dylan Jacklin", "8:10:02", "#17 overall",
        "sportraxs athlete/96091",
        [0, 92, 179, 280, 357, 490]
    ),
    ReferenceRunner(
        "Chris Carter", "8:44:02", "#23 overall, #1 master male",
        "sportraxs athlete/96072",
        [0, 105, 196, 301, 379, 524]
    ),
    ReferenceRunner(
        "Mark Tait", "9:02:26", "#28 overall",
        "sportraxs athlete/96152",
        [0, 111, 213, 322, 401, 542]
    ),  # ★ NEW
    ReferenceRunner(
        "Kelly Blair", "9:36:58", "#40 overall",
        "sportraxs athlete/96211",
        [0, 123, 223, 332, 419, 577]
    ),
    ReferenceRunner(
        "Darryl Munn", "10:14:46", "#72 overall",
        "sportraxs athlete/96083",
        [0, 125, 231, 358, 449, 615]
    ),  # ★ NEW
    ReferenceRunner(
        "Jurie Schoeman", "11:09:19", "#101 overall",
        "sportraxs athlete/96133",
        [0, 126, 252, 391, 492, 669]
    ),  # ★ NEW
    ReferenceRunner(
        "Mary Claire Worrell", "12:19:38", "#132 overall",
        "sportraxs athlete/96153",
        [0, 133, 267, 420, 538, 740]
    ),
    ReferenceRunner(
        "Karl Reith", "13:15:47", "#154 overall",
        "sportraxs athlete/96134",
        [0, 138, 287, 471, 585, 796]
    ),  # ★ NEW
    ReferenceRunner(
        "2026 PDF back runner estimate", "14:30:00", "back of pack",
        "GCU Route and Aid Stations.pdf",
        [0, 175, 335, 505, 660, 870]
    ),
]

# The raw array used by the prediction engine
PROFILES = [r.splits_minutes for r in REFERENCE_RUNNERS]


# =============================================================================
# 4. SEGMENT PROPORTIONALITY ANALYSIS
# =============================================================================
# Key question: does linear interpolation between profiles hold, or do slower
# runners spend disproportionately more time on certain segments?
#
# Analysis: compute each segment's share of total race time across profiles.

def analyse_segment_proportions():
    """Show that segment time proportions are stable across ability levels."""
    n_cp = len(CHECKPOINTS)
    results = []
    for runner in REFERENCE_RUNNERS:
        sp = runner.splits_minutes
        total = sp[-1]
        if total == 0:
            continue
        segs = []
        for i in range(1, n_cp):
            seg_time = sp[i] - sp[i - 1]
            pct = seg_time / total * 100
            segs.append(pct)
        results.append({
            "name": runner.name,
            "finish_min": total,
            "seg_pcts": segs,
        })

    print("Segment time as % of total race time:")
    print(f"{'Runner':<25} {'Finish':>7}  ", end="")
    for i, cp in enumerate(CHECKPOINTS[1:], 1):
        print(f"{'Seg'+str(i):>6}", end="")
    print()
    print("-" * 80)
    for r in results:
        print(f"{r['name']:<25} {r['finish_min']:>5}m  ", end="")
        for p in r["seg_pcts"]:
            print(f"{p:>5.1f}%", end="")
        print()

    # Compute range (max - min) for each segment across profiles
    print("\nVariance (max% - min%) per segment:")
    for si in range(len(CHECKPOINTS) - 1):
        pcts = [r["seg_pcts"][si] for r in results]
        print(f"  Seg {si+1} ({CHECKPOINTS[si].name} -> {CHECKPOINTS[si+1].name}): "
              f"{min(pcts):.1f}% - {max(pcts):.1f}% (range {max(pcts)-min(pcts):.1f}%)")

    # Conclusion: proportions vary only 1-3% across ability levels.
    # Linear interpolation between profiles is well-supported for this course.


# =============================================================================
# 5. PREDICTION ENGINE
# =============================================================================

@dataclass
class PredictionInput:
    """All optional inputs to the prediction engine."""
    # Checkpoint elapsed times: {checkpoint_index: minutes}
    checkpoint_times: dict = field(default_factory=dict)
    # HR at each checkpoint: {checkpoint_index: bpm}
    checkpoint_hr: dict = field(default_factory=dict)
    # Athlete profile (pre-race)
    max_hr: Optional[int] = None
    resting_hr: Optional[int] = None
    marathon_minutes: Optional[int] = None
    trail_experience: str = "intermediate"  # novice, intermediate, experienced
    # Conditions
    temperature_c: int = 15
    trail_condition: str = "dry"  # dry, wet, muddy


@dataclass
class CheckpointPrediction:
    minutes: float
    is_future: bool
    is_entered: bool
    is_pre_race: bool = False
    lo: Optional[float] = None  # range low (pre-race only)
    hi: Optional[float] = None  # range high (pre-race only)


@dataclass
class PredictionResult:
    predictions: dict  # {checkpoint_index: CheckpointPrediction}
    fade_rate: Optional[float]  # min/hr, None if insufficient data
    estimated_finish: Optional[float]  # minutes
    finish_range_lo: Optional[float] = None  # pre-race range
    finish_range_hi: Optional[float] = None  # pre-race range


def _interpolate_profiles(checkpoint_index: int, elapsed_minutes: float) -> list:
    """
    Given a runner's elapsed time at a specific checkpoint, interpolate between
    the two bracketing reference profiles to predict times at all checkpoints.

    This is the core of the model. Because the reference profiles are from real
    runners on this specific course, the terrain difficulty is inherently captured
    in the split ratios — steep scrambles, technical descents, altitude, etc. are
    all encoded in how long each segment took relative to the whole.

    Alpha is clamped to [0, 1]. Runners faster than the fastest reference profile
    (alpha < 0) or slower than the slowest (alpha > 1) would require extrapolation
    beyond calibrated data; clamping returns the nearest boundary profile instead,
    which is the safest conservative estimate.

    Returns a list of predicted elapsed minutes at each checkpoint [0..5].
    """
    n = len(PROFILES)
    ci = checkpoint_index
    lo, hi = 0, 1

    if elapsed_minutes <= PROFILES[0][ci]:
        lo, hi = 0, 1
    elif elapsed_minutes >= PROFILES[-1][ci]:
        lo, hi = n - 2, n - 1
    else:
        for i in range(n - 1):
            if PROFILES[i][ci] <= elapsed_minutes <= PROFILES[i + 1][ci]:
                lo, hi = i, i + 1
                break

    rng = PROFILES[hi][ci] - PROFILES[lo][ci]
    alpha = (elapsed_minutes - PROFILES[lo][ci]) / rng if rng > 0 else 0
    alpha = max(0.0, min(1.0, alpha))  # clamp: never extrapolate beyond reference profiles

    return [PROFILES[lo][f] + alpha * (PROFILES[hi][f] - PROFILES[lo][f])
            for f in range(len(CHECKPOINTS))]


def _weather_multiplier(segment_index: int, temperature_c: int, trail_condition: str) -> float:
    """
    Compute a time multiplier for a segment based on weather/conditions.

    Temperature: each degree above 15C adds ~1.5% to segment time.
    Research basis: Ely et al. (2007) found ~1-2% pace reduction per degree C
    above optimal for endurance running, accelerating above 25C.

    Trail condition: applied proportional to segment technicality.
    - Wet: +8% on fully technical segments (steep scrambles on wet rock/grass)
    - Muddy: +15% on fully technical segments
    Rationale: the 40-50% max grade scrambles (Langalibalele, Black Eagle,
    Umzimkhulu) become dramatically slower and more dangerous when wet.
    Segments 1-3 have technicality 0.9-1.0; Segment 4 is 0.5 (most honest
    descent); Segment 5 is 0.7 (Sani Hotel descent is very steep but short).
    """
    seg = SEGMENTS[segment_index]
    modifier = max(0, (temperature_c - 15) * 0.015)

    if trail_condition == "wet":
        modifier += 0.08 * seg.technicality
    elif trail_condition == "muddy":
        modifier += 0.15 * seg.technicality

    return 1 + modifier


def _calc_fade(entries: list, profiles_fn=_interpolate_profiles) -> float:
    """
    Detect pace fade by tracking how the runner's position (alpha) drifts
    across checkpoints relative to the reference profiles.

    Method:
      1. For each entered checkpoint, compute the raw projected finish (what
         finish time would be predicted if the runner held that relative position).
      2. Accumulate only the POSITIVE drift from each consecutive pair of entries.
         Negative pair drifts (apparent improvement on a segment) are clamped to 0
         per-pair, preventing spurious "runner is improving" signals.
      3. Divide total positive drift by total elapsed hours, apply 0.5x dampening.

    Per-pair comparison (not running-max) is critical: a runner who improved on
    segment N and then faded on segment N+1 should show a fade signal relative to
    their performance at checkpoint N — not relative to their earliest entry. A
    running-max clamp would carry the early high baseline forward and create a
    dead zone where genuine later-segment fading is invisible.

    Returns fade rate in minutes per hour. Positive = slowing. Zero = steady pace.
    """
    if len(entries) < 2:
        return 0

    fins = [profiles_fn(e["cp"], e["min"])[-1] for e in entries]

    # Sum positive drifts from consecutive pairs only; negative pairs contribute 0
    total_positive_drift = sum(
        max(0.0, fins[i + 1] - fins[i]) for i in range(len(fins) - 1)
    )

    hours_elapsed = (entries[-1]["min"] - entries[0]["min"]) / 60
    if hours_elapsed <= 0:
        return 0

    return (total_positive_drift / hours_elapsed) * 0.5  # dampened; always >= 0


def _hr_fade_modifier(fade: float, max_hr: Optional[int], resting_hr: Optional[int],
                      current_hr: Optional[int]) -> float:
    """
    Modify the fade rate based on heart rate effort level.

    Uses Heart Rate Reserve (%HRR) which is more accurate than %HRmax for
    comparing effort across individuals with different resting HRs.

    %HRR = (current - resting) / (max - resting)

    Modifier table:
      %HRR < 60%:  0.5x fade (large reserves, conservative effort)
      60-75%:       1.0x fade (sustainable effort)
      75-85%:       1.5x fade (threshold effort, will cost later)
      > 85%:        2.0x fade (redlining, significant slowdown expected)

    Rationale: two runners at the same checkpoint at the same time but different
    HRs are in very different states. The one at 92% HRmax is redlining; the one
    at 78% has reserves. HR directly predicts future fade.
    """
    if not max_hr or not current_hr:
        return fade

    rest = resting_hr or 60
    hrr = min(1, max(0, (current_hr - rest) / (max_hr - rest)))

    if hrr > 0.85:
        modifier = 2.0
    elif hrr > 0.75:
        modifier = 1.5
    elif hrr > 0.60:
        modifier = 1.0
    else:
        modifier = 0.5

    return fade * modifier


def _cardiac_drift(entries: list, max_hr: Optional[int]) -> float:
    """
    Detect cardiac drift: HR rising across checkpoints at similar pace.

    If HR is trending upward while pace holds steady, the runner is silently
    accumulating fatigue. This predicts steeper fade even before pace drops.

    Trend is expressed in bpm/hr (not bpm/checkpoint) so it is independent of
    how many checkpoints were entered and of variable inter-checkpoint gaps.

    Thresholds:
      > 5 bpm/hr:  strong drift signal -> +0.3 min/hr extra fade
      > 2 bpm/hr:  moderate drift      -> +0.15 min/hr extra fade

    Returns additional fade rate to add (min/hr).
    """
    hr_entries = [e for e in entries if e.get("hr")]
    if len(hr_entries) < 2 or not max_hr:
        return 0

    elapsed_hrs = (hr_entries[-1]["min"] - hr_entries[0]["min"]) / 60.0
    if elapsed_hrs <= 0:
        return 0

    trend_per_hr = (hr_entries[-1]["hr"] - hr_entries[0]["hr"]) / elapsed_hrs
    if trend_per_hr > 5:
        return 0.3
    elif trend_per_hr > 2:
        return 0.15
    return 0


def _terrain_bias(entries: list) -> Optional[dict]:
    """
    Detect if the runner has a climb bias vs descent bias by comparing their
    interpolation position (alpha) at climb-heavy vs descent-heavy checkpoints.

    Climb-heavy checkpoints: Swiman (1), Mzimkulwana (3) — both follow
    segments with major ascents.
    Descent-heavy checkpoints: Castleburn (2), Cobham (4) — both follow
    segments with net descent and technical descents.

    If the runner's projected finish differs significantly between climb-heavy
    and descent-heavy checkpoints, apply a small correction to future segments
    based on their terrain character.

    Returns dict with 'climb_finish' and 'descent_finish' projected finishes,
    or None if insufficient data.
    """
    climb_cps = [1, 3]   # post-climb checkpoints
    descent_cps = [2, 4]  # post-descent checkpoints

    climb_fins, descent_fins = [], []
    for e in entries:
        projected_finish = _interpolate_profiles(e["cp"], e["min"])[-1]
        if e["cp"] in climb_cps:
            climb_fins.append(projected_finish)
        if e["cp"] in descent_cps:
            descent_fins.append(projected_finish)

    if not climb_fins or not descent_fins:
        return None

    return {
        "climb_finish": sum(climb_fins) / len(climb_fins),
        "descent_finish": sum(descent_fins) / len(descent_fins),
    }


def predict(inp: PredictionInput) -> PredictionResult:
    """
    Main prediction pipeline.

    Layer 1 — Baseline interpolation:
      Use most recent checkpoint time to interpolate between reference profiles.
      Terrain difficulty is inherently captured because reference splits are from
      real runners on this course.

    Layer 2 — Pace fade:
      With 2+ checkpoint times, detect alpha drift rate. HR data modifies the
      drift multiplier. Cardiac drift adds additional fade signal.

    Layer 3 — Terrain bias:
      If runner shows different alpha at climb-heavy vs descent-heavy checkpoints,
      adjust future segment predictions based on terrain character.

    Layer 4 — Weather modifier:
      Temperature and trail conditions applied per-segment, weighted by
      technicality.

    Layer 5 — Pre-race estimate (fallback):
      If no checkpoint times entered, use marathon time + trail experience to
      estimate a finish range. Returns range, not point estimate.
    """
    n_cp = len(CHECKPOINTS)

    # Build entries from checkpoint times
    entries = sorted(
        [{"cp": cp, "min": mins, "hr": inp.checkpoint_hr.get(cp)}
         for cp, mins in inp.checkpoint_times.items()],
        key=lambda e: e["cp"]
    )

    # --- No checkpoint data: use pre-race estimate ---
    if not entries:
        return _pre_race_predict(inp)

    # --- Layer 1: Baseline interpolation from most recent checkpoint ---
    last = entries[-1]
    base = _interpolate_profiles(last["cp"], last["min"])

    # --- Layer 2: Fade ---
    fade = _calc_fade(entries)
    last_hr = last.get("hr")
    fade = _hr_fade_modifier(fade, inp.max_hr, inp.resting_hr, last_hr)
    fade += _cardiac_drift(entries, inp.max_hr)
    # --- Layer 3: Terrain bias ---
    bias = _terrain_bias(entries) if len(entries) >= 2 else None

    # --- Compute predictions ---
    base_finish = base[-1]
    remaining = base_finish - last["min"]
    # Cap the fade used for finish-time projection only. A fade above 15 min/hr
    # would produce runaway predictions (total_fade = fade * remaining/60 grows
    # explosively for extreme split combinations). The raw fade rate is preserved
    # for the fade_rate field so the UI label can still show "Significant fade".
    fade_for_projection = min(fade, 15.0)
    total_fade = fade_for_projection * (remaining / 60) if remaining > 0 else 0

    predictions = {}
    cumulative = last["min"]

    for f in range(last["cp"] + 1, n_cp):
        seg_base = base[f] - base[f - 1]

        # Terrain bias adjustment
        if bias:
            seg = SEGMENTS[f - 1]
            avg = (bias["climb_finish"] + bias["descent_finish"]) / 2
            strength = (bias["descent_finish"] - bias["climb_finish"]) / avg
            cw = seg.climb_weight
            dw = 1 - cw
            bias_adj = cw * (-strength) + dw * strength
            seg_base *= (1 + max(-0.08, min(0.08, bias_adj)))

        # Layer 4: Weather
        seg_base *= _weather_multiplier(f - 1, inp.temperature_c, inp.trail_condition)

        # Apply fade proportionally
        seg_proportion = (base[f] - base[f - 1]) / remaining if remaining > 0 else 0
        seg_base += total_fade * seg_proportion

        cumulative += seg_base
        predictions[f] = CheckpointPrediction(
            minutes=cumulative, is_future=True, is_entered=False
        )

    # Past checkpoints
    for f in range(1, last["cp"] + 1):
        if f in inp.checkpoint_times:
            predictions[f] = CheckpointPrediction(
                minutes=inp.checkpoint_times[f], is_future=False, is_entered=True
            )
        else:
            predictions[f] = CheckpointPrediction(
                minutes=base[f], is_future=False, is_entered=False
            )

    # Hard cap at the finish cutoff. Anything beyond 870 min means the runner
    # will not finish within the official time limit regardless of exact pace.
    finish_cutoff = CHECKPOINTS[-1].cutoff_minutes  # 870 min
    finish = predictions.get(n_cp - 1)
    raw_finish = finish.minutes if finish else cumulative
    capped_finish = min(raw_finish, finish_cutoff) if finish_cutoff else raw_finish
    if finish and capped_finish < finish.minutes:
        predictions[n_cp - 1] = CheckpointPrediction(
            minutes=capped_finish, is_future=True, is_entered=False
        )
    return PredictionResult(
        predictions=predictions,
        fade_rate=fade,
        estimated_finish=capped_finish,
    )


def _pre_race_predict(inp: PredictionInput) -> PredictionResult:
    """
    Pre-race prediction from marathon time + trail experience.

    Produces a RANGE, not a point estimate, reflecting the inherent uncertainty
    of mapping road marathon fitness to mountain ultra performance.

    Calibration (from 2025 GCU data):
      - Kelly Blair: sub-4hr marathon -> 9:36 GCU = 2.45x ratio
      - Athlete B:   3:38 marathon    -> 8:48 GCU = 2.42x ratio
      - Both cluster around 2.4-2.5x, NOT the commonly-assumed 2.0-2.2x

    Base multiplier: 2.5x marathon time
    Experience modifiers:
      - Novice:       1.3x (no mountain ultra experience adds ~30%)
      - Intermediate:  1.1x (some trail experience, but GCU-specific terrain is extreme)
      - Experienced:   0.95x (strong mountain/ultra background)

    Range: +/- 12% around the point estimate.
    Rationale: even among experienced runners with similar marathon times, GCU
    finish times vary by ~20%. Factors marathon time cannot predict:
      - Technical descent ability (47% max grade scrambles)
      - Altitude tolerance (entire race above 1500m)
      - Ultra-specific fueling/pacing discipline
      - Mountain-specific quad strength
    """
    if inp.marathon_minutes is None or inp.marathon_minutes <= 0:
        return PredictionResult(predictions={}, fade_rate=None, estimated_finish=None)

    experience_multipliers = {"novice": 1.3, "intermediate": 1.1, "experienced": 0.95}
    exp_mult = experience_multipliers.get(inp.trail_experience, 1.1)

    mid_estimate = max(300, min(1000, inp.marathon_minutes * 2.5 * exp_mult))
    lo_estimate = mid_estimate * 0.88
    hi_estimate = mid_estimate * 1.12

    def interp_finish(est):
        n = len(PROFILES)
        fi = len(CHECKPOINTS) - 1
        lo_idx, hi_idx = 0, 1
        if est <= PROFILES[0][fi]:
            lo_idx, hi_idx = 0, 1
        elif est >= PROFILES[-1][fi]:
            lo_idx, hi_idx = n - 2, n - 1
        else:
            for i in range(n - 1):
                if PROFILES[i][fi] <= est <= PROFILES[i + 1][fi]:
                    lo_idx, hi_idx = i, i + 1
                    break
        rng = PROFILES[hi_idx][fi] - PROFILES[lo_idx][fi]
        alpha = (est - PROFILES[lo_idx][fi]) / rng if rng > 0 else 0
        return [PROFILES[lo_idx][f] + alpha * (PROFILES[hi_idx][f] - PROFILES[lo_idx][f])
                for f in range(len(CHECKPOINTS))]

    p_mid = interp_finish(mid_estimate)
    p_lo = interp_finish(lo_estimate)
    p_hi = interp_finish(hi_estimate)

    n_cp = len(CHECKPOINTS)
    predictions = {}
    # Weather must be applied to segment durations, not cumulative times.
    # Accumulate weather-adjusted cumulative times for each variant separately.
    cum_mid = cum_lo = cum_hi = 0.0
    for f in range(1, n_cp):
        wm = _weather_multiplier(f - 1, inp.temperature_c, inp.trail_condition)
        cum_mid += (p_mid[f] - p_mid[f - 1]) * wm
        cum_lo  += (p_lo[f]  - p_lo[f - 1])  * wm
        cum_hi  += (p_hi[f]  - p_hi[f - 1])  * wm
        predictions[f] = CheckpointPrediction(
            minutes=cum_mid,
            lo=cum_lo,
            hi=cum_hi,
            is_future=True,
            is_entered=False,
            is_pre_race=True,
        )

    fi = n_cp - 1
    return PredictionResult(
        predictions=predictions,
        fade_rate=None,
        estimated_finish=predictions[fi].minutes if fi in predictions else None,
        finish_range_lo=predictions[fi].lo if fi in predictions else None,
        finish_range_hi=predictions[fi].hi if fi in predictions else None,
    )


# =============================================================================
# 6. ELEVATION PROFILE
# =============================================================================
# 120 evenly-spaced points sampled from the GPX file using Haversine distance.
# Total route distance: 61.37km (GPX) vs 61.4km (PDF).

ELEVATION_PROFILE = [
    (0.0, 1757.1), (0.52, 1753.1), (1.03, 1766.3), (1.55, 1818.9),
    (2.06, 1876.2), (2.58, 1963.6), (3.09, 1990.9), (3.61, 2067.1),
    (4.13, 2079.4), (4.64, 2148.3), (5.16, 2137.1), (5.67, 2112.3),
    (6.19, 2083.8), (6.7, 2078.7), (7.22, 2061.7), (7.74, 1978.1),
    (8.25, 1927.7), (8.77, 1892.9), (9.28, 1823.9), (9.8, 1856.4),
    (10.31, 1937.4), (10.83, 1928.4), (11.34, 1924.1), (11.86, 1903.5),
    (12.38, 1873.9), (12.89, 1859.8), (13.41, 1847.1), (13.92, 1839.8),
    (14.44, 1837.2), (14.95, 1845.4), (15.47, 1849.7), (15.99, 1861.6),
    (16.5, 1870.4), (17.02, 1871.8), (17.53, 1882.5), (18.05, 1937.3),
    (18.56, 1983.5), (19.08, 1976.7), (19.6, 1989.3), (20.11, 1980.5),
    (20.63, 1989.6), (21.14, 2003.6), (21.66, 1999.9), (22.17, 1990.1),
    (22.69, 1976.4), (23.21, 1986.2), (23.72, 2003.5), (24.24, 1956.4),
    (24.75, 1862.9), (25.27, 1806.0), (25.78, 1725.5), (26.3, 1664.8),
    (26.82, 1637.1), (27.33, 1643.9), (27.85, 1683.8), (28.36, 1616.7),
    (28.88, 1619.6), (29.39, 1622.0), (29.91, 1647.1), (30.42, 1665.4),
    (30.94, 1640.1), (31.46, 1721.2), (31.97, 1776.6), (32.49, 1771.5),
    (33.0, 1750.9), (33.52, 1760.3), (34.03, 1800.9), (34.55, 1832.0),
    (35.07, 1898.0), (35.58, 1961.6), (36.1, 1930.3), (36.61, 1877.4),
    (37.13, 1844.6), (37.64, 1765.6), (38.16, 1714.9), (38.68, 1698.6),
    (39.19, 1652.6), (39.71, 1630.2), (40.22, 1681.2), (40.74, 1733.0),
    (41.25, 1785.6), (41.77, 1793.3), (42.29, 1785.2), (42.8, 1812.3),
    (43.32, 1829.0), (43.83, 1831.5), (44.35, 1815.1), (44.86, 1815.1),
    (45.38, 1830.6), (45.9, 1835.7), (46.41, 1765.5), (46.93, 1726.6),
    (47.44, 1657.9), (47.96, 1624.2), (48.47, 1626.5), (48.99, 1618.9),
    (49.5, 1629.5), (50.02, 1644.9), (50.54, 1660.9), (51.05, 1680.0),
    (51.57, 1730.3), (52.08, 1756.7), (52.6, 1813.3), (53.11, 1829.4),
    (53.63, 1836.3), (54.15, 1837.6), (54.66, 1845.6), (55.18, 1833.0),
    (55.69, 1795.3), (56.21, 1777.0), (56.72, 1755.9), (57.24, 1699.3),
    (57.76, 1679.1), (58.27, 1631.9), (58.79, 1583.8), (59.3, 1581.7),
    (59.82, 1573.5), (60.33, 1567.4), (60.85, 1545.2), (61.37, 1536.7),
]


# =============================================================================
# 7. UTILITY FUNCTIONS
# =============================================================================

def format_elapsed(minutes: Optional[float]) -> str:
    """Format elapsed minutes as H:MM."""
    if minutes is None:
        return "--:--"
    h = int(minutes // 60)
    m = round(minutes % 60)
    return f"{h}:{m:02d}"


def format_clock(minutes: Optional[float]) -> str:
    """Format elapsed minutes as clock time (HH:MM) given 06:00 start."""
    if minutes is None:
        return "--:--"
    total = RACE_START_HOUR * 60 + round(minutes)
    h = total // 60
    m = total % 60
    return f"{h:02d}:{m:02d}"


# =============================================================================
# 8. DEMO / VALIDATION
# =============================================================================

def validate_model():
    """
    Validate predictions against known 2025 race data.
    Enter Kelly Blair's actual Swiman split and check downstream predictions.
    """
    print("=" * 70)
    print("MODEL VALIDATION: Kelly Blair (actual GCU finish: 9:36)")
    print("=" * 70)

    # Pre-race estimate: sub-4hr marathon, experienced
    inp_pre = PredictionInput(marathon_minutes=235, trail_experience="experienced")
    res_pre = _pre_race_predict(inp_pre)
    print(f"\nPre-race estimate (3:55 marathon, experienced):")
    print(f"  Finish range: {format_elapsed(res_pre.finish_range_lo)} - "
          f"{format_elapsed(res_pre.finish_range_hi)}")
    print(f"  Actual 9:36 falls within range: "
          f"{res_pre.finish_range_lo <= 576 <= res_pre.finish_range_hi}")

    # After Swiman (checkpoint 1): entered 2:03
    inp1 = PredictionInput(checkpoint_times={1: 123})
    res1 = predict(inp1)
    print(f"\nAfter Swiman (entered 2:03 elapsed):")
    print(f"  Predicted finish: {format_elapsed(res1.estimated_finish)}")
    for cp_idx, pred in sorted(res1.predictions.items()):
        cp = CHECKPOINTS[cp_idx]
        status = "entered" if pred.is_entered else "projected"
        print(f"  {cp.name}: {format_elapsed(pred.minutes)} ({format_clock(pred.minutes)}) [{status}]")

    # After Castleburn (checkpoint 2): entered 3:43
    inp2 = PredictionInput(checkpoint_times={1: 123, 2: 223})
    res2 = predict(inp2)
    print(f"\nAfter Castleburn (entered 2:03 + 3:43):")
    print(f"  Fade rate: {res2.fade_rate:.1f} min/hr")
    print(f"  Predicted finish: {format_elapsed(res2.estimated_finish)}")
    for cp_idx, pred in sorted(res2.predictions.items()):
        cp = CHECKPOINTS[cp_idx]
        status = "entered" if pred.is_entered else "projected"
        print(f"  {cp.name}: {format_elapsed(pred.minutes)} ({format_clock(pred.minutes)}) [{status}]")

    # Full splits entered
    print(f"\n--- Kelly Blair's actual splits for reference ---")
    actual = [0, 123, 223, 332, 419, 577]
    for i, cp in enumerate(CHECKPOINTS):
        print(f"  {cp.name}: {format_elapsed(actual[i])} ({format_clock(actual[i])})")


if __name__ == "__main__":
    analyse_segment_proportions()
    print()
    validate_model()
