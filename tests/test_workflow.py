import importlib.util
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prep = load('prepare_reference', 'prepare_reference.py')
check = load('check_reconstruction', 'check_reconstruction.py')
layout_text = load('layout_text', 'layout_text.py')


class WorkflowRegression(unittest.TestCase):
    def test_reference_line_breaks_keep_emphasis_and_reject_omission(self):
        segments=[{'text':'送您一张副卡，','bold':True,'color':'#C52C36'},{'text':'免费用一年','bold':True,'color':'#C52C36'},{'text':'。','bold':False,'color':'#000000'}]
        lines=layout_text.split_at_source_lines(segments,['送您一张副','卡，免费用一年。'])
        self.assertEqual(''.join(r['text'] for line in lines for r in line),'送您一张副卡，免费用一年。')
        self.assertTrue(lines[1][0]['bold'])
        self.assertEqual(lines[1][0]['color'],'#C52C36')
        self.assertFalse(lines[1][-1]['bold'])
        with self.assertRaises(ValueError):
            layout_text.split_at_source_lines(segments,['送您一张副卡，','免费一年。'])
    @unittest.skipUnless(Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc').exists(), 'CJK font required')
    def test_chinese_punctuation_and_latin_runs(self):
        segments = [{'text': '数据转化通报：9月21日建立本地通报体系，通报各单位“FTTR目标客群”，保留0.253%完整。', 'bold': False, 'color': '#252525'}]
        lines = layout_text.wrap_segments(segments, 144, 16,
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc', font_index=2)
        values = [''.join(r['text'] for r in line) for line in lines]
        self.assertEqual(''.join(values), segments[0]['text'])
        for value in values:
            self.assertNotIn(value[0], layout_text.CLOSING)
            self.assertNotIn(value[-1], layout_text.OPENING)
        self.assertTrue(any('FTTR' in v for v in values))
        self.assertTrue(any('0.253%' in v for v in values))

    def test_homography_maps_all_corners(self):
        quad = [(12, 20), (210, 10), (220, 130), (2, 140)]
        c = prep.perspective_coefficients(quad, 320, 180)
        for (x, y), (expected_x, expected_y) in zip([(0, 0), (320, 0), (320, 180), (0, 180)], quad):
            divisor = c[6]*x + c[7]*y + 1
            self.assertAlmostEqual((c[0]*x+c[1]*y+c[2])/divisor, expected_x)
            self.assertAlmostEqual((c[3]*x+c[4]*y+c[5])/divisor, expected_y)

    def test_crossed_and_degenerate_quads_rejected(self):
        for q in [[(0, 0), (100, 100), (100, 0), (0, 100)], [(0, 0), (1, 1), (2, 2), (3, 3)]]:
            with self.assertRaises(ValueError): prep.perspective_coefficients(q, 320, 180)

    def test_crop_bounds_and_names_rejected(self):
        for value in ['../bad=0,0,20,20', 'x=-1,0,20,20', 'x=0,0,321,180', 'x=20,0,10,10']:
            with self.assertRaises(ValueError): prep.parse_crop(value, 320, 180)

    def test_valid_crop(self):
        self.assertEqual(prep.parse_crop('evidence-01=10,20,110,80', 320, 180), ('evidence-01', (10, 20, 110, 80)))

    def fixture_report(self, actual, expected, source=None, tokens=None, screenshot=False):
        with tempfile.TemporaryDirectory() as temp:
            pptx = Path(temp) / 'fixture.pptx'
            root = ET.Element('{'+check.NS['p']+'}sld')
            shape = ET.SubElement(root, '{'+check.NS['p']+'}sp')
            text = ET.SubElement(shape, '{'+check.NS['a']+'}t')
            text.text = actual
            if screenshot: ET.SubElement(root, '{'+check.NS['p']+'}pic')
            with ZipFile(pptx, 'w') as z: z.writestr('ppt/slides/slide1.xml', ET.tostring(root))
            elements = [{'type': 'text', 'text': expected}]
            if screenshot: elements.append({'type': 'image', 'name': 'proof', 'sourceRole': 'evidence-screenshot'})
            spec = {'slides': [{'elements': elements, 'sourceText': source or [], 'requiredTokens': tokens or []}]}
            return check.check(spec, pptx)

    def test_exported_missing_text_detected(self):
        report = self.fixture_report('转化749', '转化749户')
        self.assertFalse(report['passed'])

    def test_independent_source_catches_spec_omission(self):
        report = self.fixture_report('转化749', '转化749', source=[{'id': 'metrics', 'text': '转化749户'}])
        self.assertIn('verified-source-text-missing', [f['kind'] for f in report['findings']])

    def test_critical_decimal_not_normalized_away(self):
        report = self.fixture_report('转化率0.253', '转化率0.253', tokens=['0.253%'])
        self.assertFalse(report['passed'])

    def test_linebreaks_allowed_without_changing_content(self):
        self.assertTrue(self.fixture_report('转化\n749 户', '转化749户')['passed'])

    def test_screenshot_scope_is_explicit(self):
        report = self.fixture_report('正文', '正文', screenshot=True)
        self.assertTrue(report['passed'])
        self.assertEqual(report['slides'][0]['rasterScope'][0]['role'], 'evidence-screenshot')
        self.assertFalse(report['slides'][0]['rasterScope'][0]['editableText'])

    def test_number_label_swap_detected_by_owner(self):
        root=ET.Element('{'+check.NS['p']+'}sld')
        elements=[]
        for name,value in [('new-count','47户'),('broadband-count','171户')]:
            sp=ET.SubElement(root,'{'+check.NS['p']+'}sp')
            nv=ET.SubElement(sp,'{'+check.NS['p']+'}nvSpPr')
            ET.SubElement(nv,'{'+check.NS['p']+'}cNvPr',{'name':name})
            ET.SubElement(sp,'{'+check.NS['a']+'}t').text=value
            elements.append({'type':'text','text':value})
        ss={'elements':elements,'requiredTokens':['171户','47户'],
            'nativeTextContracts':[{'name':'new-count','text':'171户'},{'name':'broadband-count','text':'47户'}]}
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'fixture.pptx'
            with ZipFile(p,'w') as z: z.writestr('ppt/slides/slide1.xml',ET.tostring(root))
            report=check.check({'slides':[ss]},p)
        self.assertEqual([f['kind'] for f in report['findings']],['native-text-binding-mismatch']*2)

    def test_emphasis_checked_across_split_runs(self):
        root=ET.Element('{'+check.NS['p']+'}sld')
        sp=ET.SubElement(root,'{'+check.NS['p']+'}sp')
        nv=ET.SubElement(sp,'{'+check.NS['p']+'}nvSpPr')
        ET.SubElement(nv,'{'+check.NS['p']+'}cNvPr',{'name':'benefit'})
        paragraph=ET.SubElement(sp,'{'+check.NS['a']+'}p')
        for value in ['流量有','150G']:
            run=ET.SubElement(paragraph,'{'+check.NS['a']+'}r')
            props=ET.SubElement(run,'{'+check.NS['a']+'}rPr',{'b':'1'})
            fill=ET.SubElement(props,'{'+check.NS['a']+'}solidFill')
            ET.SubElement(fill,'{'+check.NS['a']+'}srgbClr',{'val':'C52C36'})
            ET.SubElement(run,'{'+check.NS['a']+'}t').text=value
        ss={'formatContracts':[{'name':'benefit','text':'流量有150G','color':'#C52C36','bold':True}]}
        self.assertEqual(check.check_contracts(root,ss,1),[])
        ss['formatContracts'][0]['color']='#000000'
        self.assertEqual(check.check_contracts(root,ss,1)[0]['kind'],'emphasis-format-mismatch')

    def test_table_cell_binding_respects_column(self):
        root=ET.Element('{'+check.NS['p']+'}sld')
        table=ET.SubElement(root,'{'+check.NS['a']+'}tbl')
        row=ET.SubElement(table,'{'+check.NS['a']+'}tr')
        for value in ['标签','299元']:
            cell=ET.SubElement(row,'{'+check.NS['a']+'}tc')
            ET.SubElement(cell,'{'+check.NS['a']+'}t').text=value
        ss={'nativeTextContracts':[{'table':1,'row':0,'column':1,'text':'299元'}]}
        self.assertEqual(check.check_contracts(root,ss,1),[])
        ss['nativeTextContracts'][0]['column']=0
        self.assertEqual(check.check_contracts(root,ss,1)[0]['kind'],'native-text-binding-mismatch')


if __name__ == '__main__':
    unittest.main()
