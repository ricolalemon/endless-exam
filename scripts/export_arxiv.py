#!/usr/bin/env python3
"""Prepare a minimal named-preprint source archive; never upload or publish."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / 'bench/paper'


def without_comments(text):
    return re.sub(r'(?<!\\)%[^\n]*', '', text)


def dependencies(path):
    text = without_comments(path.read_text())
    for match in re.finditer(r'\\(?:input|include)\{([^}]+)\}', text):
        name = match[1]
        if '#' not in name:
            yield Path(name if Path(name).suffix else name + '.tex')
    for match in re.finditer(r'\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}', text):
        if '#' not in match[1]:
            yield Path(match[1])
    for command, extension in [('(?:usepackage|RequirePackage)', '.sty'),
                               ('bibliographystyle', '.bst'), ('bibliography', '.bib')]:
        for match in re.finditer(r'\\' + command + r'(?:\[[^]]*\])?\{([^}]+)\}', text):
            for name in match[1].split(','):
                relative = Path(name.strip() + extension)
                if (PAPER / relative).is_file():
                    yield relative


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'output/arxiv')
    args = parser.parse_args()
    output = args.output.resolve()
    source = output / 'source'
    if source.exists():
        raise FileExistsError(f'Refusing to replace existing source package: {source}')
    source.mkdir(parents=True)
    included = set()
    pending = [Path('main.tex')]
    while pending:
        relative = pending.pop()
        if relative in included:
            continue
        original = PAPER / relative
        if not original.is_file():
            raise FileNotFoundError(f'Missing manuscript dependency: {relative}')
        if not re.fullmatch(r'[A-Za-z0-9_+.,=/\-]+', str(relative)) or '..' in relative.parts:
            raise ValueError(f'Unsupported archive path: {relative}')
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, target)
        included.add(relative)
        if original.suffix in {'.tex', '.sty'}:
            pending.extend(dependencies(original))
    # The arXiv UI detects top-level documents by their documentclass directive.
    # Keep one root main.tex with the preprint switch, instead of the local wrapper.
    main_file = source / 'main.tex'
    main_file.write_text('\\def\\EndlessExamPreprint{1}\n' + main_file.read_text())
    shutil.copy2(PAPER / 'arxiv.bbl', source / 'main.bbl')
    included.add(Path('main.bbl'))
    archive = output / 'endless-exam-arxiv-source.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for relative in sorted(included):
            z.write(source / relative, str(relative))
    manifest = {
        'entrypoint': 'main.tex', 'compiler': 'xelatex', 'recommended_texlive': 2025,
        'file_count': len(included),
        'files': {str(p): hashlib.sha256((source / p).read_bytes()).hexdigest() for p in sorted(included)},
        'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
        'uploaded': False,
    }
    (output / 'source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'archive': str(archive), 'files': len(included),
                      'bytes': archive.stat().st_size, 'entrypoint': 'main.tex',
                      'compiler': 'xelatex'}, indent=2))


if __name__ == '__main__':
    main()
