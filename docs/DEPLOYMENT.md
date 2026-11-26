# Deploy the free live demo on Render

This deployment runs the complete Python application behind Caddy, with one public demonstration workspace and temporary SQLite storage. It does not add participant accounts. Render terminates HTTPS; only Caddy's port is exposed. The Python backend remains bound to loopback inside the container.

## What the Blueprint creates

- One Docker web service on the **Free** plan, one instance.
- **No persistent disk and no paid service configuration.** SQLite is temporary at `/var/data/calibrated_ops.sqlite3`.
- `CALIBRATED_DEMO=1`: a sample-data banner, marked exports, and live AI disabled.
- `CALIBRATED_PUBLIC_DEMO=1`: public access with no username or password.
- `/healthz`, an unauthenticated availability check that returns no workspace records.

Render's Free plan can sleep after inactivity and lose filesystem changes on restart, redeploy, or spin-down. Opening the URL wakes it, with an initial delay. The app reseeds its public cases, but demo reviews are disposable. Use it only for demonstrations, not participant collection. Check workspace free-hour and bandwidth limits; this configuration does not add paid resources. See [Render Free](https://render.com/docs/free).

## Deploy

1. Sign in to Render, choose **New > Blueprint**, and select `Dhara092005/CalibratedOps`. Authorize repository access if needed.
2. Select `main` and the root `render.yaml`. Verify that the plan is **Free** and there is **no disk** before deploying. Do not add a card or select a paid upgrade for this demo.
3. Wait for the build and health check to pass. Render supplies `RENDER_EXTERNAL_URL`, which the app uses as its exact allowed HTTPS origin.
4. Open the service's HTTPS address. The public demo opens directly without a sign-in prompt.
5. Verify the incident queue, all three public datasets, a review write, and Research readiness. Treat that write as temporary: it may disappear on restart or redeploy. Live provider calls are disabled in demo mode.

The app imports the three bundled public collections idempotently on startup: 28 provisional cases, with no fabricated reviews, trials, or scores. Set `CALIBRATED_SEED_PUBLIC=0` before startup to disable seeding. Hosted data starts separately from the local workspace. Local reviews, participant records, and backups are not uploaded by a Git deployment.

## Environment settings

| Variable | Purpose |
| --- | --- |
| `PORT` | Public container port; Blueprint uses `10000`. |
| `CALIBRATED_DATABASE` | Absolute temporary database path; no persistent disk in the Free Blueprint. |
| `CALIBRATED_DEMO` | `1` in the Blueprint; marks sample data and disables paid live AI calls. |
| `CALIBRATED_PUBLIC_DEMO` | `1` allows password-free access only when `CALIBRATED_DEMO=1`. |
| `CALIBRATED_PASSWORD` | Required only for private hosting when public-demo mode is off: 16–72 UTF-8 bytes, no newlines. |
| `CALIBRATED_PUBLIC_ORIGIN` | Optional exact HTTPS origin, without a trailing slash; overrides `RENDER_EXTERNAL_URL`, for example when using a custom domain. |
| `CALIBRATED_SEED_PUBLIC` | `1` by default; imports the bundled provisional public datasets. |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | Not needed for the demo. A configured API key is removed from the app environment when demo mode is enabled. |

`CALIBRATED_LOCAL_TEST=1` permits an HTTP loopback origin only for isolated local Docker tests. Never enable it for a hosted service. Private hosting still requires credentials; public-demo mode is explicit and tested separately.

The default demo is public: visitors share temporary sample records and can view its exports. Do not enter personal data or genuine participant responses. Live AI is disabled. Host and origin checks plus the existing review token remain enforced. For private hosting, omit `CALIBRATED_PUBLIC_DEMO` and supply `CALIBRATED_PASSWORD`; Caddy then hashes the secret over stdin and requires authentication for pages, APIs and exports. Private hosting cannot disable authentication through the public-demo flag unless demo mode is also enabled.

## Validate locally

```powershell
python -m unittest discover -s tests -v
docker build -t calibratedops:deploy-test .
python tests/docker_smoke.py
```

The Docker smoke test uses a random test password, a loopback-only port, a temporary QA volume and synthetic evidence. It checks private authentication, password-free public-demo access, hostile host/origin rejection, API writes, bundled dataset import, optional-volume persistence, and fresh-container reset. It removes only the test container and volume it creates.

## Optional persistent hosting

Persistent storage is deliberately excluded from the default deployment. If you later need durable research records, explicitly choose a paid plan and disk, retain one instance, and agree data-handling arrangements before collection. That is a separate decision. Exports contain selected records and are not a complete database backup. Do not put backups or responses in the public repository.

When using a custom domain, set its exact HTTPS origin before starting the app, then verify writes through that domain. Origin mismatches reject writes deliberately. If startup fails, verify the origin, password length, disk path and build logs; do not remove authentication to work around a failed deployment.
