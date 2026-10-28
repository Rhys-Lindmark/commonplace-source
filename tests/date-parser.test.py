import importlib.util,json,unittest
from pathlib import Path
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('audit_dates',root/'scripts/audit_dates.py');d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
refs=json.loads((root/'work/date-audit/reference-dates.json').read_text())
class Dates(unittest.TestCase):
 def quote(self,author,source,**extra):return dict(author=author,source=source,sourceUrl='https://example.com/source',year=None,**extra)
 def test_eras_ranges_centuries(self):
  for value,start,end in [('c. 700 BC',-700,-700),('23rd century BCE',-2300,-2201),('c. AD 121–180',121,180),('80–104 AD',80,104),('1940–41',1940,1941),('1880s',1880,1889),('15 May 1996',1996,1996),('June 3, 1998',1998,1998)]:
   with self.subTest(value=value):
    got=d.parse_expression(value);self.assertIsNotNone(got);self.assertEqual((got['startYear'],got['endYear']),(start,end))
 def test_no_false_dates(self):
  for value in ['0','365','2030','before 1900','2000s','B.C. Koekkoek','Early India: origins to AD 1300','born in 300 BC','2nd ed. 1901']:
   self.assertIsNone(d.parse_expression(value),value)
 def test_title_subject_not_work_date(self):
  q=self.quote('Lucio Russo','The Forgotten Revolution: How Science Was Born in 300 BC and Why It Had to Be Reborn (2004)')
  self.assertEqual(d.classify(q,refs)['startYear'],2004)
 def test_source_date_typed(self):
  c=d.classify(self.quote('A Writer','A Novel (1980)'),refs);self.assertEqual(c['kind'],'source-context');self.assertFalse(c['reviewed'])
 def test_conflict_and_edition_stay_unknown(self):
  for source in ['Collected Works (1883)','Dictionary of Quotations (1950)','A Work (1900); Another Work (1950)']:
   q=self.quote('A Writer',source,provenance={'descriptions':source.split('; ')})
   self.assertEqual(d.classify(q,refs)['kind'],'unknown')
 def test_no_lifetime_snapshot_or_quote_text_inference(self):
  q=self.quote('Aristotle','Quotable community collection',text='Words from 350 BC',provenance={'retrievedAt':'2026-10-25','snapshotDate':'2023-07-01'})
  self.assertEqual(d.classify(q,refs)['kind'],'unknown')
 def test_curated_corrections(self):
  for author,source,start,end in [('Hesiod','Works and Days (c. 700 BC)',-700,-700),('Marcus Aurelius','Meditations (c. AD 121–180)',171,175),('Ptahhotep','The Maxims of Ptahhotep (c. 2350 BC)',-2000,-1800),('Edmund Clerihew Bentley',"Trent's Last Case (1912)",1913,1913)]:
   c=d.classify(self.quote(author,source),refs);self.assertEqual((c['startYear'],c['endYear']),(start,end));self.assertTrue(c['reviewed'])
 def test_speaker_and_work_author(self):
  c=d.classify(self.quote('Socrates','Phaedo; Plato',provenance={'descriptions':['Phaedo','Plato']}),refs);self.assertEqual(c['kind'],'work');self.assertLess(c['startYear'],-300);self.assertTrue(c['approximate'])
 def test_modern_compilations_blocked(self):
  for author,source in [('Leonardo da Vinci','The Notebooks of Leonardo da Vinci (1883)'),('Epictetus','Golden Sayings of Epictetus')]:
   self.assertEqual(d.classify(self.quote(author,source),refs)['kind'],'unknown')
 def test_citation_title_not_mapping(self):
  q=self.quote('Plato','A community collection',provenance={'citations':['A comparison with the Republic']});self.assertEqual(d.classify(q,refs)['kind'],'unknown')
if __name__=='__main__':unittest.main()
