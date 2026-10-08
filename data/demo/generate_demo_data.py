"""
Standalone script that regenerates data/demo/synthetic_reviews.json.
Run once:  python data/demo/generate_demo_data.py

Output: 300 records with varied topics, ratings, authors, and dates.
All records are clearly synthetic — never real user data.
"""
from __future__ import annotations

import json
import os
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

random.seed(42)

# ── Synthetic content pools ───────────────────────────────────────────────────
TOPICS = {
    "battery": [
        ("Battery degradation after 3 years", "I've had my EV for 3 years and the battery health is down to 87%. Is that normal?"),
        ("Battery replacement cost shock", "Got quoted $14,000 for a new battery pack. Anyone negotiate this down?"),
        ("Battery warranty question", "Does the 8-year battery warranty cover capacity loss below 70%?"),
        ("Battery health tracking", "Using a third-party app to track battery health — down 4% after 18 months."),
        ("Cold weather battery degradation", "Battery lost 12% range overnight when temps dropped to -10°C."),
        ("Battery failure at 50k miles", "Pack died completely at 52,000 miles. Dealer says it's out of warranty by 200 miles."),
        ("Battery health after fast charging", "Been using DC fast charging daily. Noticed faster degradation vs Level 2."),
        ("Extended battery warranty worth it?", "Debating whether to buy the extended battery warranty. 3 years in with 91% health."),
    ],
    "range": [
        ("Real world range vs advertised", "EPA says 300 miles. I get 240 on the highway. Anyone else?"),
        ("Range anxiety on road trips", "Had to detour 45 miles because the next charger was out of service. Stressful."),
        ("Winter range loss is brutal", "Range drops from 280 to 180 miles in winter. This needs to be disclosed better."),
        ("Highway range much lower than city", "City driving I get full rated range. Highway at 75mph I lose 30%."),
        ("Range after 2 years", "Still getting 97% of original rated range after 2 years and 30k miles."),
        ("Range loss in heat", "Noticed range drops about 8% when it's very hot outside too, not just cold."),
        ("Trip planning with real range", "Had to rethink entire road trip because real range doesn't match the app."),
        ("Range improvement tips", "Driving at 60mph instead of 75mph gives me an extra 40 miles. Worth it?"),
    ],
    "charging": [
        ("DC fast charging speed dropped", "Used to charge at 150kW. Now maxes at 90kW. Battery management issue?"),
        ("Charging station reliability", "3 out of 5 chargers at the mall were broken. This is a real problem."),
        ("Home charging setup cost", "Paid $1,800 for Level 2 home charger installation. Worth every penny."),
        ("Charging speed at different SOC levels", "Charging slows dramatically above 80%. Is 80% the right daily limit?"),
        ("Public charging etiquette", "People leave cars plugged in hours after charging completes. Frustrating."),
        ("Charging problem in cold weather", "Charger won't initiate below -5°C without preconditioning. Annoying."),
        ("Fast charging vs battery health tradeoff", "Limiting to 2 DC fast charges per week to protect battery. Is this necessary?"),
        ("Charging infrastructure improving", "5 new fast chargers opened within 10 miles of me this year. Progress!"),
        ("Charging reliability at highway stops", "Stopped at 4 locations on I-95. One broken, one occupied, two worked fine."),
    ],
    "thermal": [
        ("Battery overheating warning in summer", "Got a thermal warning driving in 40°C weather. Had to slow down."),
        ("Thermal management is key", "The reason some EVs degrade faster is poor thermal management. Period."),
        ("Winter battery performance", "Battery performance in -20°C is terrible. Takes 45 min to warm up."),
        ("Battery cooling system noise", "Cooling fans run loud when fast charging in hot weather. Normal?"),
        ("Thermal runaway concern", "Read about a battery fire. Now worried about leaving car in hot garage."),
        ("Active thermal management vs passive", "Cars with active liquid cooling hold range much better in extremes."),
        ("Preconditioning helps thermal performance", "Using scheduled preconditioning before drives made a huge difference."),
    ],
    "reliability": [
        ("Overall EV reliability after 2 years", "Zero major issues in 2 years. Only maintenance: tires and wipers."),
        ("Software update broke charging", "After OTA update, home charging stopped working for 3 days. Scary."),
        ("EV reliability vs ICE comparison", "Had 3 ICE cars before this. EV has been far more reliable so far."),
        ("Unexpected repair costs", "Door handle motor failed at 18 months. $800 repair not covered under warranty."),
        ("Battery fire news coverage overblown", "Media makes EV fires seem common. ICE fires happen 80x more often per mile."),
    ],
    "ownership": [
        ("EV ownership after 1 year", "One year in: love the car, hate the charging infrastructure in my area."),
        ("EV ownership after 3 years", "3 years, 45k miles. Battery at 92%. Total maintenance cost under $400."),
        ("Long term EV ownership review", "5 years with my EV. Would never go back to gas. Cost savings are real."),
        ("EV maintenance costs are low", "Oil changes, transmission fluid, exhaust repairs — all $0. Saving a lot."),
        ("EV after 1 year: honest review", "Pros: cheap to run, smooth drive. Cons: range anxiety, charging wait times."),
        ("Hidden costs of EV ownership", "Insurance is higher, tires wear faster, and home charger install was pricey."),
        ("EV owner experience summary", "Best vehicle I've owned. The instant torque never gets old after 2 years."),
    ],
}

RATINGS = [1.0, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
RATING_WEIGHTS = [0.05, 0.07, 0.08, 0.12, 0.15, 0.22, 0.18, 0.13]
LANGUAGES = ["en"] * 18 + ["de", "fr", "es", "nl", "it", "sv", "no", "da"]
PLATFORMS = ["reddit_demo", "youtube_demo", "forum_demo", "survey_demo"]

BASE_DATE = datetime(2023, 1, 1, tzinfo=timezone.utc)
END_DATE = datetime(2024, 12, 31, tzinfo=timezone.utc)


def random_date() -> datetime:
    delta = END_DATE - BASE_DATE
    return BASE_DATE + timedelta(seconds=random.randint(0, int(delta.total_seconds())))


def make_record(idx: int, topic_key: str, title: str, text: str) -> dict:
    platform = random.choice(PLATFORMS)
    pub_date = random_date()
    return {
        "id": f"demo_{idx:04d}",
        "title": title,
        "text": text,
        "source_url": f"https://example-demo.invalid/{platform}/{idx}",
        "published_at": pub_date.isoformat(),
        "author_id": f"synthetic_user_{random.randint(1, 150):04d}",
        "rating": random.choices(RATINGS, weights=RATING_WEIGHTS, k=1)[0],
        "language": random.choice(LANGUAGES),
        "metadata": {
            "synthetic": True,
            "topic": topic_key,
            "platform": platform,
            "upvotes": random.randint(0, 500),
            "comment_count": random.randint(0, 80),
        },
    }


def generate(n: int = 300) -> list[dict]:
    records = []
    idx = 1
    all_items = [(k, t, tx) for k, pairs in TOPICS.items() for t, tx in pairs]

    # Ensure we cycle through all topics evenly
    while len(records) < n:
        item = all_items[(idx - 1) % len(all_items)]
        topic_key, title, text = item
        # Add slight variation to avoid identical duplicates
        variation = random.choice(["", " (update)", " - follow up", " revisited", " month 6"])
        records.append(make_record(idx, topic_key, title + variation, text))
        idx += 1

    return records[:n]


if __name__ == "__main__":
    out_path = Path(__file__).parent / "synthetic_reviews.json"
    data = generate(300)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Generated {len(data)} synthetic records → {out_path}")
