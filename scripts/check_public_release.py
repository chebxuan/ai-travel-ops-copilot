"""Check the public Git index/history and deterministic synthetic price fixtures."""
from pathlib import Path
import csv
import hashlib
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    'private key': rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
    'AWS key': rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    'GitHub token': rb'\b(?:ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{50,})\b',
    'API token': rb'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}\b',
    'home path': rb'/(?:Users/[^/\s]+|home/ubuntu)/',
    'Feishu webhook credential': rb'https://open\.feishu\.cn/open-apis/bot/v2/hook/[0-9a-f-]+',
}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def main():
    paths = [p for p in git('ls-files', '-z').decode().split('\0') if p]
    failures = []
    for name in paths:
        p = ROOT / name
        parts = set(p.relative_to(ROOT).parts)
        if parts & {'node_modules', '.next', '.local', '.venv', 'references', 'legacy', 'experiments', 'archive'}:
            failures.append((name, 'excluded directory'))
        if (p.name.startswith('.env') and p.name != '.env.example') or p.suffix in {'.dump', '.pem', '.ppk', '.key', '.pdf', '.xlsx', '.jpg', '.png', '.ico', '.db'} or 'payment' in p.name.lower():
            failures.append((name, 'excluded filename'))
        if p.is_symlink():
            failures.append((name, 'symlink'))
        data = p.read_bytes()
        if b'\x00' in data:
            failures.append((name, 'unexpected binary'))
        for label, pattern in PATTERNS.items():
            if re.search(pattern, data):
                failures.append((name, label))
    count = 0
    for path in (ROOT / 'data/products/services/mashes').glob('*.csv'):
        with path.open(encoding='utf-8') as stream:
            for row in csv.DictReader(stream):
                code = row['项目编号']
                seed = int(hashlib.sha256(('public-demo-v1:' + code).encode()).hexdigest()[:8], 16)
                value = str(101 + seed % 199)
                if row['单价'] not in {'', '0', value}:
                    failures.append((code, 'non-synthetic standard price'))
                if row['单价（旺季）'] not in {'', '0', str(int(value) + 37)}:
                    failures.append((code, 'non-synthetic peak price'))
                if not row['项目备注'].startswith('DEMO DATA ONLY'):
                    failures.append((code, 'unlabelled fixture'))
                count += 1
    for p in (ROOT / 'docs').glob('*.md'):
        for href in re.findall(r'\]\(([^)]+)\)', p.read_text()):
            if not re.match(r'https?://|#', href) and not (p.parent / href.split('#')[0]).exists():
                failures.append((str(p.relative_to(ROOT)), 'broken local link'))
    # Inspect every historical blob: removing a file from HEAD alone is insufficient.
    entries = git('rev-list', '--objects', '--all').decode().splitlines()
    blobs = 0
    for entry in entries:
        oid, _, name = entry.partition(' ')
        if git('cat-file', '-t', oid).strip() != b'blob':
            continue
        blobs += 1
        data = git('cat-file', 'blob', oid)
        if name.endswith('payments.json') or '/private/' in name:
            failures.append((name, 'private historical path'))
        for label, pattern in PATTERNS.items():
            if re.search(pattern, data):
                failures.append((name, 'history: ' + label))
    print(json.dumps({'indexed_files': len(paths), 'history_blobs': blobs, 'synthetic_services': count, 'findings': failures}, ensure_ascii=False))
    if failures:
        return 1
    print('PASS: scoped publication checks. Not an exhaustive privacy or licensing guarantee.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
