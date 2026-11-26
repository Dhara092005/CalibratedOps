# Prediction runs and incident-date review

Version 1.3 adds a local sequential prediction runner. This uses individual Responses API requests, not the provider's asynchronous Batch API; no Batch discounts or completion guarantees apply.

## Resolve date discrepancies

1. Open **Label review**, select the original dataset, and choose the affected case.
2. Open **Review incident date**. Inspect the linked original report. The app does not independently verify the source or choose between conflicting dates.
3. Enter the reviewer, date, source URL, and reasoning. Choose **Confirm stored date**, **Correct date**, or **Still unresolved**, then save.
4. Review the action label separately. Saving a date does not accept a flagged label.
5. Once all labels and date discrepancies are resolved, create a reviewed dataset version.

Date assertions have independent revision checks and append-only history. The original source date and notes remain unchanged. A new reviewed version receives the selected date, original collection date, and frozen date-review provenance. Historical caveat text remains attached. Date corrections do not resolve separate time discrepancies, move records across splits, or change past experiments. Unresolved discrepancies block new reviewed versions; previously created versions stay frozen.

## Run offline first

1. Open **Prediction runs** and select a dataset. For research, use your reviewed version.
2. Choose **Local rules · offline** and **Create run**. Creating a run makes no model request.
3. Click **Start / resume predictions**. The app processes one case at a time and saves each result locally.
4. When complete, click **Open prediction dataset for evaluation**, then **Evaluate dataset** in Dataset lab.

The output is a separate frozen dataset. Evidence, labels, groups, and splits stay the same; predictions and the agent identity are replaced. Calibration uses only the calibration split, threshold selection uses validation, and final policy comparison uses test cases. Human-review outcomes in these evaluations are simulated. Previously inspected test labels require a fresh holdout for confirmatory research. The 17-case public seed collection is too small to establish reliable calibration or human-empowerment claims.

## Configure a live AI run

Set `OPENAI_API_KEY` in the server's environment and optionally `OPENAI_MODEL`, then restart the app. Do not put a key in source files, dataset content, or browser fields. Live runs require a reviewed dataset version, the evidence/charges acknowledgment, and an explicit Start action. Keys remain in the process environment and are not written to prediction runs.

Only incident evidence and impact risk are sent to OpenAI. Labels, recovery notes, source links, dates, record IDs, and split membership are excluded from the request. Requested model, prompt hash, resolved response model, response ID, and reported token usage are recorded. Use a dated model version when available for stronger reproducibility. Finalization rejects a run whose returned model versions differ. The output cap is 2,048 tokens; refusals or incomplete responses count as failures. See the official [Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs).

## Pause, reload, and retry

- Pause stops further requests after the current case finishes. Navigating away or closing the browser also stops the browser-driven loop. Keep the server running to save an in-flight response.
- Reopen **Prediction runs**, select the saved run, and click Start to continue. Successful cases are never reissued.
- After a server interruption, use **Recover interrupted request**. That case becomes uncertain, because provider completion and usage may be unknown. Recovery itself makes no API request.
- Failed/uncertain cases require manual **Retry failed cases** and, for live AI, acknowledgment of possible additional charges. Then click Start. The cap is three attempts per case, with no automatic retry.
- All cases must succeed before creating a prediction dataset. Cases are never silently dropped. Finalization is idempotent.

Use one server process per database. Multiple browser tabs may observe the same run, but database claims prevent duplicate in-flight cases. Recovery is intended for a restarted server, not another process sharing the database. Runs support at most 500 cases. Successful-response token counts are informative only: failed or interrupted usage can be unknown, and no monetary cost estimate is provided.

Run details, explanations, and usage are retained in local SQLite. Bootstrap state lists only run summaries. API error bodies and credentials are not exposed. Source ZIP packaging excludes the local database. Tests use local rules and mocked provider responses; a successful test suite does not verify account-specific live API access.
