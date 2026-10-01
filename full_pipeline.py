# ============================================================
# GA Unstable Approach Warning: full pipeline in one run (v3)
# Author: Sam Suseelan. Code written with AI coding assistance.
#
# What this script does:
#   1. Loads hours of OpenSky ADS-B data near KDAB from Google Drive
#   2. Adds aircraft type from the OpenSky aircraft database
#   3. Removes frozen reports and cuts each track into approaches
#   4. Ends each approach at touchdown (for charts and durations)
#   5. Drops fragments and non-training aircraft
#   6. Flags approaches with two rules:
#        Rule B: back-to-back sink over 1,000 fpm, above 100 ft
#        Rule S: back-to-back ground speed over the type limit, 100 to 500 ft
#   7. Prints a summary per aircraft
#   8. Charts each flagged approach next to a clean one from the same aircraft
#   9. Keeps the approach codes from the sheet already sent (labeling_key_v2.csv)
#      and builds a new sheet only for approaches not in that key
#  10. Scores Rule B, Rule S and both together against instructor labels
# ============================================================

import os
import glob
import pandas as pd
import matplotlib.pyplot as plt

# ---------- Settings ----------
# Dates and UTC hours to load. Add a day here after putting its files in Drive.
DAYS = {
    "2022-06-27": ["14", "15", "16"],
}
DRIVE_DIR = "/content/drive/MyDrive/opensky"   # Drive folder with .tar files, key and labels
TRY_OPENSKY = False                             # True = download missing hours from OpenSky
LAT_MIN, LAT_MAX = 29.10, 29.26                 # box around KDAB
LON_MIN, LON_MAX = -81.15, -80.97
MIN_START_FT = 500                              # drop fragments starting lower
MIN_POINTS = 5                                  # drop approaches with fewer reports
SINK_LIMIT = 1000                               # fpm, stabilized approach criteria
SPEED_WINDOW_FT = (100, 500)                    # Rule S checks reports in this altitude band
# Ground speed limits in knots, by aircraft type. Starting values, to calibrate
# against instructor labels. Ground speed includes wind.
SPEED_LIMITS = [
    ("152", 80),
    ("172", 85),
    ("182", 95),
    ("PA-28", 85),
    ("DA 40", 90),
    ("DA 42", 105),
]
TRAINERS = "172|PA-28|DA 40|DA 42|182|152"
COLS = ["time", "icao24", "lat", "lon", "velocity", "heading",
        "vertrate", "callsign", "onground", "baroaltitude", "geoaltitude"]


# ---------- Step 1: load hours and keep rows near KDAB ----------
def get_file(name, url):
    """Use the copy in Google Drive if present, else download from OpenSky if allowed."""
    drive_copy = os.path.join(DRIVE_DIR, name)
    if os.path.exists(drive_copy):
        print("  using Drive copy of", name)
        return drive_copy
    if not TRY_OPENSKY:
        return None
    os.system(f"wget -q --timeout=60 --tries=3 {url}")
    return name if os.path.exists(name) else None


def load_hours():
    frames = []
    for date, hours in DAYS.items():
        for h in hours:
            name = f"states_{date}-{h}.csv"
            url = f"https://s3.opensky-network.org/data-samples/states/{date}/{h}/{name}.tar"
            tar_path = get_file(name + ".tar", url)
            if tar_path is None:
                print(date, "hour", h, "MISSING, skipped")
                continue
            os.system(f"tar -xf '{tar_path}'")
            if not os.path.exists(name + ".gz"):
                print(date, "hour", h, "could not unpack, skipped")
                continue
            for chunk in pd.read_csv(name + ".gz", usecols=COLS, chunksize=1_000_000):
                near = chunk[chunk["lat"].between(LAT_MIN, LAT_MAX) &
                             chunk["lon"].between(LON_MIN, LON_MAX)]
                frames.append(near)
            os.system(f"rm -f {name}.tar {name}.gz")
            print(date, "hour", h, "done")
    if not frames:
        raise SystemExit("No hours loaded. Check the files in " + DRIVE_DIR)
    day = pd.concat(frames).copy()
    day["alt_ft"] = day["baroaltitude"] * 3.281
    day["speed_kt"] = day["velocity"] * 1.944
    day["vs_fpm"] = day["vertrate"] * 196.85
    return day


# ---------- Step 2: aircraft type database ----------
def load_aircraft():
    name = "aircraft-database-complete-2022-06.csv"
    path = get_file(name, f"https://s3.opensky-network.org/data-samples/metadata/{name}")
    if path is None:
        raise SystemExit("Aircraft database missing. Put " + name + " in " + DRIVE_DIR)
    db = pd.read_csv(path, header=None, skiprows=1, dtype=str,
                     on_bad_lines="skip", encoding="latin-1")
    aircraft = db[[0, 4]].copy()
    aircraft.columns = ["icao24", "model"]
    return aircraft.drop_duplicates("icao24")


def speed_limit(model):
    """Ground speed limit for an aircraft type, or None for types without a limit."""
    model = str(model)
    for part, limit in SPEED_LIMITS:
        if part in model:
            return limit
    return None


# ---------- Step 3: clean one track and cut approaches ----------
def clean_and_cut(df):
    """Remove frozen rows, cut the track into approaches, return descending rows only."""
    df = df.sort_values("time")
    frozen = (
        (df["alt_ft"] == df["alt_ft"].shift()) &
        (df["speed_kt"] == df["speed_kt"].shift()) &
        (df["vs_fpm"] == df["vs_fpm"].shift())
    )
    df = df[~frozen].copy()
    df["descending"] = (df["vs_fpm"] < -100) & (df["alt_ft"] < 700)
    starts = df["descending"] & ~df["descending"].shift(fill_value=False)
    df["approach_id"] = starts.cumsum()
    return df[df["descending"]].copy()


def to_touchdown(a):
    """Keep reports up to the first one at or below 0 ft (standard-pressure altitude)."""
    at_ground = (a["alt_ft"] <= 0).to_numpy()
    if at_ground.any():
        return a.iloc[: at_ground.argmax() + 1]
    return a


def back_to_back(condition, a):
    """Count pairs of consecutive reports, 10 seconds apart, where both meet the condition."""
    gap_ok = a["time"].diff() <= 15
    return int((condition & condition.shift(fill_value=False) & gap_ok).sum())


def profile(values):
    """Turn numbers into short text, for example: 1280, 1088, 1152"""
    return ", ".join(str(int(round(v))) for v in values)


# ---------- Step 4 to 6: one row per approach, with Rule B and Rule S ----------
def build_approaches(day, aircraft):
    low = day[(day["alt_ft"] < 1500) & (day["speed_kt"] < 140) & (day["onground"] == False)]
    models = aircraft.set_index("icao24")["model"]
    rows, tracks = [], {}
    for plane_id in low["icao24"].unique():
        model = models.get(plane_id)
        limit = speed_limit(model)
        d = clean_and_cut(day[day["icao24"] == plane_id])
        for aid, a in d.groupby("approach_id"):
            high_sink = (a["vs_fpm"] < -SINK_LIMIT) & (a["alt_ft"] > 100)
            if limit is None:
                fast_pairs = 0
            else:
                in_band = a["alt_ft"].between(*SPEED_WINDOW_FT)
                fast_pairs = back_to_back(in_band & (a["speed_kt"] > limit), a)
            t = to_touchdown(a)
            key = f"{plane_id}_{aid}"
            tracks[key] = t
            rows.append({
                "track_key": key,
                "icao24": plane_id,
                "model": model,
                "start_utc": pd.to_datetime(a["time"].min(), unit="s"),
                "points": len(a),
                "start_ft": a["alt_ft"].iloc[0],
                "duration_s": int(a["time"].max() - a["time"].min()),
                "duration_to_touchdown_s": int(t["time"].max() - t["time"].min()),
                "max_sink_fpm": -a["vs_fpm"].min(),
                "max_speed_500ft_kt": a.loc[a["alt_ft"].between(*SPEED_WINDOW_FT), "speed_kt"].max(),
                "speed_limit_kt": limit,
                "altitude_ft": profile(a["alt_ft"]),
                "ground_speed_kt": profile(a["speed_kt"]),
                "sink_rate_fpm": profile(-a["vs_fpm"]),
                "rule_b_flag": back_to_back(high_sink, a) >= 1,
                "rule_s_flag": fast_pairs >= 1,
            })
    appr = pd.DataFrame(rows)
    appr["any_flag"] = appr["rule_b_flag"] | appr["rule_s_flag"]
    return appr, tracks


# ---------- Step 8: chart a flagged approach next to a clean one ----------
def chart_pair(flag_row, clean_row, tracks, filename, title_rule):
    fig, ax = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    for row, label, color, style in [
        (flag_row, "Flagged approach", "#eb6834", "-"),
        (clean_row, "Clean approach", "#2a78d6", "--"),
    ]:
        a = tracks[row["track_key"]]
        sec = a["time"] - a["time"].min()
        name = label + ", " + row["start_utc"].strftime("%H:%M UTC")
        ax[0].plot(sec, a["alt_ft"], style, color=color, lw=2, marker="o", ms=5, label=name)
        ax[1].plot(sec, a["speed_kt"], style, color=color, lw=2, marker="o", ms=5)
        ax[2].plot(sec, -a["vs_fpm"], style, color=color, lw=2, marker="o", ms=5)
    if flag_row["speed_limit_kt"] == flag_row["speed_limit_kt"]:   # not NaN
        ax[1].axhline(flag_row["speed_limit_kt"], color="gray", lw=1, ls=":")
        ax[1].text(0, flag_row["speed_limit_kt"] + 1,
                   f"{int(flag_row['speed_limit_kt'])} kt limit", color="gray", fontsize=9)
    ax[2].axhline(SINK_LIMIT, color="gray", lw=1, ls=":")
    ax[2].text(0, SINK_LIMIT + 20, "1,000 fpm limit", color="gray", fontsize=9)
    ax[0].set_ylabel("Altitude (ft)")
    ax[1].set_ylabel("Ground speed (kt)")
    ax[2].set_ylabel("Sink rate (fpm)")
    ax[2].set_xlabel("Seconds since approach start")
    ax[0].legend(frameon=False)
    for one in ax:
        one.grid(alpha=0.3)
        one.spines[["top", "right"]].set_visible(False)
    date = flag_row["start_utc"].strftime("%Y-%m-%d")
    fig.suptitle(f"Same {flag_row['model']}, {title_rule}: flagged vs clean approach (KDAB, {date})")
    plt.tight_layout()
    plt.savefig(filename, dpi=150)
    plt.show()


# ---------- Step 9: keep codes from the sheet already sent ----------
def attach_codes(clean):
    """Give each approach its code from labeling_key_v2.csv. New approaches get B codes."""
    key_path = os.path.join(DRIVE_DIR, "labeling_key_v2.csv")
    if not os.path.exists(key_path) and os.path.exists("labeling_key_v2.csv"):
        key_path = "labeling_key_v2.csv"
    clean = clean.copy()
    if os.path.exists(key_path):
        old = pd.read_csv(key_path, usecols=["approach_code", "icao24", "start_utc"])
        old["start_utc"] = pd.to_datetime(old["start_utc"])
        clean = clean.merge(old, on=["icao24", "start_utc"], how="left")
        print(f"\nMatched {clean['approach_code'].notna().sum()} of {len(old)} codes from labeling_key_v2.csv")
    else:
        print("\nNo labeling_key_v2.csv found in Drive. All approaches get new codes.")
        clean["approach_code"] = pd.NA

    new = clean[clean["approach_code"].isna()]
    if len(new) > 0:
        new = new.sample(frac=1, random_state=42)
        codes = ["B" + str(i + 1).zfill(3) for i in range(len(new))]
        clean.loc[new.index, "approach_code"] = codes
        sheet = clean.loc[new.index, ["approach_code", "model", "duration_s",
                                      "altitude_ft", "ground_speed_kt", "sink_rate_fpm"]].copy()
        sheet["label"] = ""
        sheet["reason"] = ""
        sheet["reviewer"] = ""
        sheet.to_csv("labeling_sheet_extra.csv", index=False)
        clean.loc[new.index].drop(columns=["track_key"]).to_csv("labeling_key_extra.csv", index=False)
        print(f"New approaches not in the sent sheet: {len(new)}. "
              "Saved labeling_sheet_extra.csv and labeling_key_extra.csv")
    return clean


# ---------- Step 10: score both rules against instructor labels ----------
def load_labels():
    """Read every labels*.csv from Drive or the Colab folder. One file per instructor is fine."""
    paths = sorted(set(glob.glob(os.path.join(DRIVE_DIR, "labels*.csv")) + glob.glob("labels*.csv")))
    frames = []
    for p in paths:
        df = pd.read_csv(p)
        df["source_file"] = os.path.basename(p)
        if "reviewer" not in df or df["reviewer"].isna().all():
            df["reviewer"] = os.path.basename(p).replace(".csv", "")
        df["reviewer"] = df["reviewer"].ffill()
        frames.append(df)
    if not frames:
        return None
    labels = pd.concat(frames, ignore_index=True)
    labels["label"] = labels["label"].astype(str).str.strip().str.lower()
    return labels[labels["label"].isin(["stable", "unstable", "unsure"])]


def score_labels(coded):
    labels = load_labels()
    if labels is None or len(labels) == 0:
        print("\nNo labels yet. Put labels_<name>.csv files in the Drive opensky folder and run again.")
        return
    merged = labels.merge(coded[["approach_code", "rule_b_flag", "rule_s_flag", "any_flag"]],
                          on="approach_code")
    print("\n===== Rules vs instructor labels =====")
    for reviewer, r in merged.groupby("reviewer"):
        sure = r[r["label"] != "unsure"]
        unstable = sure["label"] == "unstable"
        print(f"\nReviewer {reviewer}: {len(r)} labeled, {(r['label'] == 'unsure').sum()} unsure, "
              f"{unstable.sum()} unstable")
        for rule, name in [("rule_b_flag", "Rule B (sink)"),
                           ("rule_s_flag", "Rule S (speed)"),
                           ("any_flag", "B or S")]:
            flag = sure[rule].astype(bool)
            caught = (unstable & flag).sum()
            missed = (unstable & ~flag).sum()
            false_alarm = (~unstable & flag).sum()
            agree = (unstable == flag).mean() if len(sure) else float("nan")
            print(f"  {name:15} caught {caught:3}  missed {missed:3}  false alarms {false_alarm:3}  "
                  f"agrees {agree:.0%}")

    reviewers = list(merged["reviewer"].dropna().unique())
    if len(reviewers) >= 2:
        a, b = reviewers[0], reviewers[1]
        both = merged[merged["reviewer"] == a].merge(
            merged[merged["reviewer"] == b], on="approach_code", suffixes=("_a", "_b"))
        if len(both) > 0:
            same = (both["label_a"] == both["label_b"]).mean()
            print(f"\nReviewers {a} and {b} agree on {same:.0%} of {len(both)} shared approaches")


# ============================================================
# Run everything
# ============================================================
try:
    from google.colab import drive
    drive.mount("/content/drive")
except ImportError:
    pass

day = load_hours()
aircraft = load_aircraft()
appr, tracks = build_approaches(day, aircraft)

trainers = appr["model"].fillna("").str.contains(TRAINERS)
full = (appr["start_ft"] >= MIN_START_FT) & (appr["points"] >= MIN_POINTS)
clean = appr[trainers & full].copy()

print("\n===== Totals =====")
print("Aircraft near KDAB:          ", day["icao24"].nunique())
print("All approaches (3+ reports): ", (appr["points"] >= 3).sum())
print("Training aircraft approaches:", (trainers & (appr["points"] >= 3)).sum())
print("Fragments removed:           ", (trainers & (appr["points"] >= 3) & ~full).sum())
print("Approaches for review:       ", len(clean))
print("Rule B flags (sink):         ", clean["rule_b_flag"].sum())
print("Rule S flags (speed):        ", clean["rule_s_flag"].sum())
print("Flagged by either rule:      ", clean["any_flag"].sum())

# ---------- Step 7: summary per aircraft ----------
per_aircraft = clean.groupby(["icao24", "model"]).agg(
    approaches=("track_key", "count"),
    rule_b=("rule_b_flag", "sum"),
    rule_s=("rule_s_flag", "sum"),
    worst_sink_fpm=("max_sink_fpm", "max"),
    top_speed_kt=("max_speed_500ft_kt", "max"),
).round(0).sort_values(["rule_b", "rule_s", "approaches"], ascending=False)
print("\n===== Top 10 aircraft =====")
print(per_aircraft.head(10))

# ---------- Step 8: charts for each flagged approach ----------
chart_no = 0
for _, f in clean[clean["any_flag"]].iterrows():
    same_plane = clean[(clean["icao24"] == f["icao24"]) & ~clean["any_flag"]]
    if len(same_plane) == 0:
        print("No clean approach to compare for", f["icao24"], f["start_utc"])
        continue
    best = same_plane.sort_values(["max_sink_fpm", "points"], ascending=[True, False]).iloc[0]
    rules = " and ".join(n for n, c in [("Rule B", f["rule_b_flag"]), ("Rule S", f["rule_s_flag"])] if c)
    chart_no += 1
    chart_pair(f, best, tracks, f"flagged_vs_clean_{chart_no}.png", rules)

# ---------- Step 9: codes for the sheet already sent ----------
coded = attach_codes(clean)
flag_cols = ["approach_code", "icao24", "model", "start_utc", "max_sink_fpm",
             "max_speed_500ft_kt", "speed_limit_kt", "rule_b_flag", "rule_s_flag"]
coded[flag_cols].sort_values("approach_code").to_csv("rule_flags_v3.csv", index=False)
print("Saved rule_flags_v3.csv (private, has aircraft codes)")

# ---------- Step 10: score against labels, if present ----------
score_labels(coded)

# ---------- Download files to your laptop ----------
try:
    from google.colab import files
    for name in sorted(os.listdir(".")):
        if (name.startswith("flagged_vs_clean_") or name == "rule_flags_v3.csv"
                or name.startswith("labeling_sheet_extra") or name.startswith("labeling_key_extra")):
            files.download(name)
except ImportError:
    pass
