"""Build and verify the internal V9 handoff archive using a runtime allowlist."""

import hashlib
import io
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / 'dist'
NAME = 'fundtrace-agent-v9-20261031'
V9 = 'agent/exports/fundtrace_agent-v9-v1.2-20261031.zip'
EXPECTED_V9_HASH = '658A39086AD8B400C9823DD601C0B2530CE0194000DBC180E90237FEF35DA449'
SECRET_PATTERNS = [
    re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(r'\b(?:sk|ghp|github_pat)[-_][A-Za-z0-9_\-]{20,}\b'),
    re.compile(r'\bBearer\s+[A-Za-z0-9_.\-]{24,}\b', re.I),
    re.compile(r'\b(?:password|api_key|access_token|secret_key)\s*[=:]\s*["\'][^"\'\s]{8,}["\']', re.I),
]


def digest(data):
    return hashlib.sha256(data).hexdigest().upper()


def scan(name, data):
    if name.endswith('.zip'):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if archive.testzip() is not None:
                raise ValueError(f'Corrupt archive: {name}')
            for member in archive.infolist():
                safe_path(member.filename)
                if not member.is_dir():
                    scan(name + '/' + member.filename, archive.read(member))
        return
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        return
    if name.endswith('build_delivery.py'):
        return
    if any(pattern.search(text) for pattern in SECRET_PATTERNS):
        raise ValueError(f'Potential credential requires review: {name}')


def safe_path(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
        raise ValueError(f'Unsafe archive path: {name}')


def git(*args):
    return subprocess.check_output(
        ['git', '-c', f'safe.directory={ROOT.as_posix()}', *args], cwd=ROOT,
        text=True, encoding='utf-8', errors='replace',
    ).strip()


def main():
    paths = {'requirements.txt', V9, 'agent/exports/fundtrace_agent-v9-verification.json'}
    paths.update('core/' + name + '.py' for name in (
        '__init__', 'api', 'store', 'trace', 'rules', 'ruleset', 'ticket', 'rejudge'))
    paths.update('data/' + name for name in ('accounts.csv', 'transactions.csv', 'dataset_meta.json', 'README.md'))
    paths.update('Data and Rules/' + name for name in ('enums.yaml', 'rules/rules_v1.yaml', 'rules/rules_v2.yaml'))
    for folder, suffixes in (('mcp_server', {'.py', '.md', '.sh', '.ps1', '.txt'}),
                             ('agent', {'.py', '.md', '.json'}), ('kb', {'.md'}),
                             ('core/fixtures', {'.json'})):
        for path in (ROOT / folder).rglob('*'):
            rel = path.relative_to(ROOT)
            if any(part in {'dist', '__pycache__', '.pytest_cache', 'screenshots', 'exports'} for part in rel.parts[1:]):
                continue
            if path.is_file() and path.suffix in suffixes:
                paths.add(rel.as_posix())
    content = {}
    for name in sorted(paths):
        safe_path(name)
        content[name] = (ROOT / name).read_bytes()
        if name.endswith('.sh') or name in {'data/accounts.csv', 'data/transactions.csv'}:
            content[name] = content[name].replace(b'\r\n', b'\n')
        scan(name, content[name])
    if digest(content[V9]) != EXPECTED_V9_HASH:
        raise ValueError('V9 source ZIP differs from the verified release.')
    content['START_HERE.md'] = content['agent/handoff/DELIVERY.md']
    manifest = {
        'release': NAME, 'platform_version': 9, 'dataset': 'sim-gen_profile_v1-seed42',
        'source_commit': git('rev-parse', 'HEAD'), 'source_dirty': bool(git('status', '--porcelain')),
        'scope': 'Internal technical handoff; screenshots/video/sign-off pending.',
        'files': [{'path': name, 'size': len(data), 'sha256': digest(data)} for name, data in content.items()],
    }
    content['MANIFEST.json'] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    DIST.mkdir(exist_ok=True)
    target = DIST / (NAME + '.zip')
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in content.items():
            entry = zipfile.ZipInfo(name, date_time=(2026, 10, 31, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = (0o100755 if name.endswith('.sh') else 0o100644) << 16
            archive.writestr(entry, data)
    with tempfile.TemporaryDirectory(prefix='fundtrace-delivery-') as folder:
        base = Path(folder)
        with zipfile.ZipFile(target) as archive:
            assert archive.testzip() is None
            assert set(archive.namelist()) == set(content)
            archive.extractall(base)
        for item in manifest['files']:
            assert digest((base / item['path']).read_bytes()) == item['sha256'], item['path']
        for name in content:
            if name.endswith('.sh'):
                assert b'\r' not in (base / name).read_bytes(), name
            if name.endswith('.py'):
                compile((base / name).read_bytes(), name, 'exec')
        metadata = json.loads((base / 'data/dataset_meta.json').read_text(encoding='utf-8-sig'))
        for name, expected in metadata['sha256'].items():
            assert digest((base / 'data' / name).read_bytes()).lower() == expected.lower()
        assert not (base / 'eval').exists()
    sha = digest(target.read_bytes())
    (DIST / (NAME + '.sha256')).write_text(f'{sha}  {target.name}\n', encoding='ascii')
    verification = {'archive': target.name, 'sha256': sha, 'files': len(content),
                    'source_commit': manifest['source_commit'], 'source_dirty': manifest['source_dirty'],
                    'extraction_hashes': 'PASS', 'nested_zip_crc_and_v9_hash': 'PASS',
                    'python_compile': 'PASS', 'synthetic_csv_hashes': 'PASS',
                    'shell_lf_endings': 'PASS',
                    'common_credential_patterns': 'NO_MATCH', 'fresh_install_tested': False}
    (DIST / (NAME + '.verification.json')).write_text(json.dumps(verification, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(verification, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
