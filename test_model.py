"""
Comprehensive test suite for gcu_model.py
Run: python test_model.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from gcu_model import (
    predict, _pre_race_predict, _interpolate_profiles, _calc_fade,
    _cardiac_drift, _weather_multiplier, _terrain_bias,
    PredictionInput, PROFILES, CHECKPOINTS, format_elapsed,
)

PASS = 0
FAIL = 0
WARN = 0


def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        print(f"  PASS  {label}")
        PASS += 1
    else:
        print(f"  FAIL  {label}" + (f" — {detail}" if detail else ""))
        FAIL += 1


def warn(label, detail=""):
    global WARN
    print(f"  WARN  {label}" + (f" — {detail}" if detail else ""))
    WARN += 1


# ===========================================================================
# 1. _interpolate_profiles: boundary clamping
# ===========================================================================
print("\n=== 1. _interpolate_profiles boundary clamping ===")

# Fastest possible runner at Swiman (way under profile 0)
p = _interpolate_profiles(1, 10)
check("alpha clamped low: finish >= profile-0 finish",
      p[-1] >= PROFILES[0][-1] - 0.01,
      f"got finish={p[-1]:.1f}, profile0 finish={PROFILES[0][-1]}")

# Slowest possible runner at Swiman (way over profile -1)
p = _interpolate_profiles(1, 999)
check("alpha clamped high: finish <= profile-10 finish",
      p[-1] <= PROFILES[-1][-1] + 0.01,
      f"got finish={p[-1]:.1f}, profile-1 finish={PROFILES[-1][-1]}")

# Exact match at a profile boundary
p = _interpolate_profiles(1, PROFILES[5][1])
check("exact profile-5 Swiman -> finish == profile-5 finish",
      abs(p[-1] - PROFILES[5][-1]) < 0.01,
      f"got {p[-1]:.2f}, expected {PROFILES[5][-1]}")

# Internal interpolation: midpoint of two profiles
mid_sw = (PROFILES[3][1] + PROFILES[4][1]) / 2
p = _interpolate_profiles(1, mid_sw)
expected_finish = (PROFILES[3][-1] + PROFILES[4][-1]) / 2
check("midpoint interpolation finish within 0.1 min",
      abs(p[-1] - expected_finish) < 0.1,
      f"got {p[-1]:.2f}, expected {expected_finish:.2f}")

# Profile must be monotonically increasing (checkpoints are cumulative)
for ci in range(1, 6):
    p = _interpolate_profiles(ci, PROFILES[3][ci])
    is_mono = all(p[i] <= p[i+1] for i in range(len(p)-1))
    check(f"profile at ci={ci} is monotonically increasing", is_mono, str(p))


# ===========================================================================
# 2. _calc_fade: no negative fades
# ===========================================================================
print("\n=== 2. _calc_fade: monotonic enforcement / no negative fades ===")

# Scenario that used to produce negative fade (fast Swiman, mediocre Castleburn)
# Runner crosses profiles going "forward" — Swiman brackets 6/7, Castleburn 5/6
entries_neg = [{"cp": 1, "min": 125, "hr": None}, {"cp": 2, "min": 235, "hr": None}]
fade = _calc_fade(entries_neg)
check("fast Swiman + mediocre Castleburn: fade >= 0", fade >= 0, f"fade={fade:.3f}")

# Genuinely slow runner who is clearly fading
entries_slow = [{"cp": 1, "min": 100, "hr": None}, {"cp": 2, "min": 280, "hr": None}]
fade_slow = _calc_fade(entries_slow)
check("clearly fading runner: fade > 0", fade_slow > 0, f"fade={fade_slow:.3f}")

# Two identical checkpoint positions → fade = 0
entries_same = [{"cp": 1, "min": 111, "hr": None}, {"cp": 2, "min": 213, "hr": None}]
fade_same = _calc_fade(entries_same)
check("profile-4 exact splits: fade ~= 0", abs(fade_same) < 0.5, f"fade={fade_same:.3f}")

# Grid: all valid (sw, cb) pairs — no negative fades
neg_count = 0
total = 0
for sw in range(73, 176, 5):
    for cb in range(139, 340, 5):
        if cb <= sw:
            continue
        total += 1
        entries = [{"cp": 1, "min": sw, "hr": None}, {"cp": 2, "min": cb, "hr": None}]
        f = _calc_fade(entries)
        if f < 0:
            neg_count += 1
check(f"grid ({total} pairs): zero negative fades",
      neg_count == 0, f"{neg_count} negative fades found")

# Three-checkpoint grid
neg3 = 0
total3 = 0
for sw in range(73, 176, 10):
    for cb in range(139, 340, 10):
        if cb <= sw:
            continue
        for mz in range(212, 510, 25):
            if mz <= cb:
                continue
            total3 += 1
            entries = [{"cp": 1, "min": sw, "hr": None},
                       {"cp": 2, "min": cb, "hr": None},
                       {"cp": 3, "min": mz, "hr": None}]
            f = _calc_fade(entries)
            if f < 0:
                neg3 += 1
check(f"3-cp grid ({total3} triples): zero negative fades",
      neg3 == 0, f"{neg3} negative fades found")


# ===========================================================================
# 3. _weather_multiplier: sanity checks
# ===========================================================================
print("\n=== 3. _weather_multiplier ===")

check("dry 15C: multiplier = 1.0", _weather_multiplier(0, 15, "dry") == 1.0)
check("dry 25C: multiplier > 1.0", _weather_multiplier(0, 25, "dry") > 1.0)
check("muddy 15C technical seg: multiplier > dry 15C",
      _weather_multiplier(0, 15, "muddy") > _weather_multiplier(0, 15, "dry"))
check("muddy > wet > dry on technical segment",
      _weather_multiplier(0, 15, "muddy") > _weather_multiplier(0, 15, "wet") > 1.0)
# Seg 3 (index 2) is most technical (1.0); seg 3 (index 3) is least (0.5)
check("less technical seg has lower muddy modifier",
      _weather_multiplier(3, 15, "muddy") < _weather_multiplier(2, 15, "muddy"))
check("multiplier always >= 1.0 for any valid input",
      all(_weather_multiplier(s, t, c) >= 1.0
          for s in range(5)
          for t in [10, 15, 20, 30]
          for c in ["dry", "wet", "muddy"]))


# ===========================================================================
# 4. _pre_race_predict: weather fix verification
# ===========================================================================
print("\n=== 4. _pre_race_predict: weather modifier correctness ===")

inp_dry   = PredictionInput(marathon_minutes=240, trail_experience="intermediate",
                             temperature_c=15, trail_condition="dry")
inp_muddy = PredictionInput(marathon_minutes=240, trail_experience="intermediate",
                             temperature_c=15, trail_condition="muddy")
inp_hot   = PredictionInput(marathon_minutes=240, trail_experience="intermediate",
                             temperature_c=30, trail_condition="dry")

res_dry   = _pre_race_predict(inp_dry)
res_muddy = _pre_race_predict(inp_muddy)
res_hot   = _pre_race_predict(inp_hot)

fin_dry   = res_dry.estimated_finish
fin_muddy = res_muddy.estimated_finish
fin_hot   = res_hot.estimated_finish

check("muddy finish > dry finish", fin_muddy > fin_dry,
      f"muddy={fin_muddy:.1f}, dry={fin_dry:.1f}")
check("hot finish > dry finish", fin_hot > fin_dry,
      f"hot={fin_hot:.1f}, dry={fin_dry:.1f}")

# Key fix verification: weather delta should grow proportionally, not super-linearly.
# Before fix: applying wm to cumulative times meant each later CP got an ever-larger
# absolute penalty. After fix, the delta at finish should be roughly proportional to
# the sum of (seg_duration * wm_delta) — i.e. a reasonable absolute number.
# Muddy adds at most 15% to each segment. Expected finish delta ≈ fin_dry * 0.15 * avg_tech.
# avg technicality ≈ 0.72 → expected delta ≈ fin_dry * 0.15 * 0.72 ≈ 11% of dry finish.
# (Was ~15% of cumulative finish before fix, now should be ~11% or less.)
muddy_delta_pct = (fin_muddy - fin_dry) / fin_dry * 100
check("muddy finish delta is <15% of dry finish (not cumulatively over-inflated)",
      muddy_delta_pct < 15,
      f"muddy delta = {muddy_delta_pct:.1f}%")
check("muddy finish delta > 5% (conditions still have meaningful effect)",
      muddy_delta_pct > 5,
      f"muddy delta = {muddy_delta_pct:.1f}%")

# lo < mid < hi for all checkpoints
for cp_idx, pred in res_dry.predictions.items():
    check(f"pre-race cp {cp_idx}: lo <= minutes <= hi",
          pred.lo <= pred.minutes <= pred.hi,
          f"lo={pred.lo:.1f}, mid={pred.minutes:.1f}, hi={pred.hi:.1f}")

# Predictions should be monotonically increasing (later CPs = more elapsed time)
preds_dry = sorted(res_dry.predictions.items())
check("pre-race mid times are monotonically increasing",
      all(preds_dry[i][1].minutes < preds_dry[i+1][1].minutes for i in range(len(preds_dry)-1)),
      str([(k, f"{v.minutes:.0f}") for k, v in preds_dry]))

# Finish within race duration bounds
check("dry finish is within [300, 1000] min", 300 <= fin_dry <= 1000, f"fin={fin_dry:.1f}")


# ===========================================================================
# 5. predict(): full pipeline, post-race entries
# ===========================================================================
print("\n=== 5. predict() full pipeline ===")

# Single checkpoint — no fade
inp_1cp = PredictionInput(checkpoint_times={1: 123})
res_1 = predict(inp_1cp)
check("single cp: fade_rate is 0", res_1.fade_rate == 0 or res_1.fade_rate is None or res_1.fade_rate == 0.0,
      f"fade={res_1.fade_rate}")
check("single cp: finish predicted", res_1.estimated_finish is not None)
check("single cp: finish >= last entered cp time", res_1.estimated_finish >= 123)

# Two checkpoints — reference athlete (Kelly Blair actual splits)
inp_2cp = PredictionInput(checkpoint_times={1: 123, 2: 223})
res_2 = predict(inp_2cp)
check("2 cp: fade_rate >= 0", res_2.fade_rate >= 0, f"fade={res_2.fade_rate:.3f}")
check("2 cp: finish > cp2 time", res_2.estimated_finish > 223)
check("2 cp: finish in plausible range [350, 900]",
      350 <= res_2.estimated_finish <= 900, f"finish={res_2.estimated_finish:.1f}")

# Three checkpoints
inp_3cp = PredictionInput(checkpoint_times={1: 123, 2: 223, 3: 332})
res_3 = predict(inp_3cp)
check("3 cp: finish > cp3 time", res_3.estimated_finish > 332)
check("3 cp: predicted times are monotonically increasing",
      all(res_3.predictions[i].minutes <= res_3.predictions[i+1].minutes
          for i in sorted(res_3.predictions.keys())[:-1]),
      str({k: f"{v.minutes:.0f}" for k, v in res_3.predictions.items()}))

# All checkpoints except finish
inp_4cp = PredictionInput(checkpoint_times={1: 123, 2: 223, 3: 332, 4: 419})
res_4 = predict(inp_4cp)
check("4 cp: finish > cp4 time", res_4.estimated_finish > 419)

# With HR data — higher HR should produce more fade (and therefore longer finish)
inp_hr_high = PredictionInput(checkpoint_times={1: 123, 2: 223},
                               max_hr=185, resting_hr=55, checkpoint_hr={2: 175})
inp_hr_low  = PredictionInput(checkpoint_times={1: 123, 2: 223},
                               max_hr=185, resting_hr=55, checkpoint_hr={2: 130})
res_hr_high = predict(inp_hr_high)
res_hr_low  = predict(inp_hr_low)
check("high HR -> longer finish than low HR",
      res_hr_high.estimated_finish >= res_hr_low.estimated_finish,
      f"high={res_hr_high.estimated_finish:.1f}, low={res_hr_low.estimated_finish:.1f}")

# Weather conditions: muddy > dry finish time
inp_w_dry   = PredictionInput(checkpoint_times={2: 223}, trail_condition="dry",   temperature_c=15)
inp_w_muddy = PredictionInput(checkpoint_times={2: 223}, trail_condition="muddy", temperature_c=15)
res_w_dry   = predict(inp_w_dry)
res_w_muddy = predict(inp_w_muddy)
check("in-race: muddy finish > dry finish",
      res_w_muddy.estimated_finish > res_w_dry.estimated_finish,
      f"muddy={res_w_muddy.estimated_finish:.1f}, dry={res_w_dry.estimated_finish:.1f}")


# ===========================================================================
# 6. predict(): grid stress test — no crashes, sensible outputs
# ===========================================================================
print("\n=== 6. Grid stress test ===")

outliers = []
impossible = []
total_grid = 0

for sw in range(73, 176, 7):
    for cb in range(139, 340, 7):
        if cb <= sw:
            continue
        total_grid += 1
        inp = PredictionInput(checkpoint_times={1: sw, 2: cb})
        try:
            res = predict(inp)
            fin = res.estimated_finish
            if fin is None:
                impossible.append((sw, cb, "None finish"))
            elif fin < cb:
                impossible.append((sw, cb, f"finish {fin:.1f} < cb {cb}"))
            elif fin > 870:
                outliers.append((sw, cb, f"finish {fin:.1f} > race cutoff 870"))
            elif fin < 300:
                outliers.append((sw, cb, f"finish {fin:.1f} < 300"))
            if res.fade_rate is not None and res.fade_rate < 0:
                impossible.append((sw, cb, f"negative fade {res.fade_rate:.3f}"))
        except Exception as ex:
            impossible.append((sw, cb, f"EXCEPTION: {ex}"))

check(f"grid ({total_grid} pairs): no impossible outputs (finish < cp, None, exceptions)",
      len(impossible) == 0,
      f"{len(impossible)} impossible: {impossible[:5]}")
check(f"grid ({total_grid} pairs): no wildly out-of-range finishes",
      len(outliers) == 0,
      f"{len(outliers)} outliers: {outliers[:5]}")

# Check finish consistency: adding more checkpoints should only narrow the uncertainty
# (finish from 3 cps should be closer to actual than from 1 cp for a reference athlete)
# Use Karl Reith's actual splits [0, 138, 287, 471, 585, 796]
reith_actual = 796
res_reith_1 = predict(PredictionInput(checkpoint_times={1: 138}))
res_reith_2 = predict(PredictionInput(checkpoint_times={1: 138, 2: 287}))
res_reith_3 = predict(PredictionInput(checkpoint_times={1: 138, 2: 287, 3: 471}))
err_1 = abs(res_reith_1.estimated_finish - reith_actual)
err_2 = abs(res_reith_2.estimated_finish - reith_actual)
err_3 = abs(res_reith_3.estimated_finish - reith_actual)
check("Karl Reith: more CPs = more accurate (err1 >= err3)",
      err_1 >= err_3,
      f"err1={err_1:.1f}, err2={err_2:.1f}, err3={err_3:.1f}")


# ===========================================================================
# 7. Pre-race predict: various marathon times and experience levels
# ===========================================================================
print("\n=== 7. Pre-race predict: marathon time / experience grid ===")

for marathon in [180, 210, 240, 270, 300, 360]:
    for exp in ["novice", "intermediate", "experienced"]:
        inp = PredictionInput(marathon_minutes=marathon, trail_experience=exp)
        res = _pre_race_predict(inp)
        fin = res.estimated_finish
        check(f"pre-race marathon={marathon} {exp}: finish in [300,1000]",
              fin is not None and 300 <= fin <= 1000,
              f"finish={fin}")
        if fin is not None:
            check(f"pre-race marathon={marathon} {exp}: lo <= fin <= hi",
                  res.finish_range_lo <= fin <= res.finish_range_hi,
                  f"lo={res.finish_range_lo:.1f}, fin={fin:.1f}, hi={res.finish_range_hi:.1f}")

# Novice should always predict slower than experienced for same marathon time
for marathon in [210, 240, 270]:
    r_nov = _pre_race_predict(PredictionInput(marathon_minutes=marathon, trail_experience="novice"))
    r_exp = _pre_race_predict(PredictionInput(marathon_minutes=marathon, trail_experience="experienced"))
    check(f"novice slower than experienced (marathon={marathon})",
          r_nov.estimated_finish > r_exp.estimated_finish,
          f"novice={r_nov.estimated_finish:.1f}, exp={r_exp.estimated_finish:.1f}")

# Slower marathon → longer GCU finish
r_fast = _pre_race_predict(PredictionInput(marathon_minutes=200, trail_experience="intermediate"))
r_slow = _pre_race_predict(PredictionInput(marathon_minutes=300, trail_experience="intermediate"))
check("slower marathon -> longer predicted finish",
      r_slow.estimated_finish > r_fast.estimated_finish,
      f"fast={r_fast.estimated_finish:.1f}, slow={r_slow.estimated_finish:.1f}")


# ===========================================================================
# 8. _cardiac_drift: time-based trend
# ===========================================================================
print("\n=== 8. _cardiac_drift ===")

# Strong drift over 2 hours: 10 bpm/hr -> should return 0.3
entries_drift_strong = [
    {"cp": 1, "min": 120, "hr": 150},
    {"cp": 2, "min": 240, "hr": 170},  # +20 bpm over 2 hrs = 10 bpm/hr
]
d = _cardiac_drift(entries_drift_strong, max_hr=185)
check("strong cardiac drift (10 bpm/hr) returns 0.3", d == 0.3, f"got {d}")

# Moderate drift: ~3 bpm/hr -> 0.15
entries_drift_mod = [
    {"cp": 1, "min": 120, "hr": 150},
    {"cp": 2, "min": 240, "hr": 156},  # +6 bpm over 2 hrs = 3 bpm/hr
]
d = _cardiac_drift(entries_drift_mod, max_hr=185)
check("moderate cardiac drift (3 bpm/hr) returns 0.15", d == 0.15, f"got {d}")

# No drift: 0 bpm/hr -> 0
entries_no_drift = [
    {"cp": 1, "min": 120, "hr": 150},
    {"cp": 2, "min": 240, "hr": 150},
]
d = _cardiac_drift(entries_no_drift, max_hr=185)
check("no cardiac drift returns 0", d == 0, f"got {d}")

# Missing HR data -> 0
entries_no_hr = [{"cp": 1, "min": 120}, {"cp": 2, "min": 240}]
d = _cardiac_drift(entries_no_hr, max_hr=185)
check("no HR data returns 0", d == 0, f"got {d}")

# One checkpoint → 0
entries_one = [{"cp": 1, "min": 120, "hr": 160}]
d = _cardiac_drift(entries_one, max_hr=185)
check("one checkpoint returns 0", d == 0, f"got {d}")

# Old bug: same HR change over 30 min vs 120 min should yield different trends
e_short = [{"cp": 1, "min": 90, "hr": 150}, {"cp": 2, "min": 120, "hr": 160}]   # +10 over 0.5hr = 20/hr
e_long  = [{"cp": 1, "min": 90, "hr": 150}, {"cp": 2, "min": 210, "hr": 160}]   # +10 over 2hr = 5/hr
d_short = _cardiac_drift(e_short, max_hr=185)
d_long  = _cardiac_drift(e_long,  max_hr=185)
check("same HR delta: short interval -> stronger drift than long interval",
      d_short >= d_long,
      f"short={d_short}, long={d_long}")


# ===========================================================================
# 9. Terrain bias: climb vs descent detection
# ===========================================================================
print("\n=== 9. _terrain_bias ===")

# Only climb checkpoints → no result
bias = _terrain_bias([{"cp": 1, "min": 100}, {"cp": 3, "min": 300}])
check("only climb CPs -> bias is None", bias is None)

# Only descent checkpoints → no result
bias = _terrain_bias([{"cp": 2, "min": 200}, {"cp": 4, "min": 420}])
check("only descent CPs -> bias is None", bias is None)

# Mixed → result with climb and descent finish
bias = _terrain_bias([{"cp": 1, "min": 111}, {"cp": 2, "min": 213}])
check("mixed climb/descent CPs -> bias is dict", isinstance(bias, dict))
if isinstance(bias, dict):
    check("bias has climb_finish and descent_finish keys",
          "climb_finish" in bias and "descent_finish" in bias)


# ===========================================================================
# 10. Validation against known athletes
# ===========================================================================
print("\n=== 10. Validation against known 2025 athletes ===")

known = [
    ("Admire",  [0, 73,  139, 212, 266, 362]),
    ("Olivia",  [0, 85,  164, 248, 311, 429]),
    ("Dylan",   [0, 92,  179, 280, 357, 490]),
    ("Chris",   [0, 105, 196, 301, 379, 524]),
    ("Kelly",   [0, 123, 223, 332, 419, 577]),
    ("Karl",    [0, 138, 287, 471, 585, 796]),
]

for name, splits in known:
    # Predict from Swiman only
    res_sw = predict(PredictionInput(checkpoint_times={1: splits[1]}))
    # Predict from Swiman + Castleburn
    res_cb = predict(PredictionInput(checkpoint_times={1: splits[1], 2: splits[2]}))
    # Predict from Swiman + Castleburn + Mzimkulwana
    res_mz = predict(PredictionInput(checkpoint_times={1: splits[1], 2: splits[2], 3: splits[3]}))

    actual = splits[-1]
    err_sw = res_sw.estimated_finish - actual
    err_cb = res_cb.estimated_finish - actual
    err_mz = res_mz.estimated_finish - actual

    print(f"  {name:<8} actual={format_elapsed(actual)}"
          f"  sw-only err={err_sw:+.0f}m"
          f"  +cb err={err_cb:+.0f}m"
          f"  +mz err={err_mz:+.0f}m")

    # With all 3 CPs, prediction should be within ±20 min for athletes in the profile set
    check(f"{name}: 3-cp prediction within ±20 min of actual",
          abs(err_mz) <= 20,
          f"err={err_mz:+.0f}m, predicted={res_mz.estimated_finish:.0f}, actual={actual}")


# ===========================================================================
# Summary
# ===========================================================================
print(f"\n{'='*60}")
print(f"Results: {PASS} passed, {FAIL} failed, {WARN} warnings")
print(f"{'='*60}")

if FAIL:
    sys.exit(1)
