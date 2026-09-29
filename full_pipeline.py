# ============================================================
# GA Unstable Approach Warning: full pipeline in one run
# Author: Sam Suseelan. Code written with AI coding assistance.
#
# What this script does:
#   1. Downloads six hours of OpenSky ADS-B data near KDAB
#   2. Adds aircraft type from the OpenSky aircraft database
#   3. Removes frozen reports and cuts each track into approaches
#   4. Drops fragments and non-training aircraft
#   5. Flags approaches with Rule B (back-to-back sink over 1,000 fpm above 100 ft)
#   6. Prints a summary per aircraft
#   7. Charts each flagged approach next to a clean one from the same aircraft
#   8. Builds the blind labeling sheet and the private key
#   9. Scores Rule B against instructor labels, once labels.csv exists
# ============================================================

import os
import pandas as pd
import matplotlib.pyplot as plt

# ---------- Settings ----------
DATE = "2022-06-27"
HOURS = ["13", "14", "15", "16", "17", "18"]
LAT_MIN, LAT_MAX = 29.10, 29.26          # box around KDAB
LON_MIN, LON_MAX = -81.15, -80.97
MIN_START_FT = 500                        # drop fragments starting lower
MIN_POINTS = 5                            # drop approaches with fewer reports
SINK_LIMIT = 1000                         # fpm, stabilized approach criteria
TRAINERS = "172|PA-28|DA 40|DA 42|182|152"
COLS = ["time", "icao24", "lat", "lon", "velocity", "heading",
        "vertrate", "callsign", "onground", "baroaltitude", "geoaltitude"]


# ---------- Step 1: download and keep rows near KDAB ----------
def load_hours():
    frames = []
    for h in HOURS:
        name = f"states_{DATE}-{h}.csv"
        url = f"https://s3.opensky-network.org/data-samples/states/{DATE}/{h}/{name}.tar"
        os.system(f"wget -q {url} && tar -xf {name}.tar")
        if not os.path.exists(name + ".gz"):
            print("Hour", h, "MISSING, skipped")
            continue
        for chunk in pd.read_csv(name + ".gz", usecols=COLS, chunksize=1_000_000):
            near = chunk[chunk["lat"].between(LAT_MIN, LAT_MAX) &
                         chunk["lon"].between(LON_MIN, LON_MAX)]
            frames.append(near)
        os.system(f"rm -f {name}.tar {name}.gz")
        print("Hour", h, "done")
    day = pd.concat(frames).copy()
    day["alt_ft"] = day["baroaltitude"] * 3.281
    day["speed_kt"] = day["velocity"] * 1.944
    day["vs_fpm"] = day["vertrate"] * 196.85
    return day


# ---------- Step 2: aircraft type database ----------
def load_aircraft():
    name = "aircraft-database-complete-2022-06.csv"
    if not os.path.exists(name):
        os.system(f"wget -q https://s3.opensky-network.org/data-samples/metadata/{name}")
    db = pd.read_csv(name, header=None, skiprows=1, dtype=str,
                     on_bad_lines="skip", encoding="latin-1")
    aircraft = db[[0, 4]].copy()
    aircraft.columns = ["icao24", "model"]
    return aircraft.drop_duplicates("icao24")


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


def profile(values):
    """Turn numbers into short text, for example: 1280, 1088, 1152"""
    return ", ".join(str(int(round(v))) for v in values)


# ---------- Step 4 and 5: one row per approach, with Rule B ----------
def build_approaches(day, aircraft):
    low = day[(day["alt_ft"] < 1500) & (day["speed_kt"] < 140) & (day["onground"] == False)]
    rows, tracks = [], {}
    for plane_id in low["icao24"].unique():
        d = clean_and_cut(day[day["icao24"] == plane_id])
        for aid, a in d.groupby("approach_id"):
            high = (a["vs_fpm"] < -SINK_LIMIT) & (a["alt_ft"] > 100)
            b2b = (high & high.shift(fill_value=False) & (a["time"].diff() <= 15)).sum()
            key = f"{plane_id}_{aid}"
            tracks[key] = a
            rows.append({
                "track_key": key,
                "icao24": plane_id,
                "start_utc": pd.to_datetime(a["time"].min(), unit="s"),
                "points": len(a),
                "start_ft": a["alt_ft"].iloc[0],
                "duration_s": int(a["time"].max() - a["time"].min()),
                "max_sink_fpm": -a["vs_fpm"].min(),
                "altitude_ft": profile(a["alt_ft"]),
                "ground_speed_kt": profile(a["speed_kt"]),
                "sink_rate_fpm": profile(-a["vs_fpm"]),
                "rule_b_flag": b2b >= 1,
            })
    appr = pd.DataFrame(rows).merge(aircraft, on="icao24", how="left")
    return appr, tracks


# ---------- Step 7: chart a flagged approach next to a clean one ----------
def chart_pair(flag_row, clean_row, tracks, filename):
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
    fig.suptitle(f"Same {flag_row['model']}, same day: flagged vs clean approach (KDAB, {DATE})")
    plt.tight_layout()
    plt.savefig(filename, dpi=150)
    plt.show()


# ---------- Step 9: score Rule B against instructor labels ----------
def score_labels(key, labels_file="labels.csv"):
    """labels.csv: the Google Sheet downloaded as CSV, with approach_code, label, reviewer."""
    if not os.path.exists(labels_file):
        print("No labels.csv yet. Upload the labeled sheet as labels.csv and run again.")
        return
    labels = pd.read_csv(labels_file)
    labels["label"] = labels["label"].astype(str).str.strip().str.lower()
    labels = labels[labels["label"].isin(["stable", "unstable", "unsure"])]
    merged = labels.merge(key[["approach_code", "rule_b_flag"]], on="approach_code")

    print("\n===== Rule B vs instructor labels =====")
    for reviewer, r in merged.groupby("reviewer"):
        sure = r[r["label"] != "unsure"]
        unstable = sure["label"] == "unstable"
        flag = sure["rule_b_flag"]
        print(f"\nReviewer {reviewer}: {len(r)} labeled, {(r['label'] == 'unsure').sum()} unsure")
        print("  Unstable per instructor:", unstable.sum())
        print("  Caught by Rule B:       ", (unstable & flag).sum())
        print("  Missed by Rule B:       ", (unstable & ~flag).sum())
        print("  False alarms:           ", (~unstable & flag).sum())
        if len(sure) > 0:
            print("  Rule B agrees with reviewer:", f"{(unstable == flag).mean():.0%}")

    reviewers = merged["reviewer"].dropna().unique()
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
print("Rule B flags:                ", clean["rule_b_flag"].sum())

# ---------- Step 6: summary per aircraft ----------
per_aircraft = clean.groupby(["icao24", "model"]).agg(
    approaches=("track_key", "count"),
    rule_b_flags=("rule_b_flag", "sum"),
    worst_sink_fpm=("max_sink_fpm", "max"),
).round(0).sort_values(["rule_b_flags", "approaches"], ascending=False)
print("\n===== Top 10 aircraft =====")
print(per_aircraft.head(10))

# ---------- Step 7: charts for each flagged approach ----------
for i, (_, f) in enumerate(clean[clean["rule_b_flag"]].iterrows(), start=1):
    same_plane = clean[(clean["icao24"] == f["icao24"]) & ~clean["rule_b_flag"]]
    if len(same_plane) == 0:
        print("No clean approach to compare for", f["icao24"])
        continue
    best = same_plane.sort_values(["max_sink_fpm", "points"], ascending=[True, False]).iloc[0]
    chart_pair(f, best, tracks, f"flagged_vs_clean_{i}.png")

# ---------- Step 8: blind labeling sheet and private key ----------
key = clean.sample(frac=1, random_state=42).reset_index(drop=True)
key["approach_code"] = ["A" + str(i + 1).zfill(3) for i in range(len(key))]

sheet = key[["approach_code", "model", "duration_s",
             "altitude_ft", "ground_speed_kt", "sink_rate_fpm"]].copy()
sheet["label"] = ""
sheet["reason"] = ""
sheet["reviewer"] = ""
sheet.to_csv("labeling_sheet_v2.csv", index=False)
key.drop(columns=["track_key"]).to_csv("labeling_key_v2.csv", index=False)
print("\nSaved labeling_sheet_v2.csv and labeling_key_v2.csv")

# ---------- Step 9: score against labels, if present ----------
score_labels(key)

# ---------- Download files to your laptop ----------
try:
    from google.colab import files
    files.download("labeling_sheet_v2.csv")
    files.download("labeling_key_v2.csv")
    for name in sorted(os.listdir(".")):
        if name.startswith("flagged_vs_clean_"):
            files.download(name)
except ImportError:
    pass
