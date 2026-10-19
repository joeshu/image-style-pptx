#!/usr/bin/env python3
"""Compare verified source/spec text with native PPTX text; report raster scope.

This is a content/editability check, not a visual or PowerPoint execution test.
"""
import argparse
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

NS = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'p': 'http://schemas.openxmlformats.org/presentationml/2006/main'}


def normalize(s):
    return re.sub(r'\s+', '', str(s))


def content_text(value):
    if isinstance(value, dict):
        if 'runs' in value:
            return ''.join(x.get('text', '') for x in value['runs'])
        if 'paragraphs' in value:
            return ''.join(content_text(x) for x in value['paragraphs'])
        return str(value.get('text', ''))
    return str(value)


def resolve_owner(root, contract):
    if 'name' in contract:
        for shape in root.findall('.//p:sp', NS):
            props = shape.find('p:nvSpPr/p:cNvPr', NS)
            if props is not None and props.get('name') == contract['name']:
                return shape
        return None
    if 'table' in contract:
        try:
            table = root.findall('.//a:tbl', NS)[int(contract['table']) - 1]
            return table.findall('a:tr', NS)[int(contract['row'])].findall('a:tc', NS)[int(contract['column'])]
        except (IndexError, KeyError, ValueError):
            return None
    return None


def owner_text(owner):
    return ''.join(t.text or '' for t in owner.findall('.//a:t', NS))


def run_characters(owner):
    """Return whitespace-normalized text and explicit RGB/bold per character."""
    text, styles = [], []
    for paragraph in owner.findall('.//a:p', NS):
        default = paragraph.find('a:pPr/a:defRPr', NS)
        for run in paragraph.findall('a:r', NS):
            props = run.find('a:rPr', NS)
            color, bold = None, None
            for source in [default, props]:
                if source is None: continue
                rgb = source.find('a:solidFill/a:srgbClr', NS)
                if rgb is not None: color = rgb.get('val', '').upper()
                if source.get('b') is not None: bold = source.get('b') in ['1', 'true']
            for value in run.findall('a:t', NS):
                for char in value.text or '':
                    if char.isspace(): continue
                    text.append(char); styles.append({'color': color, 'bold': bold})
    return ''.join(text), styles


def check_contracts(root, ss, slide):
    findings = []
    for contract in ss.get('nativeTextContracts', []):
        owner = resolve_owner(root, contract)
        if owner is None:
            findings.append({'slide': slide, 'kind': 'native-text-owner-missing', 'contract': contract})
            continue
        actual = normalize(owner_text(owner))
        if ('text' in contract and normalize(contract['text']) != actual) or ('contains' in contract and normalize(contract['contains']) not in actual):
            findings.append({'slide': slide, 'kind': 'native-text-binding-mismatch', 'contract': contract})
    for contract in ss.get('formatContracts', []):
        owner = resolve_owner(root, contract)
        if owner is None:
            findings.append({'slide': slide, 'kind': 'format-owner-missing', 'contract': contract})
            continue
        actual, styles = run_characters(owner)
        needle = normalize(contract['text'])
        starts = [m.start() for m in re.finditer(re.escape(needle), actual)] if needle else []
        def matches(start):
            for style in styles[start:start+len(needle)]:
                if 'color' in contract and style['color'] != contract['color'].lstrip('#').upper(): return False
                if 'bold' in contract and style['bold'] != contract['bold']: return False
            return True
        if not any(matches(start) for start in starts):
            findings.append({'slide': slide, 'kind': 'emphasis-format-mismatch', 'contract': contract})
    return findings


def check(spec, pptx_path):
    findings, reports, warnings = [], [], []
    with ZipFile(pptx_path) as z:
        slides = sorted((n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml', n)),
                        key=lambda n: int(re.search(r'(\d+)\.xml$', n).group(1)))
        if len(slides) != len(spec['slides']):
            findings.append({'kind': 'slide-count', 'expected': len(spec['slides']), 'actual': len(slides)})
        for i, (ss, name) in enumerate(zip(spec['slides'], slides), start=1):
            root = ET.fromstring(z.read(name))
            actual = ''.join(t.text or '' for t in root.findall('.//a:t', NS))
            expected, tables, images, raster_scope = [], 0, 0, []
            for e in ss['elements']:
                if e['type'] == 'text':
                    expected.append(content_text(e))
                elif e['type'] == 'table':
                    tables += 1
                    expected.extend(content_text(v) for row in e['values'] for v in row)
                elif e['type'] == 'image':
                    images += 1
                    raster_scope.append({'name': e['name'], 'role': e.get('sourceRole', 'unspecified'), 'editableText': False})
            if normalize(''.join(expected)) != normalize(actual):
                findings.append({'slide': i, 'kind': 'spec-native-text-mismatch'})
            for token in ss.get('requiredTokens', []):
                if normalize(token) not in normalize(actual):
                    findings.append({'slide': i, 'kind': 'required-token-missing', 'token': token})
            for block in ss.get('sourceText', []):
                text = block['text'] if isinstance(block, dict) else block
                if normalize(text) not in normalize(actual):
                    findings.append({'slide': i, 'kind': 'verified-source-text-missing',
                                     'block': block.get('id') if isinstance(block, dict) else text[:30]})
            findings.extend(check_contracts(root, ss, i))
            uncertainties = ss.get('uncertainties', [])
            warnings.extend({'slide': i, 'kind': 'source-uncertainty', **u} for u in uncertainties)
            counts = {'tables': len(root.findall('.//a:tbl', NS)), 'images': len(root.findall('.//p:pic', NS)),
                      'shapes': len(root.findall('.//p:sp', NS))}
            if counts['tables'] != tables or counts['images'] != images:
                findings.append({'slide': i, 'kind': 'native-object-count-mismatch', 'expectedTables': tables,
                                 'expectedImages': images, 'actual': counts})
            reports.append({'slide': i, 'nativeTextCharacters': len(actual), 'objectCounts': counts,
                            'rasterScope': raster_scope, 'sourceBlockCount': len(ss.get('sourceText', [])),
                            'nativeTextContractCount': len(ss.get('nativeTextContracts', [])),
                            'formatContractCount': len(ss.get('formatContracts', [])), 'uncertainties': uncertainties})
    return {'passed': not findings, 'findings': findings, 'warnings': warnings, 'slides': reports,
            'claimBoundary': 'Native text coverage, text bindings, explicit RGB/bold contracts and object counts only. Review final renders separately.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--spec', required=True, type=Path)
    p.add_argument('--pptx', required=True, type=Path)
    p.add_argument('--report', type=Path)
    args = p.parse_args()
    report = check(json.loads(args.spec.read_text(encoding='utf8')), args.pptx)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open('x', encoding='utf8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
            f.write('\n')
    print(json.dumps(report, ensure_ascii=False))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
