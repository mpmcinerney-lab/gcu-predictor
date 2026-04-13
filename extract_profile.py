import xml.etree.ElementTree as ET
import math

GPX_FILE = r"C:\Users\MMcInerney\Downloads\GCU62.V2.Dec03.gpx"
NUM_SAMPLES = 120

CHECKPOINTS = [
    ("Silverstreams", 0),
    ("Swiman", 14.3),
    ("Castleburn", 28.2),
    ("Mzimkulwana Hut", 39.6),
    ("Cobham", 48.2),
    ("Sani", 61.4),
]

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# Parse GPX
ns = {"gpx": "http://www.topografix.com/GPX/1/1"}
tree = ET.parse(GPX_FILE)
root = tree.getroot()

points = []
for trkpt in root.findall(".//gpx:trkpt", ns):
    lat = float(trkpt.get("lat"))
    lon = float(trkpt.get("lon"))
    ele = float(trkpt.find("gpx:ele", ns).text)
    points.append((lat, lon, ele))

# Compute cumulative distance
cum_dist = [0.0]
for i in range(1, len(points)):
    d = haversine(points[i-1][0], points[i-1][1], points[i][0], points[i][1])
    cum_dist.append(cum_dist[-1] + d)

total_km = cum_dist[-1]

# Sample ~120 evenly spaced points
step = total_km / (NUM_SAMPLES - 1)
sampled = []
j = 0
for i in range(NUM_SAMPLES):
    target = i * step
    while j < len(cum_dist) - 1 and cum_dist[j+1] < target:
        j += 1
    if j >= len(cum_dist) - 1:
        sampled.append((round(cum_dist[-1], 2), round(points[-1][2], 1)))
    else:
        # Linear interpolation
        seg_len = cum_dist[j+1] - cum_dist[j]
        if seg_len == 0:
            frac = 0
        else:
            frac = (target - cum_dist[j]) / seg_len
        ele = points[j][2] + frac * (points[j+1][2] - points[j][2])
        sampled.append((round(target, 2), round(ele, 1)))

# Find checkpoint indices (nearest sample)
cp_out = []
for name, km in CHECKPOINTS:
    best_idx = 0
    best_diff = abs(sampled[0][0] - km)
    for idx, (d, _) in enumerate(sampled):
        diff = abs(d - km)
        if diff < best_diff:
            best_diff = diff
            best_idx = idx
    cp_out.append((name, km, best_idx))

# Output
print("const ELEVATION_PROFILE = [")
for i, (d, e) in enumerate(sampled):
    comma = "," if i < len(sampled) - 1 else ""
    print(f"  [{d}, {e}]{comma}")
print("];")
print()
print("const CHECKPOINT_POSITIONS = [")
for i, (name, km, idx) in enumerate(cp_out):
    comma = "," if i < len(cp_out) - 1 else ""
    print(f"  {{name: '{name}', km: {km}, idx: {idx}}}{comma}")
print("];")

print(f"\n// Total trackpoints: {len(points)}, Total distance: {round(total_km, 2)} km")
