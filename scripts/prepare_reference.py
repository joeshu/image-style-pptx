#!/usr/bin/env python3
"""Deterministic document preprocessing: perspective rectification and asset crops.

Does not generate, repaint or infer missing content. Requires Pillow and NumPy.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps


def perspective_coefficients(quad, width, height):
    q = np.asarray(quad, dtype=float).reshape(4, 2)
    if not np.isfinite(q).all() or width <= 0 or height <= 0:
        raise ValueError('Coordinates must be finite and dimensions positive')
    edges = np.roll(q, -1, axis=0) - q
    next_edges = np.roll(edges, -1, axis=0)
    cross = edges[:, 0] * next_edges[:, 1] - edges[:, 1] * next_edges[:, 0]
    if not (np.all(cross > 0) or np.all(cross < 0)):
        raise ValueError('Quad must be convex and ordered TL,TR,BR,BL')
    area = abs(np.dot(q[:, 0], np.roll(q[:, 1], -1)) - np.dot(q[:, 1], np.roll(q[:, 0], -1))) / 2
    if area < 16:
        raise ValueError('Quad is too small or degenerate')
    target = [(0, 0), (width, 0), (width, height), (0, height)]
    a, b = [], []
    for (x, y), (u, v) in zip(target, q):
        a.extend([[x, y, 1, 0, 0, 0, -u*x, -u*y], [0, 0, 0, x, y, 1, -v*x, -v*y]])
        b.extend([u, v])
    return np.linalg.solve(np.asarray(a), np.asarray(b))


def parse_crop(value, width, height):
    name, coords = value.split('=', 1)
    if not name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in name):
        raise ValueError('Crop names may contain letters, digits, hyphens and underscores')
    box = tuple(int(x) for x in coords.split(','))
    if len(box) != 4 or not (0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height):
        raise ValueError(f'Crop outside rectified canvas: {value}')
    return name, box


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--quad', nargs=8, type=float, help='TLx TLy TRx TRy BRx BRy BLx BLy in EXIF-oriented source pixels')
    ap.add_argument('--width', type=int)
    ap.add_argument('--height', type=int)
    ap.add_argument('--crop', action='append', default=[], help='name=left,top,right,bottom in output pixels')
    ap.add_argument('--asset-dir', type=Path)
    ap.add_argument('--geometry-note', default='', help='Record inferred corners, aspect ratio or excluded UI')
    args = ap.parse_args()
    with Image.open(args.input) as raw:
        im = ImageOps.exif_transpose(raw).convert('RGB')
    source_size = im.size
    width, height = args.width or im.width, args.height or im.height
    if width <= 0 or height <= 0 or width * height > 30_000_000:
        raise ValueError('Output dimensions must be positive and at most 30 megapixels')
    quad = np.asarray(args.quad, dtype=float).reshape(4, 2).tolist() if args.quad else None
    coeff = perspective_coefficients(quad, width, height) if quad else None
    crops = [parse_crop(x, width, height) for x in args.crop]
    if len({n for n, _ in crops}) != len(crops):
        raise ValueError('Duplicate crop name')
    asset_dir = args.asset_dir or args.out.parent
    manifest_path = args.out.with_suffix('.geometry.json')
    paths = [args.out, manifest_path] + [asset_dir / (name + '.png') for name, _ in crops]
    if len({p.resolve() for p in paths}) != len(paths):
        raise ValueError('Output paths collide')
    for p in paths:
        if p.exists() or p.resolve() == args.input.resolve():
            raise FileExistsError(f'Refusing to overwrite {p}')
    if coeff is not None:
        im = im.transform((width, height), Image.Transform.PERSPECTIVE, coeff,
                          Image.Resampling.BICUBIC, fillcolor='white')
    elif im.size != (width, height):
        raise ValueError('Size changes require --quad; do not distort the reference')
    for p in paths:
        p.parent.mkdir(parents=True, exist_ok=True)
    im.save(args.out, format='PNG')
    crop_info = []
    for name, box in crops:
        p = asset_dir / (name + '.png')
        im.crop(box).save(p, format='PNG')
        crop_info.append({'name': name, 'box': box, 'path': str(p.resolve()), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})
    manifest = {'source': str(args.input.resolve()), 'sourceSha256': hashlib.sha256(args.input.read_bytes()).hexdigest(),
                'sourceSizeAfterExif': source_size, 'targetSize': [width, height], 'quadTL_TR_BR_BL': quad,
                'operation': 'perspective-and-crop' if quad else 'crop-only',
                'geometryNote': args.geometry_note, 'generatedContent': False, 'assets': crop_info}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'reference': str(args.out), 'manifest': str(manifest_path), 'assetCount': len(crops)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
