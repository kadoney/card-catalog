-- =============================================================================
-- 07 -- Remove six MESDA scrape artifacts from library_cards (2026-09-04)
--
-- The 2026-04-08 MESDA journal scrape harvested every <a> under a volume
-- heading. Six of the 79 rows it produced are page furniture, not articles:
-- a Blurb print-on-demand link, its bare "click here.", a second Blurb link,
-- MESDA's craftsman-database link, an archive.org index listing for an
-- unrelated 1992 issue, and the site's Cloudflare-obfuscated contact address.
--
--   704  Print-on-Demand Copy                  http://blur.by/1L3xRwN
--   705  click here.                           http://blur.by/1L3xRwN
--   718  Print-on-Demand Copy                  http://blur.by/1zSp12V
--   725  Craftsman Database at www.mesda.org   http://mesda.org/research/craftsman-database/
--   726  Vol, 18, No. 2 (November 1992)        http://www.archive.org/details/journalofearlyso1821992muse
--   727  [email protected]                      /cdn-cgi/l/email-protection
--
-- None describes an article, and none can be repaired: there is no article
-- behind them to repair toward. Each nevertheless carries an LLM-written
-- `description` inventing a scholarly abstract from the junk title, plus
-- invented period/form/region/topic tags. (The later teaser pass got it right
-- and refused: card 727's teaser reads "too incomplete to support a
-- responsible teaser ... likely a database or formatting error".)
--
-- They are inert TODAY only by coincidence: all 78 MESDA cards are
-- status='hidden' pending the permissions outreach, so these six ride along.
-- The day that permission lands and the set is unhidden in one go, six
-- fabricated abstracts go live. That is why they are deleted now rather than
-- left as known-bad rows.
--
-- Verified before deletion: 0 member saves (sapfm.collection_item), 0 child
-- rows via parent_id, submissions table empty. Not in the Vectorize index --
-- /embed/cards selects status='approved' only, and the restricted-set
-- reconcile purges hidden cards.
--
-- Full pre-delete rows: _backup-mesda-scrape-artifacts-2026-09-04.json
--
-- Root cause fixed in scripts/mesda_website_scraper.py: an article link must
-- point at mesdajournal.org. The previous blocklist ('blurb.com' in href,
-- title starts with 'Vol.') was aimed at exactly this class and each real
-- instance slipped a near miss -- blur.by is Blurb's shortener, and the
-- archive.org row's title reads "Vol," with a comma.
--
-- Deliberately NOT removed: 724 "2012 Editor's Welcome", which points at
-- mesdajournal.org and is a real piece in the issue.
-- =============================================================================

DELETE FROM library_cards
 WHERE source_key = 'mesda'
   AND id IN (704, 705, 718, 725, 726, 727)
   AND view_url IN (
     'http://blur.by/1L3xRwN',
     'http://blur.by/1zSp12V',
     'http://mesda.org/research/craftsman-database/',
     'http://www.archive.org/details/journalofearlyso1821992muse',
     '/cdn-cgi/l/email-protection'
   );
