# Ticket routing eval: baseline (TF-IDF + logistic regression, isotonic calibration)

Train: 743 older tickets. Test: 319 tickets from 2026-07-01 to 2026-11-17, 10 teams.
Routing every ticket by hand costs $991 per 1,000 tickets (2.0 min each at $29.74/hr).
Model cost at $0.042 per million input tokens: $0.014 per 1,000 tickets.

## Accuracy and cost by confidence threshold

| Threshold | Routed automatically | Accuracy on those | Misroutes per 1,000 | Sent to a person per 1,000 | Cost per 1,000 | Saving vs all manual |
|---:|---:|---:|---:|---:|---:|---:|
| 0.00 | 100% | 74.9% (239 of 319) | 251 | 0 | $1,243 | $-252 |
| 0.30 | 98% | 76.0% (237 of 312) | 235 | 22 | $1,187 | $-196 |
| 0.40 | 91% | 78.3% (227 of 290) | 197 | 91 | $1,069 | $-78 |
| 0.50 | 79% | 85.3% (214 of 251) | 116 | 213 | $786 | $205 |
| 0.60 | 66% | 91.0% (191 of 210) | 60 | 342 | $634 | $357 |
| 0.70 | 54% | 93.1% (161 of 173) | 38 | 458 | $640 | $351 |
| 0.80 | 42% | 94.0% (125 of 133) | 25 | 583 | $702 | $289 |
| 0.85 | 35% | 97.3% (108 of 111) | 9 | 652 | $693 | $298 |
| 0.90 | 24% | 98.7% (75 of 76) | 3 | 762 | $771 | $221 |
| 0.95 | 5% | 100.0% (15 of 15) | 0 | 953 | $945 | $47 |

Each misroute is charged 10.0 minutes (the wrong team reads it, then it is moved and re-queued).

**Threshold picked on the validation slice (149 older tickets): 0.70.** On the test tickets it routes 54% automatically at 93.1% accuracy (161 of 173), which misses the 95% bar (bootstrap 95% range 89% to 97%), and saves $351 per 1,000 tickets.

In hindsight, the lowest threshold that clears the bar on the test tickets is 0.85 (35% routed at 97.3%, 108 of 111). The validation pick cleared the bar by a small margin on few tickets, and the team mix also shifted between older and newer tickets, so a threshold chosen once is not enough evidence; a pilot re-checks it every week on a few hundred routes.

## Does confidence track accuracy?

Expected calibration error: 0.061 (0 means confidence equals accuracy in every bucket).

| Confidence bucket | Tickets | Mean confidence | Actual accuracy |
|---|---:|---:|---:|
| 0.00-0.50 | 68 | 0.40 | 37% |
| 0.50-0.70 | 78 | 0.60 | 68% |
| 0.70-0.80 | 40 | 0.76 | 90% |
| 0.80-0.90 | 57 | 0.85 | 88% |
| 0.90-0.95 | 61 | 0.93 | 98% |
| 0.95-1.00 | 15 | 0.96 | 100% |

## By month (drift check)

| Month | Tickets | Accuracy, all | Routed automatically | Accuracy, routed |
|---|---:|---:|---:|---:|
| 2026-07 | 33 | 70% | 19 | 100% |
| 2026-08 | 96 | 81% | 40 | 98% |
| 2026-09 | 80 | 74% | 49 | 84% |
| 2026-10 | 74 | 72% | 45 | 96% |
| 2026-11 | 36 | 72% | 20 | 95% |
