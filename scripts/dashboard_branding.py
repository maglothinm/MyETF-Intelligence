"""Copy the approved web icons for either dashboard generation entry point."""

from pathlib import Path
import shutil


def copy_branding_assets(output_dir: Path) -> None:
    assets = Path(__file__).with_name("dashboard_assets")
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(assets / "icons", output_dir / "icons", dirs_exist_ok=True)
    shutil.copyfile(assets / "site.webmanifest", output_dir / "site.webmanifest")
