"""Route tickets, then show accuracy and cost per 1,000 tickets at each confidence threshold.

    python run_eval.py                              # baseline router
    python run_eval.py --answers jev_answers.jsonl  # score Jev (or any model) answers

Tickets above the threshold are routed automatically; the rest go to a person.
Train = oldest 70% of tickets, test = newest 30%, so the test looks like next month's queue.
The threshold is picked on a validation slice (the newest 20% of the training tickets),
never on the test set, the way a pilot has to pick it before seeing next month's tickets.
"""
import argparse, json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from triage.models import BaselineRouter, FileRouter
from triage.metrics import sweep, calibration, by_month, pick_threshold, bootstrap

THRESHOLDS = [0.0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--answers", help="JSONL of Choice answers on data/test_set.jsonl, scored instead of the baseline")
    ap.add_argument("--val-answers", help="JSONL of answers on data/val_set.jsonl, used to pick the threshold")
    ap.add_argument("--confidence", choices=["confidence", "top"], default="confidence",
                    help="threshold on the answer's confidence field (default) or its top probability")
    ap.add_argument("--tickets", default="data/tickets.jsonl")
    ap.add_argument("--costs", default="costs.json")
    ap.add_argument("--out", default="reports")
    args = ap.parse_args()

    tickets = [json.loads(l) for l in open(args.tickets)]
    costs = json.load(open(args.costs))
    cut = int(len(tickets) * 0.7)
    train, test = tickets[:cut], tickets[cut:]

    vcut = int(len(train) * 0.8)
    router = FileRouter(args.answers, args.val_answers) if args.answers else BaselineRouter()
    f = args.confidence
    val_answers = router.validation_answers(train[:vcut], train[vcut:])
    val_rows, _, _ = sweep(train[vcut:], val_answers, costs, THRESHOLDS, f)
    pick = pick_threshold(val_rows, costs["target_accuracy"])

    answers = router.fit(train).answer(test)
    rows, manual, model_cost = sweep(test, answers, costs, THRESHOLDS, f)
    cal, ece = calibration(test, answers, field=f)
    best = next((s for s in rows if pick and s["threshold"] == pick["threshold"]), None)
    hindsight = pick_threshold(rows, costs["target_accuracy"])
    ci = bootstrap(test, answers, best["threshold"], f) if best else None
    months = by_month(test, answers, best["threshold"] if best else 0.9, f)

    out = Path(args.out); out.mkdir(exist_ok=True)
    json.dump({"router": router.name, "n_train": len(train), "n_test": len(test),
               "test_from": test[0]["created_at"][:10], "test_to": test[-1]["created_at"][:10],
               "costs": costs, "manual_cost_per_1k": manual, "model_cost_per_1k": model_cost,
               "validation_sweep": val_rows, "validation_pick": pick, "sweep": rows,
               "test_at_pick": best, "test_at_pick_bootstrap95": ci, "hindsight_best_on_test": hindsight,
               "calibration": cal, "ece": ece, "by_month": months},
              open(out / "results.json", "w"), indent=2)

    L = [f"# Ticket routing eval: {router.name}", "",
         f"Train: {len(train)} older tickets. Test: {len(test)} tickets from {test[0]['created_at'][:10]} to {test[-1]['created_at'][:10]}, {len(set(t['team'] for t in test))} teams.",
         f"Routing every ticket by hand costs ${manual:,.0f} per 1,000 tickets ({costs['manual_triage_minutes']} min each at ${costs['triage_wage_per_hour']}/hr).",
         f"Model cost at ${costs['model_price_per_m_input_tokens']} per million input tokens: ${model_cost:.3f} per 1,000 tickets.", "",
         "## Accuracy and cost by confidence threshold", "",
         "| Threshold | Routed automatically | Accuracy on those | Misroutes per 1,000 | Sent to a person per 1,000 | Cost per 1,000 | Saving vs all manual |",
         "|---:|---:|---:|---:|---:|---:|---:|"]
    for s in rows:
        acc = f"{s['auto_accuracy']:.1%} ({s['n_auto_correct']} of {s['n_auto']})" if s["auto_share"] else "n/a"
        L.append(f"| {s['threshold']:.2f} | {s['auto_share']:.0%} | {acc} | {s['misroutes_per_1k']:.0f} | {s['deferred_per_1k']:.0f} | ${s['cost_per_1k']:,.0f} | ${s['saving_vs_manual_per_1k']:,.0f} |")
    L += ["", f"Each misroute is charged {costs['misroute_minutes']} minutes (the wrong team reads it, then it is moved and re-queued).", ""]
    if best:
        met = "meets" if best["auto_accuracy"] >= costs["target_accuracy"] else "misses"
        L += [f"**Threshold picked on the validation slice ({len(train) - vcut} older tickets): {best['threshold']:.2f}.** "
              f"On the test tickets it routes {best['auto_share']:.0%} automatically at {best['auto_accuracy']:.1%} accuracy "
              f"({best['n_auto_correct']} of {best['n_auto']}), which {met} the {costs['target_accuracy']:.0%} bar "
              f"(bootstrap 95% range {ci['accuracy'][0]:.0%} to {ci['accuracy'][1]:.0%}), and saves ${best['saving_vs_manual_per_1k']:,.0f} per 1,000 tickets.", ""]
    else:
        L += [f"**No threshold reached {costs['target_accuracy']:.0%} on the validation slice; this router should stay in shadow mode.**", ""]
    if hindsight:
        L += [f"In hindsight, the lowest threshold that clears the bar on the test tickets is {hindsight['threshold']:.2f} "
              f"({hindsight['auto_share']:.0%} routed at {hindsight['auto_accuracy']:.1%}, {hindsight['n_auto_correct']} of {hindsight['n_auto']}). "
              "The validation pick cleared the bar by a small margin on few tickets, and the team mix also shifted between older and newer tickets, so a threshold chosen once is not enough evidence; a pilot re-checks it every week on a few hundred routes.", ""]
    L += ["## Does confidence track accuracy?", "",
          f"Expected calibration error: {ece:.3f} (0 means confidence equals accuracy in every bucket).", "",
          "| Confidence bucket | Tickets | Mean confidence | Actual accuracy |", "|---|---:|---:|---:|"]
    for c in cal:
        L.append(f"| {c['bucket']} | {c['n']} | {c['mean_confidence']:.2f} | {c['accuracy']:.0%} |")
    L += ["", "## By month (drift check)", "", "| Month | Tickets | Accuracy, all | Routed automatically | Accuracy, routed |", "|---|---:|---:|---:|---:|"]
    for m, d in sorted(months.items()):
        ar = f"{d['auto_correct']/d['auto']:.0%}" if d["auto"] else "n/a"
        L.append(f"| {m} | {d['n']} | {d['correct']/d['n']:.0%} | {d['auto']} | {ar} |")
    (out / "report.md").write_text("\n".join(L) + "\n")

    fig, ax = plt.subplots(figsize=(6.4, 3.4), dpi=150)
    xs = [s["threshold"] for s in rows]
    ax.plot(xs, [s["auto_share"] * 100 for s in rows], "k-o", ms=3, label="% routed automatically")
    ax.plot(xs, [s["auto_accuracy"] * 100 if s["auto_share"] else None for s in rows], "k--s", ms=3, label="% accuracy on those")
    ax.axhline(costs["target_accuracy"] * 100, color="k", lw=0.6, ls=":")
    ax.set_xlabel("Confidence threshold"); ax.set_ylabel("%"); ax.set_ylim(0, 102)
    ax2 = ax.twinx()
    ax2.plot(xs, [s["cost_per_1k"] for s in rows], color="0.5", marker="^", ms=3, label="Cost per 1,000 tickets ($)")
    ax2.set_ylabel("$ per 1,000 tickets")
    h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, fontsize=7, loc="lower left", frameon=False)
    fig.tight_layout(); fig.savefig(out / "threshold_chart.png")
    print((out / "report.md").read_text())


if __name__ == "__main__":
    main()
