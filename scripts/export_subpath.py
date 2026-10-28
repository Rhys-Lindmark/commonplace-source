#!/usr/bin/env python3
"""Export the deploy-ready app into an existing static website, without dependencies."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--destination', type=Path, required=True)
parser.add_argument('--base-path', default='/commonplace/')
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent
source = root / 'dist'
if args.destination.is_symlink():
    raise SystemExit('Destination must not be a symlink.')
destination = args.destination.resolve()
base = args.base_path
if not base.startswith('/') or not base.endswith('/') or any(c not in '/abcdefghijklmnopqrstuvwxyz0123456789-_' for c in base):
    raise SystemExit('Use a safe absolute base path with a trailing slash.')
marker = destination / 'commonplace-release.json'
previous = json.loads(marker.read_text()) if marker.exists() else {}
if destination.exists() and any(destination.iterdir()) and previous.get('generated_by') != 'commonplace-static-export-v1':
    raise SystemExit('Refusing to overwrite an existing directory without an export marker.')
revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
old = previous.get('files', {})
files = {}
updated = 0
for file in sorted(source.rglob('*')):
    if file.is_symlink():
        raise SystemExit(f'Refusing source symlink: {file}')
    if not file.is_file():
        continue
    relative = file.relative_to(source).as_posix()
    data = file.read_bytes()
    if relative == 'index.html':
        text = data.decode()
        if '<base ' in text:
            raise SystemExit('Source already has a base element; reconcile before exporting.')
        text = text.replace('<head>', f'<head><base href="{base}"><link rel="canonical" href="https://ai.rhyslindmark.com{base}">', 1)
        data = text.encode()
    target = destination / relative
    if target.is_symlink() or any(parent.is_symlink() for parent in target.parents if parent != destination.parent):
        raise SystemExit(f'Refusing destination symlink: {target}')
    digest = hashlib.sha256(data).hexdigest()
    files[relative] = digest
    if target.exists():
        existing = hashlib.sha256(target.read_bytes()).hexdigest()
        if existing == digest:
            continue
        if old.get(relative) != existing:
            raise SystemExit(f'Preserve local changes before replacing: {target}')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    updated += 1
for relative, digest in old.items():
    if Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise SystemExit('Invalid previous export path.')
    if relative in files:
        continue
    target = destination / relative
    if not target.is_relative_to(destination) or target.is_symlink():
        raise SystemExit('Invalid previous export path.')
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise SystemExit(f'Preserve local changes before removing stale export: {target}')
        target.unlink()
metadata = {'generated_by': 'commonplace-static-export-v1', 'source_repository': 'https://github.com/Rhys-Lindmark/commonplace-source', 'source_commit': revision, 'base_path': base, 'files': files}
marker.write_text(json.dumps(metadata, sort_keys=True, indent=2) + '\n')
print(json.dumps({'destination': str(destination), 'source_commit': revision, 'file_count': len(files), 'updated_files': updated}))
