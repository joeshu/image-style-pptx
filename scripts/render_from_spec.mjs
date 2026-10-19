#!/usr/bin/env node
// Native editable slide objects; external icons are embedded as separate SVGs.
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { pathToFileURL } from 'node:url';
import { validateIconConfig, loadIconAsset, DEFAULT_ICON_COLOR } from './icon_assets.mjs';

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 2) {
    const key = argv[i];
    if (!['--spec', '--out', '--preview', '--layout'].includes(key) || !argv[i + 1])
      throw new Error('Usage: render_from_spec.mjs --spec layout.json --out draft.pptx [--preview preview.png] [--layout layout.json]');
    args[key.slice(2)] = path.resolve(argv[i + 1]);
  }
  if (!args.spec || !args.out) throw new Error('--spec and --out are required');
  if (args.out === args.spec) throw new Error('Output must differ from input');
  return args;
}

function requireNumber(value, name, positive = false) {
  if (typeof value !== 'number' || !Number.isFinite(value) || (positive && value <= 0))
    throw new Error(`Invalid ${name}: ${value}`);
}

function validateText(config, name, allowParagraphs = true) {
  const fields = ['text', 'runs', ...(allowParagraphs ? ['paragraphs'] : [])].filter(k => config[k] !== undefined);
  if (fields.length !== 1) throw new Error(`Exactly one of text/runs/paragraphs is required: ${name}`);
  if (fields[0] === 'text' && typeof config.text !== 'string') throw new Error(`Text must be a string: ${name}`);
  if (fields[0] === 'runs') {
    if (!Array.isArray(config.runs) || config.runs.length === 0 || config.runs.some(r => !r || typeof r.text !== 'string')) throw new Error(`Invalid runs: ${name}`);
  }
  if (fields[0] === 'paragraphs') {
    if (!Array.isArray(config.paragraphs) || config.paragraphs.length === 0) throw new Error(`Invalid paragraphs: ${name}`);
    config.paragraphs.forEach((p, i) => validateText(typeof p === 'string' ? { text: p } : p, `${name}.paragraphs[${i}]`, false));
  }
}

export function validateSpec(spec) {
  requireNumber(spec.width, 'width', true);
  requireNumber(spec.height, 'height', true);
  if (!Array.isArray(spec.slides) || spec.slides.length === 0) throw new Error('No slides');
  for (const [i, slide] of spec.slides.entries()) {
    if (!Array.isArray(slide.elements)) throw new Error(`No elements on slide ${i + 1}`);
    const names = new Set();
    const iconGroups = new Map();
    for (const e of slide.elements) {
      if (!e.name || names.has(e.name)) throw new Error(`Missing/duplicate name: ${e.name}`);
      names.add(e.name);
      if (!['shape', 'text', 'image', 'table', 'icon'].includes(e.type)) throw new Error(`Unsupported type: ${e.type}`);
      for (const prop of ['x', 'y', 'w', 'h']) requireNumber(e[prop], `${e.name}.${prop}`, prop === 'w' || prop === 'h');
      if (e.x < -0.01 || e.y < -0.01 || e.x + e.w > spec.width + 0.01 || e.y + e.h > spec.height + 0.01)
        throw new Error(`Element outside slide: ${e.name}`);
      if (e.type === 'text') validateText(e, e.name);
      if (e.type === 'icon') {
        validateIconConfig(e);
        const color = e.color ?? slide.iconColor ?? spec.iconColor ?? DEFAULT_ICON_COLOR;
        if (!/^#[0-9a-f]{6}$/i.test(color)) throw new Error('Icon color must be #RRGGBB');
        if (e.group) {
          const style = JSON.stringify([e.w, e.h, color.toUpperCase()]);
          if (iconGroups.has(e.group) && iconGroups.get(e.group) !== style) throw new Error(`Inconsistent icon size/color in group: ${e.group}`);
          iconGroups.set(e.group, style);
        }
      }
      if (e.type === 'table') {
        if (!Array.isArray(e.values) || !e.values.length || !Array.isArray(e.values[0]) || !e.values[0].length)
          throw new Error(`Invalid table: ${e.name}`);
        const columns = e.values[0].length;
        if (e.values.some(row => !Array.isArray(row) || row.length !== columns)) throw new Error(`Ragged table: ${e.name}`);
        e.values.forEach((row, r) => row.forEach((v, c) => {
          if (v !== null && typeof v === 'object') validateText(v, `${e.name}[${r},${c}]`);
        }));
        for (const [key, total, count] of [['columnWidths', e.w, columns], ['rowHeights', e.h, e.values.length]]) {
          if (e[key]) {
            if (e[key].length !== count) throw new Error(`Invalid ${key}: ${e.name}`);
            e[key].forEach(n => requireNumber(n, key, true));
            if (Math.abs(e[key].reduce((a, b) => a + b, 0) - total) > 0.1) throw new Error(`${key} sum mismatch: ${e.name}`);
          }
        }
      }
    }
  }
}

function runValues(runs, font) {
  return runs.map(r => ({
    run: r.text,
    style: {
      typeface: r.fontFamily ?? font,
      ...(r.bold !== undefined ? { bold: r.bold } : {}),
      ...(r.color ? { color: r.color } : {}),
      ...(r.fontSize ? { fontSize: `${r.fontSize}px` } : {}),
    },
  }));
}

export function toNativeText(config, font) {
  if (config.paragraphs) return config.paragraphs.map(raw => {
    const p = typeof raw === 'string' ? { text: raw } : raw;
    return {
      runs: p.runs ? runValues(p.runs, font) : [{ run: p.text, style: { typeface: font } }],
      spaceBefore: Math.round((p.spaceBeforePt ?? 0) * 100),
      spaceAfter: Math.round((p.spaceAfterPt ?? 0) * 100),
    };
  });
  if (config.runs) return [runValues(config.runs, font)];
  return config.text ?? '';
}

function textStyle(e, font) {
  return {
    typeface: e.fontFamily ?? font,
    fontSize: e.fontSize ?? 16,
    bold: e.bold ?? false,
    color: e.color ?? '#202020',
    alignment: e.align ?? 'left',
    verticalAlignment: e.valign ?? 'middle',
    autoFit: 'none',
    wrap: e.wrap ?? 'none',
    insets: e.insets ?? 0,
    ...(e.lineSpacing !== undefined ? { lineSpacing: e.lineSpacing } : {}),
  };
}

async function assertNew(p) {
  try { await fs.access(p); } catch (error) { if (error.code === 'ENOENT') return; throw error; }
  throw new Error(`Refusing to overwrite: ${p}`);
}

export function plannedOutputs(spec, output) {
  if (!output.out || path.extname(output.out).toLowerCase() !== '.pptx') throw new Error('PPTX output must end in .pptx');
  if (output.preview && path.extname(output.preview).toLowerCase() !== '.png') throw new Error('Preview must end in .png');
  const previews = output.preview ? spec.slides.map((_, i) => spec.slides.length === 1 ? output.preview : output.preview.slice(0, -4) + `-${String(i + 1).padStart(2, '0')}.png`) : [];
  const paths = [output.out, ...previews, ...(output.layout ? [output.layout] : [])].map(p => path.resolve(p));
  if (new Set(paths).size !== paths.length) throw new Error('Output paths collide');
  return { paths, previews };
}

async function commitFiles(files) {
  const written = [];
  try {
    for (const { destination, bytes } of files) {
      await fs.mkdir(path.dirname(destination), { recursive: true });
      await fs.writeFile(destination, bytes, { flag: 'wx' });
      written.push(destination);
    }
  } catch (error) {
    // Remove only files created by this invocation, preserving existing outputs.
    await Promise.allSettled(written.map(p => fs.unlink(p)));
    throw error;
  }
}

export async function renderSpec(specPath, output) {
  const spec = JSON.parse(await fs.readFile(specPath, 'utf8'));
  validateSpec(spec);
  const plan = plannedOutputs(spec, output);
  const imageBytes = new Map();
  const iconSvgs = new Map();
  const inputPaths = new Set([path.resolve(specPath)]);
  for (const slide of spec.slides) for (const e of slide.elements) {
    if (e.type === 'icon') {
      const asset = await loadIconAsset(e.icon, e.color ?? slide.iconColor ?? spec.iconColor ?? DEFAULT_ICON_COLOR);
      inputPaths.add(asset.sourcePath);
      iconSvgs.set(e, asset.svg);
      continue;
    }
    if (e.type !== 'image') continue;
    const p = path.resolve(path.dirname(specPath), e.path);
    if (!['.svg', '.png', '.jpg', '.jpeg'].includes(path.extname(p).toLowerCase())) throw new Error(`Unsupported image: ${p}`);
    inputPaths.add(p);
    imageBytes.set(p, await fs.readFile(p));
  }
  for (const p of plan.paths) {
    if (inputPaths.has(p)) throw new Error(`Output collides with source: ${p}`);
    await assertNew(p);
  }
  const moduleRoot = process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES;
  const moduleEntry = process.env.ARTIFACT_TOOL_ENTRY ?? (moduleRoot ? path.join(moduleRoot, '@oai/artifact-tool/dist/artifact_tool.mjs') : undefined);
  let api;
  if (moduleEntry) {
    // Resolve the package's documented export if its file layout differs.
    const pkgPath = moduleRoot ? path.join(moduleRoot, '@oai/artifact-tool/package.json') : undefined;
    let entry = moduleEntry;
    if (!process.env.ARTIFACT_TOOL_ENTRY && pkgPath) {
      const pkg = JSON.parse(await fs.readFile(pkgPath, 'utf8'));
      const exported = pkg.exports?.['.'];
      const relative = typeof exported === 'string' ? exported : exported?.import ?? exported?.default ?? pkg.module ?? pkg.main;
      if (typeof relative === 'string') entry = path.resolve(path.dirname(pkgPath), relative);
    }
    api = await import(pathToFileURL(entry).href);
  } else {
    api = await import('@oai/artifact-tool');
  }
  const { Presentation, PresentationFile } = api;
  const font = spec.fontFamily ?? 'Noto Sans CJK SC';
  const presentation = Presentation.create({ slideSize: { width: spec.width, height: spec.height } });
  for (const slideSpec of spec.slides) {
    const slide = presentation.slides.add();
    slide.background.fill = slideSpec.background ?? '#FFFFFF';
    if (slideSpec.notes) slide.speakerNotes.text = slideSpec.notes;
    for (const e of slideSpec.elements) {
      const position = { left: e.x, top: e.y, width: e.w, height: e.h };
      const line = { style: 'solid', fill: e.stroke ?? 'none', width: e.strokeWidth ?? 0 };
      if (e.type === 'shape') {
        slide.shapes.add({ geometry: e.geometry ?? 'rect', name: e.name, position, fill: e.fill ?? 'none', line, ...(e.radius ? { borderRadius: e.radius } : {}) });
      } else if (e.type === 'text') {
        const shape = slide.shapes.add({ geometry: 'textbox', name: e.name, position, fill: 'none', line: { style: 'solid', fill: 'none', width: 0 } });
        shape.text.style = textStyle(e, font);
        shape.text = toNativeText(e, e.fontFamily ?? font);
      } else if (e.type === 'icon') {
        slide.images.add({ svg: iconSvgs.get(e), alt: e.alt ?? `统一矢量图标：${e.icon}`, fit: 'contain', position });
      } else if (e.type === 'image') {
        const imagePath = path.resolve(path.dirname(specPath), e.path);
        const bytes = imageBytes.get(imagePath);
        const ext = path.extname(imagePath).toLowerCase();
        const contentType = { '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg' }[ext];
        if (!contentType) throw new Error(`Unsupported image: ${imagePath}`);
        slide.images.add({ blob: bytes, contentType, alt: e.alt ?? e.name, fit: e.fit ?? 'contain', position });
      } else {
        const values = e.values.map(row => row.map(v => typeof v === 'object' && v !== null ? toNativeText(v, v.fontFamily ?? e.fontFamily ?? font) : String(v)));
        const table = slide.tables.add({ rows: values.length, columns: values[0].length, left: e.x, top: e.y, width: e.w, height: e.h, columnWidths: e.columnWidths, values });
        table.styleOptions = { headerRow: false, totalRow: false, firstColumn: false, lastColumn: false, bandedRows: false, bandedColumns: false };
        const border = { style: 'solid', fill: e.stroke ?? '#EEDBC1', width: e.strokeWidth ?? 0.6 };
        table.borders.assign({ outside: border, inside: border });
        table.cells.block({ row: 0, column: 0, rowCount: values.length, columnCount: values[0].length }).assign({
          margins: e.cellMargins ?? { left: 2, right: 2, top: 0, bottom: 0 },
          anchor: 'middle',
        });
        if (e.rowHeights) e.rowHeights.forEach((height, i) => { table.rows[i].height = height; });
        for (let r = 0; r < values.length; r++) {
          for (let c = 0; c < values[0].length; c++) {
            const cell = table.getCell(r, c);
            const raw = e.values[r][c];
            const config = typeof raw === 'object' && raw !== null ? raw : {};
            table.cells.block({ row: r, column: c, rowCount: 1, columnCount: 1 }).borders = { outside: border };
            cell.fill = config.fill ?? e.rowFills?.[r] ?? e.fill ?? '#FFFFFF';
            const valign = config.valign ?? e.valign ?? 'middle';
            table.cells.block({ row: r, column: c, rowCount: 1, columnCount: 1 }).assign({
              margins: config.cellMargins ?? e.cellMargins ?? { left: 2, right: 2, top: 0, bottom: 0 },
              anchor: valign,
            });
            cell.text.style = textStyle({ ...e, ...config, align: config.align ?? e.align ?? 'center', valign, wrap: config.wrap ?? e.wrap ?? 'none', insets: 0 }, font);
            if (config.runs || config.paragraphs) cell.value = toNativeText(config, config.fontFamily ?? e.fontFamily ?? font);
          }
        }
      }
    }
  }
  const files = [];
  if (output.preview) {
    for (const [i, slide] of presentation.slides.items.entries()) {
      const png = await presentation.export({ slide, format: 'png', scale: 1.5 });
      files.push({ destination: plan.previews[i], bytes: new Uint8Array(await png.arrayBuffer()) });
    }
  }
  if (output.layout) {
    const layouts = [];
    for (const slide of presentation.slides.items) layouts.push(JSON.parse(await (await slide.export({ format: 'layout' })).text()));
    files.push({ destination: output.layout, bytes: JSON.stringify(layouts, null, 2) });
  }
  const staging = await fs.mkdtemp(path.join(os.tmpdir(), 'image-style-pptx-'));
  try {
    const stagedDeck = path.join(staging, 'draft.pptx');
    await (await PresentationFile.exportPptx(presentation)).save(stagedDeck);
    files.unshift({ destination: output.out, bytes: await fs.readFile(stagedDeck) });
    await commitFiles(files);
  } finally {
    await fs.rm(staging, { recursive: true, force: true });
  }
  return { presentation, PresentationFile, spec };
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  try {
    const args = parseArgs(process.argv.slice(2));
    const { spec } = await renderSpec(args.spec, args);
    console.log(JSON.stringify({ draft: args.out, slideCount: spec.slides.length, width: spec.width, height: spec.height }));
  } catch (error) {
    console.error(error.stack ?? error.message);
    process.exitCode = 1;
  }
}
