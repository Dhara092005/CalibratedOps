# Five-minute project presentation

## Opening: the problem

"AI agents can propose useful actions, but their confidence may be misleading. Requiring review for every decision creates work, while allowing every decision to execute can create errors. This project studies how to choose the handoff while preserving human control."

Start `python -m calibrated_ops serve` and open the local dashboard.

## Demonstrate the oversight loop

Click **Load demo incidents**. Explain that these incidents and all infrastructure actions are synthetic. Show an automatically handled case with the status filter, then return to **Needs review**.

Select an uncertain case. Show the evidence, proposed action, raw confidence, calibrated estimate, and labeled bin observations. Explain that calibration estimates observed correctness from past outcomes rather than accepting the agent's confidence at face value.

Choose an incident whose proposal disagrees with the simple evidence. Select the supported alternative action, write an explanation, and click **Use alternative**. The decision is recorded and the simulation label is revealed afterward.

Approve another reasonable proposal. Reject a high-risk proposal when more evidence would be needed. Show that rejection creates no action and that high risk requires review even above the numerical confidence threshold.

## Show the trace

Open **Decision audit**. Expand a human decision to show reviewer name, feedback, action, and client-reported review duration. Show a simulated execution event. Explain that transactional state changes prevent two views from deciding the same pending case twice.

## Show the experiment

Open **Experiment lab** and run the default comparison. Describe the four policies. The reviewer is simulated and imperfect; this is not evidence from human participants.

Compare accuracy and review effort. Inspect reliability, Brier score, and ECE. Explain that improved calibration can cause more review at a fixed threshold and does not guarantee the best final accuracy. Run another threshold if time permits. These comparisons are exploratory; final research needs a separate validation set for choosing thresholds.

## Show the real-agent boundary

Create a custom incident with the local rule agent. It has no calibrated correctness estimate, so review is mandatory. If you configured a key, repeat with OpenAI and non-sensitive synthetic evidence. Explain that an LLM proposal does not make self-reported confidence calibrated.

## Closing

"The application demonstrates agent adapters, calibration, an enforced human handoff, persistent decisions, and reproducible policy evaluation. A research claim about empowerment needs representative data and a human study measuring understanding, control, workload, and trust."

Use `python -m calibrated_ops study --repeats 20` to produce supporting JSON, CSV, and a report. Use the README and architecture guide for implementation questions.
