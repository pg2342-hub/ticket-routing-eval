"""Write the validation and test tickets as System One request bodies, ready to send to Jev.

    python export_test_set.py   # writes data/val_set.jsonl and data/test_set.jsonl

Each line is {"id": <ticket id>, "request": {...}}, where "request" follows the
DecisionsRequest shape in OpenRouter's System One API reference: a "state" holding the
ticket and one "choice" question whose "criteria" keys are the teams. Send each request
with your own client and key, then save each answer as
{"id": <ticket id>, "answer": <answers["team"] from the response>} and run:

    python run_eval.py --val-answers val_answers.jsonl --answers test_answers.jsonl

Set MODEL below to the Jev model version you were given, and keep it pinned for the whole run.
"""
import json

MODEL = "typesafe/jev-1.13"  # model name from the public API example; replace with the pinned version

TEAMS = {
    "product-analytics": "Insights, trends, funnels, retention, paths, dashboards, cohorts, or HogQL queries in product analytics.",
    "feature-flags": "Feature flag creation, targeting, rollout, evaluation, flag SDK behavior, or remote config.",
    "experiments": "A/B tests and experiments: setup, exposures, metrics, results, and statistics.",
    "data-warehouse": "Data warehouse sources and syncs, external tables, SQL editor, views, and data modeling.",
    "web-analytics": "The web analytics dashboard: visitors, pageviews, channels, referrers, bounce rate, and web vitals.",
    "llm-analytics": "LLM analytics or AI observability: traces, generations, token costs, and evaluations of LLM calls.",
    "session-replay": "Session recordings: capture, playback, masking, network and console logs in replays.",
    "error-tracking": "Error tracking: exceptions, stack traces, issue grouping, source maps, and alerts on errors.",
    "conversations": "The support product: inbox, tickets, chat widget, support agent, and customer conversations.",
    "cdp": "Data pipelines and destinations: realtime destinations, transformations, webhooks, and batch exports.",
}

tickets = [json.loads(l) for l in open("data/tickets.jsonl")]
cut = int(len(tickets) * 0.7)
train, test = tickets[:cut], tickets[cut:]
val = train[int(len(train) * 0.8):]
for name, rows in (("val", val), ("test", test)):
    with open(f"data/{name}_set.jsonl", "w") as f:
        for t in rows:
            req = {"model": MODEL, "state": {"ticket": t["text"]},
                   "questions": {"team": {"type": "choice", "criteria": TEAMS,
                                          "instructions": "Which PostHog engineering team should own this ticket?"}}}
            f.write(json.dumps({"id": t["id"], "request": req}) + "\n")
    print(len(rows), f"{name} tickets -> data/{name}_set.jsonl")
