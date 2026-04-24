#!/usr/bin/env python3
"""Add this repository's OpenCode setup to the global config directory.

The script is intentionally additive: it creates missing directories/files and
adds missing package dependencies, but it does not overwrite existing files or
existing dependency versions unless --override is used for copied files.
"""

from __future__ import annotations

import argparse
import filecmp
import json
import os
import shutil
from pathlib import Path
from typing import Any


PACKAGE_SECTIONS = (
    "dependencies",
    "devDependencies",
    "optionalDependencies",
    "peerDependencies",
)


def default_config_dir() -> Path:
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        return Path(xdg_config_home).expanduser() / "opencode"
    return Path.home() / ".config" / "opencode"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install the local .opencode setup into the global OpenCode config."
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=default_config_dir(),
        help="Global OpenCode config directory. Defaults to $XDG_CONFIG_HOME/opencode or ~/.config/opencode.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing files.",
    )
    parser.add_argument(
        "--override",
        action="store_true",
        help="Replace existing plugin and skill files with the local versions.",
    )
    return parser.parse_args()


def ensure_dir(path: Path, dry_run: bool) -> None:
    if path.exists():
        if not path.is_dir():
            raise RuntimeError(f"Expected directory but found file: {path}")
        print(f"present: {path}")
        return

    print(f"create:  {path}")
    if not dry_run:
        path.mkdir(parents=True, exist_ok=True)


def copy_tree(source_dir: Path, target_dir: Path, dry_run: bool, override: bool) -> None:
    if not source_dir.is_dir():
        return

    ensure_dir(target_dir, dry_run)

    for source in sorted(source_dir.rglob("*")):
        relative = source.relative_to(source_dir)
        target = target_dir / relative

        if source.is_dir():
            ensure_dir(target, dry_run)
            continue

        if target.exists():
            if target.is_file() and filecmp.cmp(source, target, shallow=False):
                print(f"present: {target}")
            elif target.is_file() and override:
                print(f"replace: {source} -> {target}")
                if not dry_run:
                    shutil.copy2(source, target)
            else:
                print(f"skip:    {target} already exists")
            continue

        print(f"copy:    {source} -> {target}")
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected JSON object in {path}")
    return data


def merge_package_json(source_path: Path, target_path: Path, dry_run: bool) -> None:
    if not source_path.is_file():
        return

    source = load_json(source_path)

    if not target_path.exists():
        print(f"copy:    {source_path} -> {target_path}")
        if not dry_run:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)
        return

    target = load_json(target_path)
    changed = False

    for section in PACKAGE_SECTIONS:
        source_packages = source.get(section)
        if not isinstance(source_packages, dict):
            continue

        target_packages = target.get(section)
        if target_packages is None:
            target[section] = dict(source_packages)
            changed = True
            print(f"add:     package.json {section}")
            continue

        if not isinstance(target_packages, dict):
            print(f"skip:    package.json {section} is not an object")
            continue

        for name, version in source_packages.items():
            if name in target_packages:
                print(f"present: package.json {section}.{name}")
                continue
            target_packages[name] = version
            changed = True
            print(f"add:     package.json {section}.{name}")

    if not changed:
        return

    if not dry_run:
        target_path.write_text(json.dumps(target, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parent
    source_opencode = repo_root / ".opencode"
    target_config = args.config_dir.expanduser().resolve()

    ensure_dir(target_config, args.dry_run)
    copy_tree(
        source_opencode / "plugins",
        target_config / "plugins",
        args.dry_run,
        args.override,
    )
    copy_tree(
        source_opencode / "skills",
        target_config / "skills",
        args.dry_run,
        args.override,
    )
    merge_package_json(
        source_opencode / "package.json",
        target_config / "package.json",
        args.dry_run,
    )


if __name__ == "__main__":
    main()
