# CalibratedOps experiment report

All results below are synthetic. They do not establish real model performance or human empowerment.

Configuration: starting seed 42; 20 independent repeats; 1000 calibration cases and 500 held-out test cases per repeat; review threshold 80%; simulated reviewer correctness 85% in expectation.

| Policy | Mean accuracy | Mean review rate | Mean high-risk errors per run |
| --- | ---: | ---: | ---: |
| automatic | 56.1% | 0.0% | 43.0 |
| review_all | 84.8% | 100.0% | 15.2 |
| selective_raw | 83.2% | 69.2% | 15.2 |
| selective_calibrated | 83.8% | 87.5% | 15.2 |

Mean Brier score: raw 0.2380; calibrated 0.2062. Mean ECE: raw 0.1824; calibrated 0.0341. Lower is better.

Paired accuracy difference (calibrated selective minus raw selective): 0.56 percentage points; approximate 95% interval [0.18, 0.94].

Approximate normal 95% intervals across independent seeds; descriptive, especially with few repeats. Not evidence about human participants.

## Interpretation

Better calibration does not guarantee less review effort or higher final accuracy at a fixed numerical threshold. A calibrated score can be lower than the agent's raw confidence and trigger more handoffs. The reviewer is imperfect, so reviewing a correct proposal can also introduce an error. The experiment should reveal these trade-offs rather than assume one policy wins.

High-risk errors count incorrect high-risk final actions after both automatic and reviewed decisions. Mandatory review does not guarantee correctness. Review rate is a workload proxy, not a measure of engagement. Calibration is trained on independent generated cases; evaluation labels are not fed back during the run.

The full JSON includes each seed, calibration reliability bins, policy counts, and aggregate intervals. The CSV contains metric means and intervals. Reproduce this report with the command:

```powershell
python -m calibrated_ops study --seed 42 --repeats 20 --test-size 500 --threshold 0.8 --reviewer-accuracy 0.85
```
