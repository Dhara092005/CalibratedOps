# Multi-step recovery plans (v1.5)

**Interface update:** v1.6 replaces the coded text editor and candidate text box below with guided sections, action menus, step cards, and prerequisite checkboxes. Use [the guided-review walkthrough](GUIDED_REVIEW.md) for current buttons and screen instructions. The underlying plan schema, API, versioning, and structural-check semantics below remain applicable.

CalibratedOps now supports reviewed reference plans with ordered steps and explicit prerequisites. Plans are annotations, not executable runbooks. The candidate checker compares supported action names and dependency order; it cannot establish operational safety, verify that a prerequisite was completed, or diagnose infrastructure.

## Review a reference plan

1. Open **Label review**, select the dataset, and select a case.
2. Open **Recovery plan**. Review its original source and recovery notes.
3. Enter one step per line as `action | description | prerequisites`. The first line is step 1. Leave the last field blank when there is no prerequisite. Separate multiple required earlier step numbers with commas.
4. Enter your reviewer name, HTTPS source URL, and explanation.
5. Click **Accept recovery plan**, or **Flag recovery plan** if unresolved. This does not accept or correct the single-action dataset label.

Example:

```text
replace_certificate | Replace the expired internal certificate | 
restart_service | Restart impacted services after replacement | 1
```

Plans contain 1–12 required steps. Descriptions are limited to 500 characters. Dependencies must refer to distinct earlier steps; forward references, cycles, and unsupported action names are rejected. The supported actions include the existing four coarse actions plus `replace_certificate`, `restore_known_good_data`, `repair_records`, `disable_rule`, `optimize_query`, `verify_recovery`, and `other_remediation`. Descriptions carry contextual meaning that the structural checker does not validate.

Two source-backed starter drafts are available for the existing Cloudflare feature-file and GitHub TLS incidents. They are explicitly provisional assistant drafts, not automatic human approvals. Their source URLs and case identities must match the attached provenance. GitHub's [November 2025 report](https://github.blog/news-insights/company-news/github-availability-report-november-2025/) describes certificate replacement followed by service restarts. Cloudflare's [November 18 report](https://blog.cloudflare.com/18-november-2025-outage/) describes known-good configuration-file restoration and downstream restarts. Other multi-action incidents require manual plan annotation.

## Check a proposed sequence

After a reference draft or accepted plan is available, enter one candidate action name per line under **Check a proposed action sequence**, in intended execution order. Click **Check proposed plan**.

- `restart_service` alone misses certificate replacement and violates the restart prerequisite in the example above.
- `restart_service` followed by `replace_certificate` has both actions but violates their dependency order.
- `replace_certificate` followed by `restart_service` matches that reference's action structure.
- Extra actions are reported as unreferenced, not silently ignored. The checker does not establish whether extras are appropriate.

Repeated actions are matched by occurrence: one restart cannot satisfy two required restart steps. Steps without dependency constraints may be reordered. Candidate inputs have the same 12-step limit. The checker uses the saved reference, excluding unsaved edits in the editor. It reports whether that reference is a provisional draft or a locally reviewed annotation. Flagged plans cannot be checked until resolved. Matching requires every reference step, satisfied dependencies, and no unreferenced extra steps.

## Versions, diagnostics, and evaluation

Recovery-plan reviews are append-only, with reviewer, timestamp, explanation, source URL, and revision. Stale saves return a conflict. Reviewer identities are self-entered and qualifications remain unverified. Multi-action source records require accepted plans before **new** reviewed dataset versions can be created; explicit flagged plan annotations also block creation. Existing versions remain available.

Reviewed versions freeze plan annotations alongside label/date review history. Original evidence, coarse labels, groups, splits, predictions, and previous experiments remain unchanged. Prediction output datasets copy frozen source plans and review provenance. A new review round on a child version starts with its own revision count and retains inherited reference context.

Failure analysis now shows frozen reference plans (or explicitly marked source drafts) and identifies when a single proposal omits required recovery steps. Later annotations on a parent do not rewrite a previously frozen child or experiment. The full plan is available in the dedicated unblinded review/diagnostic exports, not bootstrap state, generic experiment summaries, or agent prompts.

The four-policy accuracy benchmark and existing prediction runner retain the original single-action taxonomy. Version 1.7 adds a separate [Plan lab](PLAN_LAB.md) for multi-step proposal generation, human review, and structural evaluation. The reference-plan checker on this page remains a separate assessment of manually entered candidate sequences, without real execution or model calls. A coarse action matching the label must never be interpreted as proof of complete recovery.

## API

- `POST /api/recovery-plan-review`: dataset/record ID, expected revision, decision (`accepted`/`flagged`), `steps` array, reviewer, explanation, source URL. Each step has `action`, `description`, and `requires` (earlier 1-based step numbers).
- `POST /api/recovery-plan-check`: dataset/record ID and `candidate` array of ordered action names.
- Existing dataset-review endpoints return effective plans, local review history, supported actions, and unresolved counts. Their export includes the plan annotations.

Both writes use the application's same-origin session token. Source URLs are retained as references, not fetched by these endpoints. No API keys, shell commands, or infrastructure credentials are needed.
