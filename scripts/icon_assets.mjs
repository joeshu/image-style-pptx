import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';

const directory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../assets/icons');
export const DEFAULT_ICON_COLOR = '#0B5BD3';

export function validateIconConfig(e) {
  if (typeof e.icon !== 'string' || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(e.icon)) throw new Error(`Invalid icon key: ${e.icon}`);
  if (Math.abs(e.w - e.h) > 0.01) throw new Error(`Icon slot must be square: ${e.name}`);
  if (e.color !== undefined && !/^#[0-9a-f]{6}$/i.test(e.color)) throw new Error(`Icon color must be #RRGGBB: ${e.name}`);
  for (const key of ['path', 'svg', 'fill', 'stroke', 'strokeWidth']) {
    if (e[key] !== undefined) throw new Error(`Unified icons do not accept ${key}: ${e.name}`);
  }
}

export async function loadIconAsset(key, color = DEFAULT_ICON_COLOR) {
  if (!/^#[0-9a-f]{6}$/i.test(color)) throw new Error('Icon color must be #RRGGBB');
  const catalog = JSON.parse(await fs.readFile(path.join(directory, 'catalog.json'), 'utf8'));
  if (!Object.hasOwn(catalog.icons, key)) throw new Error(`Unknown unified icon: ${key}`);
  const entry = catalog.icons[key];
  if (!/^[a-z0-9-]+\.svg$/.test(entry.file)) throw new Error('Invalid catalogue file');
  const sourcePath = path.join(directory, entry.file);
  const raw = await fs.readFile(sourcePath, 'utf8');
  if (createHash('sha256').update(raw).digest('hex') !== entry.sha256) throw new Error(`Icon checksum mismatch: ${key}`);
  if (!raw.includes('viewBox="0 0 24 24"') || !raw.includes('stroke-width="2"') || !raw.includes('fill="none"')) throw new Error(`Noncanonical icon: ${key}`);
  return { sourcePath, svg: raw.replace(/stroke="#[0-9a-f]{6}"/i, `stroke="${color.toUpperCase()}"`) };
}
