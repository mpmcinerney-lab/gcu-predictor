"""
GCU 62km GPX Analysis Script
Parses trackpoints, computes distances, and analyzes terrain between checkpoints.
"""
import xml.etree.ElementTree as ET
import math

# ── GPX Parsing ──────────────────────────────────────────────────────────────
GPX_FILE = r"C:\Users\MMcInerney\Downloads\GCU62.V2.Dec03.gpx"
NS = {"gpx": "http://www.topografix.com/GPX/1/1"}

tree = ET.parse(GPX_FILE)
root = tree.getroot()
trkpts = root.findall(".//gpx:trkpt", NS)

lats, lons, eles = [], [], []
for pt in trkpts:
    lats.append(float(pt.attrib["lat"]))
    lons.append(float(pt.attrib["lon"]))
    eles.append(float(pt.find("gpx:ele", NS).text))

N = len(lats)
print(f"Parsed {N} trackpoints")
print(f"Elevation range in file: {min(eles):.1f} m  to  {max(eles):.1f} m")
print()

# ── Haversine ────────────────────────────────────────────────────────────────
R_EARTH = 6371000  # metres

def haversine(lat1, lon1, lat2, lon2):
    """Return distance in metres between two WGS-84 points."""
    la1, lo1, la2, lo2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlat = la2 - la1
    dlon = lo2 - lo1
    a = math.sin(dlat / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlon / 2) ** 2
    return 2 * R_EARTH * math.asin(math.sqrt(a))

# ── Cumulative distance ─────────────────────────────────────────────────────
cum_dist = [0.0]  # metres
for i in range(1, N):
    d = haversine(lats[i - 1], lons[i - 1], lats[i], lons[i])
    cum_dist.append(cum_dist[-1] + d)

total_dist_km = cum_dist[-1] / 1000
print(f"Total GPX distance: {total_dist_km:.2f} km")
print()

# ── Checkpoint matching ──────────────────────────────────────────────────────
checkpoints = [
    ("START: Silverstreams",    0.0),
    ("AID: Swiman",            14.3),
    ("AID: Castleburn",        28.2),
    ("AID: Mzimkulwana Hut",   39.6),
    ("AID: Cobham",            48.2),
    ("FINISH: Sani",           61.4),
]

# For each checkpoint distance, find the closest trackpoint index
cp_indices = []
for name, km in checkpoints:
    target_m = km * 1000
    best_idx = 0
    best_diff = abs(cum_dist[0] - target_m)
    for i in range(1, N):
        diff = abs(cum_dist[i] - target_m)
        if diff < best_diff:
            best_diff = diff
            best_idx = i
    cp_indices.append(best_idx)

print("Checkpoint index mapping:")
print(f"{'Checkpoint':<28} {'Target km':>10} {'GPX km':>10} {'Idx':>6} {'Elev (m)':>10}")
print("-" * 70)
for (name, km), idx in zip(checkpoints, cp_indices):
    print(f"{name:<28} {km:>10.1f} {cum_dist[idx]/1000:>10.2f} {idx:>6} {eles[idx]:>10.1f}")
print()

# ── Segment analysis ─────────────────────────────────────────────────────────
def analyze_segment(start_idx, end_idx, cum_dist, eles):
    """Compute stats for a segment between two trackpoint indices."""
    seg_dist = cum_dist[end_idx] - cum_dist[start_idx]
    total_ascent = 0.0
    total_descent = 0.0
    ascent_dist = 0.0  # horizontal distance of uphill sections
    descent_dist = 0.0  # horizontal distance of downhill sections
    min_ele = eles[start_idx]
    max_ele = eles[start_idx]

    for i in range(start_idx + 1, end_idx + 1):
        de = eles[i] - eles[i - 1]
        dd = cum_dist[i] - cum_dist[i - 1]
        if de > 0:
            total_ascent += de
            ascent_dist += dd
        elif de < 0:
            total_descent += abs(de)
            descent_dist += dd
        min_ele = min(min_ele, eles[i])
        max_ele = max(max_ele, eles[i])

    avg_up_grad = (total_ascent / ascent_dist * 100) if ascent_dist > 0 else 0
    avg_down_grad = (total_descent / descent_dist * 100) if descent_dist > 0 else 0

    # Steepest 500m window (by gradient magnitude)
    steepest_500_grad = 0.0
    steepest_500_start_km = 0.0
    steepest_500_ele_change = 0.0
    window = 500  # metres
    # We scan all windows within the segment
    j = start_idx
    for i in range(start_idx, end_idx + 1):
        # advance j until the window distance >= 500m
        while j < end_idx and (cum_dist[j] - cum_dist[i]) < window:
            j += 1
        if j <= end_idx:
            window_dist = cum_dist[j] - cum_dist[i]
            if window_dist >= window * 0.9:  # allow some tolerance
                ele_change = eles[j] - eles[i]
                grad = ele_change / window_dist * 100
                if abs(grad) > abs(steepest_500_grad):
                    steepest_500_grad = grad
                    steepest_500_start_km = cum_dist[i] / 1000
                    steepest_500_ele_change = ele_change

    return {
        "dist_km": seg_dist / 1000,
        "ascent": total_ascent,
        "descent": total_descent,
        "min_ele": min_ele,
        "max_ele": max_ele,
        "start_ele": eles[start_idx],
        "end_ele": eles[end_idx],
        "avg_up_grad": avg_up_grad,
        "avg_down_grad": avg_down_grad,
        "steepest_500_grad": steepest_500_grad,
        "steepest_500_start_km": steepest_500_start_km,
        "steepest_500_ele_change": steepest_500_ele_change,
    }

# ── Print segment table ─────────────────────────────────────────────────────
seg_names = []
for i in range(len(checkpoints) - 1):
    seg_names.append(f"{checkpoints[i][0].split(': ')[1]} -> {checkpoints[i+1][0].split(': ')[1]}")

print("=" * 120)
print("SEGMENT ANALYSIS")
print("=" * 120)
header = (
    f"{'Segment':<30} {'Dist km':>8} {'D+ (m)':>8} {'D- (m)':>8} "
    f"{'Min m':>7} {'Max m':>7} {'Start m':>8} {'End m':>7} "
    f"{'AvgUp%':>7} {'AvgDn%':>7} {'Steep500':>9}"
)
print(header)
print("-" * 120)

all_segs = []
cum_ascent = 0.0
cum_descent = 0.0
for i in range(len(checkpoints) - 1):
    s = analyze_segment(cp_indices[i], cp_indices[i + 1], cum_dist, eles)
    all_segs.append(s)
    cum_ascent += s["ascent"]
    cum_descent += s["descent"]
    row = (
        f"{seg_names[i]:<30} {s['dist_km']:>8.2f} {s['ascent']:>8.0f} {s['descent']:>8.0f} "
        f"{s['min_ele']:>7.0f} {s['max_ele']:>7.0f} {s['start_ele']:>8.0f} {s['end_ele']:>7.0f} "
        f"{s['avg_up_grad']:>7.1f} {s['avg_down_grad']:>7.1f} {s['steepest_500_grad']:>+8.1f}%"
    )
    print(row)

print("-" * 120)
full = analyze_segment(cp_indices[0], cp_indices[-1], cum_dist, eles)
print(
    f"{'TOTAL':<30} {full['dist_km']:>8.2f} {cum_ascent:>8.0f} {cum_descent:>8.0f} "
    f"{full['min_ele']:>7.0f} {full['max_ele']:>7.0f} {full['start_ele']:>8.0f} {full['end_ele']:>7.0f} "
    f"{full['avg_up_grad']:>7.1f} {full['avg_down_grad']:>7.1f} {full['steepest_500_grad']:>+8.1f}%"
)
print()

# ── Compare GPX ascent with race PDF ascent ──────────────────────────────────
pdf_ascents = [596, 326, 489, 309, 351]  # per-segment D+ from PDF
print("GPX vs PDF Ascent Comparison:")
print(f"{'Segment':<30} {'GPX D+':>8} {'PDF D+':>8} {'Diff':>8} {'Diff%':>8}")
print("-" * 65)
for i, name in enumerate(seg_names):
    gpx_a = all_segs[i]["ascent"]
    pdf_a = pdf_ascents[i]
    diff = gpx_a - pdf_a
    pct = diff / pdf_a * 100 if pdf_a else 0
    print(f"{name:<30} {gpx_a:>8.0f} {pdf_a:>8} {diff:>+8.0f} {pct:>+7.1f}%")
print(f"{'TOTAL':<30} {cum_ascent:>8.0f} {sum(pdf_ascents):>8} {cum_ascent - sum(pdf_ascents):>+8.0f} {(cum_ascent - sum(pdf_ascents))/sum(pdf_ascents)*100:>+7.1f}%")
print()

# ── Elevation profile summary at checkpoints ────────────────────────────────
print("Elevation at each checkpoint:")
cum_a = 0.0
cum_d = 0.0
for i, ((name, km), idx) in enumerate(zip(checkpoints, cp_indices)):
    if i > 0:
        cum_a += all_segs[i-1]["ascent"]
        cum_d += all_segs[i-1]["descent"]
    print(f"  {name:<28}  km={cum_dist[idx]/1000:>6.2f}  elev={eles[idx]:>7.1f}m  cumD+={cum_a:>6.0f}m  cumD-={cum_d:>6.0f}m")
print()

# ── Net elevation change sanity check ────────────────────────────────────────
net = eles[cp_indices[-1]] - eles[cp_indices[0]]
print(f"Net elevation change (finish - start): {net:>+.1f} m")
print(f"Check: cumD+ - cumD- = {cum_ascent - cum_descent:>+.1f} m  (should equal net)")
