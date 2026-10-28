import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from complete_dates import source_date, citation_dates, estimate, normalize

def author(birth=None,death=None):
    return {'alice':{'facts':[{'timeNumbering':'historical','birth':[f'{birth:+05}-01-01T00:00:00Z'] if birth else [],'death':[f'{death:+05}-01-01T00:00:00Z'] if death else [],'source':'https://www.wikidata.org/wiki/Q1','instance':['http://www.wikidata.org/entity/Q5']}]}}

def quote(citations=None,**extra):
    return {'id':'test-quote','text':'A thought with 1900 in the text.','author':'Alice','year':None,'source':'Wikiquote via QuoteKG','sourceUrl':'https://en.wikiquote.org/wiki/Alice','provenance':{'dataset':'QuoteKG v1.2','citations':citations or []},**extra}

class CompleteDates(unittest.TestCase):
    def test_source_speech(self):
        self.assertEqual(source_date(quote(['Speech (1850)']),{},{},author(1800,1880),{})['startYear'],1850)
    def test_original_event_before_carrier(self):
        q=quote(['Letter, 13 January 1855, quoted in A Biography (2001), p.1993'])
        self.assertEqual(source_date(q,{},{},author(1800,1880),{})['startYear'],1855)
    def test_conducted_not_republished(self):
        q=quote(['Interview conducted by fax in 1993 and published in 2019.'])
        self.assertEqual(source_date(q,{},{},author(1950),{})['startYear'],1993)
    def test_access_date_not_work_date(self):
        values=citation_dates('An Article (2019), accessed January 1, 2020')
        self.assertEqual({v[0]['startYear'] for v in values},{2019})
    def test_modern_carrier_and_lifetime_range_rejected(self):
        for citation in ['As reported by A Biographer (1850)','Quoted from A Dictionary (1850)','Book (1800–1880)','Book (2001)']:
            self.assertIsNone(source_date(quote([citation]),{},{},author(1800,1880),{}),citation)
    def test_text_dates_never_evidence(self):
        self.assertIsNone(source_date(quote(),{},{},author(1800,1880),{}))
    def test_ambiguous_citation(self):
        self.assertIsNone(source_date(quote(['A volume from 1850 or 1860']),{},{},author(1800,1880),{}))
    def test_lifespan_75_percent(self):
        date=estimate(quote(),author(1800,1880),{},1950)
        self.assertEqual(date['startYear'],1860);self.assertEqual(date['kind'],'estimate');self.assertEqual(date['method'],'author-lifespan-75-percent')
    def test_living_cutoff(self):
        date=estimate(quote(),author(2000),{},1950)
        self.assertTrue(2000<=date['startYear']<=2022);self.assertEqual(date['method'],'author-birth-and-observed-lifespan')
    def test_death_activity_and_unresolved(self):
        self.assertEqual(estimate(quote(),author(death=1880),{},1950)['startYear'],1860)
        self.assertEqual(estimate(quote(),{}, {'alice':[1850,1870]},1950)['startYear'],1860)
        fallback=estimate(quote(),{},{},1950);self.assertEqual(fallback['confidence'],'very-low');self.assertEqual(fallback['startYear'],1950)
    def test_bce_and_cross_era_no_year_zero(self):
        self.assertEqual(estimate(quote(),author(-500,-400),{},1950)['startYear'],-425)
        self.assertEqual(estimate(quote(),author(-1,99),{},1950)['startYear'],74)
    def test_author_era_is_still_an_estimate(self):
        refs={'authorEstimates':[{'authorPattern':'^Alice$','year':1855,'basis':'Published author-era research','sourceUrls':['https://example.com/anchor']}]}
        date=estimate(quote(),author(1800,1880),{},1950,refs);self.assertEqual(date['kind'],'estimate');self.assertEqual(date['startYear'],1855);self.assertEqual(date['method'],'reviewed-author-era')
    def test_coarse_dates_preserve_ancient_era(self):
        a=author(-2000,-2094);a['alice']['facts'][0]['birthBounds']=[[-2000,-1901]]
        self.assertEqual(estimate(quote(),a,{},1990)['startYear'],-2114)
        a=author(-50,-100);a['alice']['facts'][0].update(birthBounds=[[-100,-1]],deathBounds=[[-100,-1]])
        self.assertTrue(-100<=estimate(quote(),a,{},1990)['startYear']<=-1)
    def test_unknown_date_is_not_a_range(self):
        a=author(death=1920);a['alice']['facts'][0]['birthBounds']=[[-10000,2026]]
        self.assertEqual(estimate(quote(),a,{},1990)['startYear'],1900)
    def test_implausible_lifespan_keeps_known_death_era(self):
        self.assertEqual(estimate(quote(),author(-3000,1920),{},1990)['startYear'],1900)
    def test_rdf_bce_conversion(self):
        a=author(-499,-399);del a['alice']['facts'][0]['timeNumbering']
        self.assertEqual(estimate(quote(),a,{},1990)['startYear'],-425)
    def test_reviewed_quote_guard(self):
        refs={'quoteMappings':[{'id':'review','quoteIds':['test-quote'],'authorPattern':'^Alice$','textPattern':'^A thought','startYear':1848,'basis':'Attested source','sourceUrls':['https://example.com/primary']}]}
        result=source_date(quote(),{},refs,author(1800,1880),{});self.assertEqual(result['startYear'],1848);self.assertTrue(result['reviewed'])
        self.assertIsNone(source_date(quote(author='Bob'),{},refs,author(1800,1880),{}))

if __name__=='__main__':unittest.main()
