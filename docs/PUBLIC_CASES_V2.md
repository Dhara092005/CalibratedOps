# Second staged public-case collection

Collected and imported on 24 November 2026 as **Additional public incidents - pending source review v2**. Six new records from five GitHub reports bring the current inventory to 28 cases. None were accepted as human-reviewed references. Labels, risks, and dependency mappings remain provisional assistant judgments.

| Record | Source | Split | Review concern |
| --- | --- | --- | --- |
| gh-2024-12-17-live-updates | [December 2024 report](https://github.blog/news-insights/company-news/github-availability-report-december-2024/) | calibration | Preserve both rollback and added capacity; source start times disagree. |
| gh-2025-03-29-credentials | [March 2025 report](https://github.blog/news-insights/company-news/github-availability-report-march-2025/) | validation | Related failures form one case; credential renewal is distinct from redeployment. |
| gh-2025-04-11-codespaces | [April 2025 report](https://github.blog/news-insights/company-news/github-availability-report-april-2025/) | validation | Separate recovery from later preventive work. |
| gh-2025-05-01-attachments | [May 2025 report](https://github.blog/news-insights/company-news/github-availability-report-may-2025/) | test | Review the feature-flag rollback mapping. |
| gh-2025-05-28-runner-cache | [May 2025 report](https://github.blog/news-insights/company-news/github-availability-report-may-2025/) | test | Include cache repair and capacity; avoid an unsupported dependency. |
| gh-2025-07-28-gei | [July 2025 report](https://github.blog/news-insights/company-news/github-availability-report-july-2025/) | test | Replacement provisioning is only coarsely represented by scale_capacity. |

Source URLs and incident IDs were checked against both earlier collections: no overlap. Report groups are kept in one split. The March report describes related failures; they are not inflated into two independent cases. This is retrospective collection, not a sealed prospective holdout. No source article text is copied in full.

Reproduce the import from the project directory:

```powershell
python scripts/prepare_research_materials.py --add-cases --case-file calibrated_ops/data/additional_public_incidents_v2.json
python scripts/export_reference_worksheets.py
python scripts/research_report.py
```

Import is idempotent for unchanged rows. Earlier datasets and their human review history remain intact. Open Label review and select the v2 dataset to inspect the new cases. For current gaps use runs/research-materials/calibration-readiness.json; the case count alone does not make calibration eligible.
