import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { validateSpec, plannedOutputs, renderSpec, toNativeText } from '../scripts/render_from_spec.mjs';

const tmp = await fs.mkdtemp(path.join(os.tmpdir(), 'image-style-pptx-test-'));
const previousEntry = process.env.ARTIFACT_TOOL_ENTRY;
// A preflight failure must happen before loading an authoring runtime.
process.env.ARTIFACT_TOOL_ENTRY = '/nonexistent-test-artifact-entry.mjs';
try {
  const spec = { width: 100, height: 60, slides: [{ elements: [{ type: 'text', name: 'body', x: 0, y: 0, w: 100, h: 30, text: '正文' }] }] };
  assert.doesNotThrow(() => validateSpec(spec));
  const paragraphSpec={...spec,slides:[{elements:[{...spec.slides[0].elements[0],text:undefined,paragraphs:[{text:'第一段'},{runs:[{text:'150G',color:'#C52C36',bold:true}]}]}]}]};
  assert.doesNotThrow(()=>validateSpec(paragraphSpec));
  const native=toNativeText(paragraphSpec.slides[0].elements[0],'Noto Sans CJK SC');
  assert.equal(native.length,2);
  assert.equal(native[0].runs[0].run,'第一段');
  assert.equal(native[1].runs[0].style.color,'#C52C36');
  assert.equal(native[1].runs[0].style.bold,true);
  assert.equal(native[1].spaceAfter,0);
  assert.throws(()=>validateSpec({...spec,slides:[{elements:[{...spec.slides[0].elements[0],paragraphs:['冲突']}]}]}),/Exactly one/);
  assert.throws(()=>validateSpec({...spec,slides:[{elements:[{type:'table',name:'bad-cell',x:0,y:0,w:100,h:60,values:[[{fill:'#FFFFFF'}]]}]}]}),/Exactly one/);
  assert.throws(() => validateSpec({ ...spec, slides: [{ elements: [{ ...spec.slides[0].elements[0], x: 90 }] }] }), /outside slide/);
  assert.throws(() => plannedOutputs(spec, { out: path.join(tmp, 'same.pptx'), layout: path.join(tmp, 'same.pptx') }), /collide/);
  assert.throws(() => plannedOutputs(spec, { out: path.join(tmp, 'draft.pptx'), preview: path.join(tmp, 'bad.jpg') }), /end in .png/);
  const specPath = path.join(tmp, 'spec.json');
  const draft = path.join(tmp, 'draft.pptx');
  const preview = path.join(tmp, 'preview.png');
  await fs.writeFile(specPath, JSON.stringify(spec));
  await fs.writeFile(preview, 'preserve-existing');
  await assert.rejects(() => renderSpec(specPath, { out: draft, preview }), /Refusing to overwrite/);
  assert.equal(await fs.readFile(preview, 'utf8'), 'preserve-existing');
  await assert.rejects(() => fs.access(draft), { code: 'ENOENT' });
  const imageSpec = { ...spec, slides: [{ elements: [{ type: 'image', name: 'evidence', x: 0, y: 0, w: 20, h: 20, path: 'missing.png' }] }] };
  await fs.writeFile(specPath, JSON.stringify(imageSpec));
  await assert.rejects(() => renderSpec(specPath, { out: draft }), { code: 'ENOENT' });
  await assert.rejects(() => fs.access(draft), { code: 'ENOENT' });
  const multi = { ...spec, slides: [spec.slides[0], spec.slides[0]] };
  assert.deepEqual(plannedOutputs(multi, { out: '/task/deck.pptx', preview: '/task/slide.png' }).previews, ['/task/slide-01.png', '/task/slide-02.png']);
  console.log('Preflight regressions passed: rich paragraphs, ambiguous/empty content rejection, bounds, collision, preview extension, existing-output preservation, missing assets, multi-slide naming.');
} finally {
  if (previousEntry === undefined) delete process.env.ARTIFACT_TOOL_ENTRY;
  else process.env.ARTIFACT_TOOL_ENTRY = previousEntry;
  await fs.rm(tmp, { recursive: true, force: true });
}
