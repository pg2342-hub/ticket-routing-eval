"""Threshold sweep, calibration check and cost per 1,000 tickets."""
import numpy as np


def conf(a, field="confidence"):
    """Confidence used for the threshold. A refusal has no choice, so it always goes to a person."""
    if a.get("type") == "refusal" or "choice" not in a:
        return -1.0
    if field == "top" or a.get("confidence") is None:
        if not a.get("probabilities"):
            return -1.0
        return max(a["probabilities"].values())
    return a["confidence"]


def rows(tickets, answers, field="confidence"):
    return [(conf(answers[t["id"]], field), answers[t["id"]].get("choice") == t["team"], t) for t in tickets]


def sweep(tickets, answers, costs, thresholds, field="confidence"):
    r = rows(tickets, answers, field)
    n = len(r)
    tok = np.mean([len(t["text"]) / 4 for _, _, t in r])  # rough tokens per ticket
    model_cost_per_1k = 1000 * tok * costs["model_price_per_m_input_tokens"] / 1e6
    wage_min = costs["triage_wage_per_hour"] / 60
    manual_per_1k = 1000 * costs["manual_triage_minutes"] * wage_min
    out = []
    for th in thresholds:
        auto = [ok for c, ok, _ in r if c >= th]
        a = len(auto) / n
        acc = (sum(auto) / len(auto)) if auto else float("nan")
        per1k_auto = 1000 * a
        per1k_wrong = per1k_auto * (1 - acc) if auto else 0.0
        per1k_deferred = 1000 - per1k_auto
        cost = (per1k_deferred * costs["manual_triage_minutes"] * wage_min
                + per1k_wrong * costs["misroute_minutes"] * wage_min
                + model_cost_per_1k)
        out.append({"threshold": th, "n_auto": len(auto), "n_auto_correct": int(sum(auto)), "auto_share": a, "auto_accuracy": acc,
                    "auto_per_1k": per1k_auto, "misroutes_per_1k": per1k_wrong,
                    "deferred_per_1k": per1k_deferred, "cost_per_1k": cost,
                    "saving_vs_manual_per_1k": manual_per_1k - cost})
    return out, manual_per_1k, model_cost_per_1k


def calibration(tickets, answers, bins=(0, .5, .7, .8, .9, .95, 1.0001), field="confidence"):
    r = [x for x in rows(tickets, answers, field) if x[0] >= 0]
    out = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        b = [(c, ok) for c, ok, _ in r if lo <= c < hi]
        if b:
            out.append({"bucket": f"{lo:.2f}-{min(hi, 1):.2f}", "n": len(b),
                        "mean_confidence": float(np.mean([c for c, _ in b])),
                        "accuracy": float(np.mean([ok for _, ok in b]))})
    ece = sum(x["n"] * abs(x["mean_confidence"] - x["accuracy"]) for x in out) / len(r)
    return out, ece


def by_month(tickets, answers, threshold, field="confidence"):
    out = {}
    for c, ok, t in rows(tickets, answers, field):
        m = t["created_at"][:7]
        d = out.setdefault(m, {"n": 0, "correct": 0, "auto": 0, "auto_correct": 0})
        d["n"] += 1; d["correct"] += ok
        if c >= threshold:
            d["auto"] += 1; d["auto_correct"] += ok
    return out


def pick_threshold(sweep_rows, target_accuracy):
    ok = [s for s in sweep_rows if s["auto_share"] > 0 and s["auto_accuracy"] >= target_accuracy]
    return min(ok, key=lambda s: s["threshold"]) if ok else None


def bootstrap(tickets, answers, threshold, field="confidence", n=2000, seed=0):
    """95% range for accuracy and share routed at one threshold, resampling test tickets."""
    rng = np.random.default_rng(seed)
    r = rows(tickets, answers, field)
    accs, shares = [], []
    for _ in range(n):
        s = [r[i] for i in rng.integers(0, len(r), len(r))]
        auto = [ok for c, ok, _ in s if c >= threshold]
        shares.append(len(auto) / len(s))
        if auto:
            accs.append(sum(auto) / len(auto))
    q = lambda x: (float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5)))
    return {"accuracy": q(accs), "share": q(shares)}
