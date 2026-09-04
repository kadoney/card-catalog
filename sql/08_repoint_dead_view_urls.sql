-- =============================================================================
-- 08 -- Repoint "Read Article" off dead hosts onto the copies we hold
--       (2026-09-04)
--
-- Every card_type='manual' card, plus Der Stuhlmacher and the Modern American
-- Period Furniture set, sent "Read Article" to a URL that 404s -- while the
-- "Download PDF" button beside it, pointing at our own R2 copy, worked. 29
-- cards, all member-visible, all approved.
--
-- Two distinct causes, one shape:
--
--   A. 15 cards pointed at legacy Joomla paths on sapfm.org --
--      /assets/ManualsAndPublications/*.pdf and /der-stuhlmacher/537-the-
--      chairmaker. Those died when Joomla was retired on 2026-07-04. The PDFs
--      had already been migrated into the `publications` R2 bucket and
--      download_url was already correct; only view_url was left behind. So the
--      whole Tool Manuals shelf has been broken for two months in the one
--      place a member clicks first.
--
--   B. 14 cards pointed at https://books.google.com/books?id=modern-american-
--      period-furniture -- a slug where a Google Books volume id belongs.
--      There is no such volume; the id was invented. Verified 404. We hold the
--      scan ourselves (books/modern-american-period-furniture.pdf, 24.9 MB).
--
-- Fix in both cases: view_url = the copy we actually hold. For the 13 chapter
-- cards that carry a page range, the target gains #page=<page_start>, the same
-- convention the P&T article citations use, so a chapter opens at its chapter.
--
-- Every target verified present in R2 by key before this ran (29/29).
--
-- Not touched: the Met and NGA links, which answer 429/403 to a scripted
-- request. That is bot-blocking, not death -- the 2026-07-04 link-check made
-- the same finding and it was a false positive then too.
-- =============================================================================

-- A. Tool manuals: the R2 copy is already in download_url.
UPDATE library_cards
   SET view_url = download_url,
       updated_at = datetime('now')
 WHERE card_type = 'manual'
   AND view_url LIKE 'https://sapfm.org/assets/ManualsAndPublications/%'
   AND download_url LIKE 'https://publications.sapfm.org/manuals/%';

-- A. Der Stuhlmacher: same shape, different prefix.
UPDATE library_cards
   SET view_url = download_url,
       updated_at = datetime('now')
 WHERE id = 2585
   AND view_url = 'https://www.sapfm.org/der-stuhlmacher/537-the-chairmaker'
   AND download_url = 'https://publications.sapfm.org/books/der-stuhlmacher.pdf';

-- B. Modern American Period Furniture -- the volume card.
UPDATE library_cards
   SET view_url = download_url,
       updated_at = datetime('now')
 WHERE card_type = 'book'
   AND view_url = 'https://books.google.com/books?id=modern-american-period-furniture'
   AND download_url = 'https://publications.sapfm.org/books/modern-american-period-furniture.pdf';

-- B. ...and its chapters, each opening at its own first page.
UPDATE library_cards
   SET view_url = download_url || '#page=' || page_start,
       updated_at = datetime('now')
 WHERE card_type = 'book_chapter'
   AND view_url = 'https://books.google.com/books?id=modern-american-period-furniture'
   AND download_url = 'https://publications.sapfm.org/books/modern-american-period-furniture.pdf'
   AND page_start IS NOT NULL;
