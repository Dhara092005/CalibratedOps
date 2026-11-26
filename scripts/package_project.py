"""Package source and documentation, excluding runtime records and secrets."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
destination = root / "runs" / "CalibratedOps-project.zip"
destination.parent.mkdir(parents=True, exist_ok=True)
included = ("README.md", "pyproject.toml", "start.cmd", ".gitignore", ".dockerignore", "Dockerfile", "render.yaml", ".github", "calibrated_ops", "docs", "tests", "scripts")
count = 0
with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
    for name in included:
        target = root / name
        for item in sorted(target.rglob("*")) if target.is_dir() else [target]:
            if item.is_file() and "__pycache__" not in item.parts and item.suffix != ".pyc":
                archive.write(item, Path("CalibratedOps") / item.relative_to(root))
                count += 1
with ZipFile(destination) as archive:
    if archive.testzip() is not None:
        raise RuntimeError("Archive integrity check failed")
print(f"Packaged {count} source/documentation files: {destination}")
