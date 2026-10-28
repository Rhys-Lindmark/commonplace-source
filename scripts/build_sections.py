#!/usr/bin/env python3
"""Build bounded browsing sections without rewriting quote records or topic bits."""
import collections
import hashlib
import json
import math
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 10000

def slug(value):
    return re.sub(r'[^a-z0-9]+', '-', unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower()).strip('-')

def author_key(value):
    normalized = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().casefold()
    return re.sub(r'[^a-z0-9]+', '', normalized) or '\uffff' + value.casefold()

def build_sections():
    data = ROOT / 'dist/data'
    manifest_path = data / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    rules_path = ROOT / 'work/topic-sections/rules.json'
    rules = json.loads(rules_path.read_text())
    oversized = {t['name']: t['count'] for t in manifest['topics'] if t['count'] > LIMIT}
    buckets = {name: collections.defaultdict(list) for name in oversized}
    compiled = {name: [(r['name'], re.compile(r'\b(?:' + r['pattern'] + r')\b', re.I)) for r in rules.get(name, [])] for name in oversized}
    original = hashlib.sha256()
    ordinal = 0
    for file in sorted((data / 'records').glob('*.json')):
        raw = file.read_bytes()
        original.update(file.name.encode() + raw)
        for quote in json.loads(raw):
            for parent in quote['topics']:
                if parent not in buckets:
                    continue
                scores = [(len({m.group(0).casefold() for m in pattern.finditer(quote['text'])}), name) for name, pattern in compiled[parent]]
                score, child = max(scores, key=lambda pair: pair[0], default=(0, 'Reflections'))
                if not score:
                    child = 'Reflections'
                buckets[parent][child].append((ordinal, quote['author'], quote['id']))
            ordinal += 1
    assert ordinal == manifest['total']
    folder = data / 'sections'
    folder.mkdir(exist_ok=True)
    groups = []
    files = {}
    for parent, children in buckets.items():
        sections = []
        covered = []
        names = [name for name, _ in compiled[parent]] + ['Reflections']
        for name in names:
            rows = children.get(name, [])
            if not rows:
                continue
            parts = math.ceil(len(rows) / LIMIT)
            if parts > 1:
                rows.sort(key=lambda row: (author_key(row[1]), row[2]))
            width = math.ceil(len(rows) / parts)
            for part, offset in enumerate(range(0, len(rows), width)):
                chunk = rows[offset:offset + width]
                title = name
                description = 'Editorial keyword grouping within ' + parent + '.'
                if parts > 1:
                    a, b = chunk[0][1], chunk[-1][1]
                    first = lambda value: author_key(value)[0].upper() if author_key(value)[0].isascii() else 'Z+'
                    title += ' · ' + first(a) + '–' + first(b) + ' (' + str(part + 1) + ')'
                    description = 'Authors from ' + a + ' to ' + b + '; part ' + str(part + 1) + ' of ' + str(parts) + '.'
                identity = slug(parent) + '--' + slug(name) + '--' + str(part + 1)
                path = 'sections/' + identity + '.json'
                ordinals = sorted(row[0] for row in chunk)
                assert 0 < len(ordinals) <= LIMIT and len(set(ordinals)) == len(ordinals)
                raw = (json.dumps(ordinals, separators=(',', ':')) + '\n').encode()
                files[path] = raw
                covered.extend(ordinals)
                sections.append({'id': identity, 'name': title, 'count': len(ordinals), 'file': path, 'description': description})
        assert len(covered) == oversized[parent] and len(set(covered)) == len(covered), parent
        groups.append({'topic': parent, 'sections': sections})
    old_files = {s['file'] for g in manifest.get('browseGroups', []) for s in g['sections']}
    for path, raw in files.items():
        (data / path).write_bytes(raw)
    for path in old_files - files.keys():
        if not path.startswith('sections/') or '..' in Path(path).parts:
            raise ValueError('Invalid old section path')
        (data / path).unlink(missing_ok=True)
    manifest['browseGroups'] = groups
    manifest['sectionVersion'] = 1
    manifest['sectionLimit'] = LIMIT
    digest = hashlib.sha256((data / manifest['catalog']).read_bytes() + rules_path.read_bytes())
    digest.update(str(manifest.get('dateAuditId', '')).encode())
    for path, raw in sorted(files.items()):
        digest.update(path.encode() + raw)
    manifest['release'] = digest.hexdigest()[:16]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, separators=(',', ':')) + '\n')
    report = {'limit': LIMIT, 'total': ordinal, 'recordsSha256': original.hexdigest(), 'catalogSha256': hashlib.sha256((data / manifest['catalog']).read_bytes()).hexdigest(), 'release': manifest['release'], 'groups': groups, 'membershipBytes': sum(map(len, files.values())), 'largestSection': max([s['count'] for g in groups for s in g['sections']] + [t['count'] for t in manifest['topics'] if t['name'] not in oversized])}
    (ROOT / 'work/topic-sections/report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'groups'}))
    return report

if __name__ == '__main__':
    build_sections()
