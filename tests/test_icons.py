import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('icon_check',ROOT/'scripts/check_reconstruction.py')
checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)


class UnifiedIcons(unittest.TestCase):
    def test_all_catalog_assets_follow_one_vector_style(self):
        folder=ROOT/'assets/icons'
        catalog=json.loads((folder/'catalog.json').read_text())
        self.assertEqual(catalog['family'],'Lucide')
        self.assertEqual(len(catalog['icons']),30)
        self.assertTrue((folder/catalog['license']).is_file())
        for name,entry in catalog['icons'].items():
            with self.subTest(icon=name):
                raw=(folder/entry['file']).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(),entry['sha256'])
                root=ET.fromstring(raw)
                for key,value in {'viewBox':'0 0 24 24','fill':'none','stroke':'#0B5BD3','stroke-width':'2','stroke-linecap':'round','stroke-linejoin':'round'}.items():
                    self.assertEqual(root.get(key),value)
                for child in root.iter():
                    self.assertIn(child.tag.rsplit('}',1)[-1],['svg','path','rect','circle','line','polyline','polygon','ellipse','g'])
                    self.assertFalse(any('href' in k for k in child.attrib))
                    if child is not root:
                        self.assertNotIn('stroke',child.attrib)
                        self.assertNotIn('stroke-width',child.attrib)
                        self.assertIn(child.get('fill'),[None,'none'])

    def test_pptx_requires_svg_reference_for_icon(self):
        root=ET.Element('{'+checker.NS['p']+'}sld')
        picture=ET.SubElement(root,'{'+checker.NS['p']+'}pic')
        deck={'slides':[{'elements':[{'type':'icon','name':'sim','icon':'card-sim'}]}]}
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'fixture.pptx'
            def inspect():
                with ZipFile(p,'w') as z:z.writestr('ppt/slides/slide1.xml',ET.tostring(root))
                return checker.check(deck,p)
            report=inspect()
            self.assertIn('vector-icon-rasterized',[f['kind'] for f in report['findings']])
            ET.SubElement(picture,'{http://schemas.microsoft.com/office/drawing/2016/SVG/main}svgBlip')
            report=inspect()
            self.assertTrue(report['passed'])
            self.assertEqual(len(report['slides'][0]['vectorIcons']),1)
            self.assertEqual(report['slides'][0]['rasterScope'],[])


if __name__=='__main__':unittest.main()
