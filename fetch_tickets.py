"""Pull PostHog's public GitHub issues that carry exactly one team/* label.

Each issue stands in for a support ticket: the text a customer or teammate wrote,
and the team that ended up owning it. Needs the GitHub CLI (gh) logged in.

    python fetch_tickets.py            # writes data/tickets.jsonl
"""
import json, re, subprocess, time
from pathlib import Path

TEAMS = ["product-analytics", "feature-flags", "experiments", "data-warehouse",
         "web-analytics", "llm-analytics", "session-replay", "error-tracking",
         "conversations", "cdp"]
REPO = "PostHog/posthog"


def search(team, page, raw_dir=None):
    if raw_dir and (Path(raw_dir) / f"{team}_{page}.json").exists():
        return json.loads((Path(raw_dir) / f"{team}_{page}.json").read_text())
    out = subprocess.run(["gh", "api", "-X", "GET", "search/issues",
                          "-f", f'q=repo:{REPO} is:issue label:"team/{team}"',
                          "-f", "per_page=100", "-f", f"page={page}",
                          "-f", "sort=created", "-f", "order=desc"],
                         capture_output=True, text=True, check=True).stdout
    time.sleep(2.5)  # search API allows 30 requests a minute
    return json.loads(out)


PREFIX = re.compile(r"^\s*(\[[^\]]{1,40}\]\s*|[\w\s/().-]{1,40}:\s+)")


def clean_title(t):
    # Drop "Feature flags: ..." or "feat(flags): ..." prefixes, which name the team outright.
    for _ in range(2):
        t = PREFIX.sub("", t, count=1)
    return t.strip()


def clean_body(b):
    b = re.sub(r"<!--.*?-->", " ", b or "", flags=re.S)
    b = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", b)          # images
    b = re.sub(r"https?://\S+", " ", b)                 # links
    b = re.sub(r"\s+", " ", b)
    return b.strip()[:1500]


def main(raw_dir=None):
    rows, seen = [], set()
    for team in TEAMS:
        for page in (1, 2):
            data = search(team, page, raw_dir)
            for it in data.get("items", []):
                teams = [l["name"][5:] for l in it["labels"] if l["name"].startswith("team/")]
                if len(teams) != 1 or teams[0] not in TEAMS or it["number"] in seen:
                    continue
                seen.add(it["number"])
                rows.append({"id": it["number"], "created_at": it["created_at"],
                             "text": clean_title(it["title"]) + "\n" + clean_body(it["body"]),
                             "team": teams[0], "url": it["html_url"]})
    rows.sort(key=lambda r: r["created_at"])
    Path("data").mkdir(exist_ok=True)
    with open("data/tickets.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(len(rows), "tickets written to data/tickets.jsonl")


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else None)
