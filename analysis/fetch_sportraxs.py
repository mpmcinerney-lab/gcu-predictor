"""
Fetch athlete split data from Sportraxs race page and save expanded PR.

Creates: analysis/expanded_pr.json — list of profiles [Start, Swiman, Castleburn, Mzimkulwana, Cobham, Finish]

Run: python analysis/fetch_sportraxs.py
"""
import urllib.request
import urllib.error
import re
import json
import time

LEADERBOARD_PAGE = 'https://tan.sportraxs.com/events/517/races/1255/leaderboard'
ATHLETE_URL_TEMPLATE = 'https://tan.sportraxs.com/events/517/races/1255/athlete/{id}'

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36'}

CP_LABELS = [
    ('Start', 'Start'),
    ('Swiman', 'Swiman'),
    ('Castleburn', 'Castleburn'),
    ('Mzimkulwana', 'Mzimkulwana'),
    ('Cobham', 'Cobham'),
    ('Finish', 'Finish'),
]

OUT_FILE = 'analysis/expanded_pr.json'


def get_html(url):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode('utf-8', errors='ignore')
    except urllib.error.HTTPError as e:
        print(f"HTTPError {e.code} for {url}")
    except Exception as e:
        print(f"Error fetching {url}: {e}")
    return None


def find_athlete_ids(html):
    ids = re.findall(r'/athlete/(\d+)', html)
    ids = [int(i) for i in ids]
    # preserve order while deduping
    seen = set(); out = []
    for i in ids:
        if i not in seen:
            seen.add(i); out.append(i)
    return out


def find_time_after_label(html, label):
    # find position of label, then search for first HH:MM:SS within 400 chars
    lo = html.lower().find(label.lower())
    if lo == -1:
        return None
    snippet = html[lo: lo + 400]
    m = re.search(r'([0-9]{2}:[0-9]{2}:[0-9]{2})', snippet)
    if m:
        return m.group(1)
    # fallback: search a little further
    snippet = html[lo: lo + 800]
    m = re.search(r'([0-9]{2}:[0-9]{2}:[0-9]{2})', snippet)
    if m:
        return m.group(1)
    return None


def hhmmss_to_minutes(s):
    try:
        parts = s.split(':')
        h = int(parts[0]); m = int(parts[1]); sec = int(parts[2])
        total_seconds = h * 3600 + m * 60 + sec
        return int(round(total_seconds / 60.0))
    except Exception:
        return None


def athlete_has_finished(html):
    # Check for 'FINISHED' in page (case-insensitive)
    return 'finished' in html.lower()


def parse_athlete_profile(html):
    # Many athlete pages are delivered as SPA JS blobs; a robust approach
    # is to extract all HH:MM:SS timestamps and look for the timeline block
    # that starts at 00:00:00 and contains successive checkpoint times.
    all_times = re.findall(r'([0-9]{2}:[0-9]{2}:[0-9]{2})', html)
    if not all_times:
        return None
    # convert to seconds
    secs = []
    for t in all_times:
        try:
            h, m, s = map(int, t.split(':'))
            secs.append(h * 3600 + m * 60 + s)
        except Exception:
            continue

    # look for a block starting at 00:00:00 with increasing times
    for i in range(len(secs) - 5):
        if secs[i] != 0:
            continue
        # require the next 4 checkpoints to be strictly increasing and reasonable
        ok = True
        for j in range(4):
            if not (secs[i + j] < secs[i + j + 1] and 0 < (secs[i + j + 1] - secs[i + j]) < 8 * 3600):
                ok = False
                break
        if not ok:
            continue
        # assume mapping: start, swiman, castleburn, mzim, cobham
        start = secs[i]
        sw = secs[i + 1]
        cb = secs[i + 2]
        mz = secs[i + 3]
        co = secs[i + 4]
        # try to pick finish time from a few entries ahead (sometimes 'Almost Finished' sits between)
        finish_idx = min(i + 7, len(secs) - 1)
        finish = secs[finish_idx]
        return [int(round(start / 60.0)), int(round(sw / 60.0)), int(round(cb / 60.0)), int(round(mz / 60.0)), int(round(co / 60.0)), int(round(finish / 60.0))]
    return None


def main(limit=None):
    print('Fetching leaderboard page...')
    main_html = get_html(LEADERBOARD_PAGE)
    if not main_html:
        print('Failed to fetch leaderboard page')
        return
    athlete_ids = find_athlete_ids(main_html)
    print(f'Found {len(athlete_ids)} athlete links on leaderboard page')
    if limit:
        athlete_ids = athlete_ids[:limit]
    profiles = []
    count = 0
    for aid in athlete_ids:
        url = ATHLETE_URL_TEMPLATE.format(id=aid)
        html = get_html(url)
        if not html:
            continue
        if not athlete_has_finished(html):
            continue
        prof = parse_athlete_profile(html)
        if prof:
            profiles.append(prof)
            count += 1
            print(f'  Parsed athlete {aid}: {prof}')
        else:
            # skip athletes without complete splits
            pass
        time.sleep(0.35)
    print(f'Parsed {count} complete athlete profiles')
    # save
    try:
        with open(OUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(profiles, f, indent=2)
        print(f'Wrote {len(profiles)} profiles to {OUT_FILE}')
    except Exception as e:
        print('Error writing output:', e)

if __name__ == '__main__':
    # limit to first 120 athletes to be polite
    main(limit=120)
