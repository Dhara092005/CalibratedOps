# Fictional missing-step exercise

This is an assistant-authored teaching fixture, deliberately chosen to expose a limitation of the offline keyword generator. It is not a real incident, independent evaluation, or evidence of general human-review effectiveness. Keep its dashboard separate from public incidents. No reference is recorded as a human acceptance.

Install with `python scripts/setup_correction_demo.py`; repeat installation reuses the same dataset. Use `--check` to validate without database writes.

1. Refresh the app. In Plan lab choose **Fictional correction exercise - missing verification** and **demo-missing-verification**.
2. Keep the offline generator, prepare a job, and generate its proposal. The frozen scripted reference is included even though reference review is pending.
3. The proposal should contain rollback config but omit verification. The scenario explicitly requires both rollback and subsequent verification.
4. Open **Edit the proposed steps**. Keep rollback as step 1 and clarify its description to “Revert the sandbox configuration change.”
5. Click **+ Add step**. Select **Verify recovery**, describe it as “Confirm sandbox health checks pass and errors return to baseline after rollback,” and select step 1 as its prerequisite.
6. Enter your own name and explanation of the missing verification step. Save your edited plan only after inspecting it.
7. Reveal the frozen reference. Expected original: 1/2 required steps; expected edited plan: 2/2, with the dependency declared. This is a scripted structural demonstration.
8. If desired, create a separate comparison dashboard containing this job. Its reference stays provisional, and its results must not be combined with the real-incident dashboard.

The two support records satisfy the dataset importer's three-group/split requirement. They do not constitute calibration or validation evidence for multi-step plan quality.
