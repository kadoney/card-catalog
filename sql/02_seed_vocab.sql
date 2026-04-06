-- SAPFM Card Catalog — Migration 02: Seed controlled vocabulary
-- Source: chipstone-vocabulary.md (revised April 2026 after full Chipstone TOC scan)

-- Period
INSERT OR IGNORE INTO vocab_terms (dimension, value, label, notes, sort_order) VALUES
  ('period', 'Early Colonial',        'Early Colonial',        'Pre-1690. Joined furniture, Pilgrim Century.', 10),
  ('period', 'William & Mary',        'William & Mary',        '1690–1730. Turned ornament, bun feet, japanning.', 20),
  ('period', 'Baroque / Late Baroque','Baroque / Late Baroque','1700–1740. Boston Georgian chairs; between W&M and Queen Anne.', 30),
  ('period', 'Queen Anne',            'Queen Anne',            '1725–1755. Cabriole leg, splat back, pad foot.', 40),
  ('period', 'Chippendale',           'Chippendale',           '1750–1790. Ball-and-claw, carved ornament, Rococo.', 50),
  ('period', 'Federal / Neoclassical','Federal / Neoclassical','1785–1820. Inlay, taper leg, Hepplewhite/Sheraton sources.', 60),
  ('period', 'Empire',                'Empire',                '1815–1840. Archaeological classicism, heavy forms, Lannuier.', 70),
  ('period', 'Victorian',             'Victorian',             '1840–1900. Revival styles, Reform movement, Eastlake.', 80),
  ('period', 'Colonial Revival',      'Colonial Revival',      '1880–1940. Revival of early American forms; Potthast, reproductions.', 90),
  ('period', 'Arts & Crafts',         'Arts & Crafts',         '1880–1920. Mission, Stickley, Greene & Greene, craft revival.', 100),
  ('period', 'Shaker',                'Shaker',                'Distinct community tradition; typically 1820–1900.', 110),
  ('period', 'Modern / Studio',       'Modern / Studio',       'Post-1920. Studio furniture makers, contemporary craft.', 120),
  ('period', 'Survey / Multiple',     'Survey / Multiple',     'Articles spanning multiple periods.', 130);

-- Form
INSERT OR IGNORE INTO vocab_terms (dimension, value, label, notes, sort_order) VALUES
  ('form', 'Case pieces',                  'Case pieces',                  'Chests, highboys, lowboys, secretaries, bookcases.', 10),
  ('form', 'Seating',                      'Seating',                      'Chairs, settees, stools, benches — general seating.', 20),
  ('form', 'Easy Chairs / Upholstered Seating', 'Easy Chairs / Upholstered Seating', 'Easy chairs, wing chairs, sofas — upholstery construction central.', 30),
  ('form', 'Windsor',                      'Windsor',                      'Windsor chairs and related stick-construction seating.', 40),
  ('form', 'Vernacular',                   'Vernacular',                   'Non-fashionable, rural, or utilitarian forms.', 50),
  ('form', 'Tables',                       'Tables',                       'All table forms: dining, card, tea, pembroke, side, work.', 60),
  ('form', 'Beds',                         'Beds',                         'Bedsteads, cradles, related sleeping furniture.', 70),
  ('form', 'Clocks / Tall Case',           'Clocks / Tall Case',           'Clock cases and related timekeeping furniture.', 80),
  ('form', 'Textiles / Covers',            'Textiles / Covers',            'Protective covers, upholstery fabric, textile furnishings.', 90),
  ('form', 'Survey / Multiple',            'Survey / Multiple',            'Articles spanning multiple forms.', 100);

-- Region
INSERT OR IGNORE INTO vocab_terms (dimension, value, label, notes, sort_order) VALUES
  ('region', 'New England',          'New England',          'CT, MA, RI, VT, NH, ME — broad regional.', 10),
  ('region', 'Boston',               'Boston',               'Boston and immediate surrounds — city-specific scholarship.', 20),
  ('region', 'Newport',              'Newport',              'Newport, RI — Townsend-Goddard tradition.', 30),
  ('region', 'Rural New England',    'Rural New England',    'Non-urban New England; country and vernacular.', 40),
  ('region', 'New York',             'New York',             'New York State broadly.', 50),
  ('region', 'New York City',        'New York City',        'Manhattan cabinetmaking — Phyfe, Lannuier, Meier-Hagen.', 60),
  ('region', 'Philadelphia',         'Philadelphia',         'Philadelphia and Delaware Valley — city-specific.', 70),
  ('region', 'Baltimore',            'Baltimore',            'Baltimore as distinct furniture center; Federal period.', 80),
  ('region', 'Mid-Atlantic',         'Mid-Atlantic',         'PA, DE, MD broadly (non-Philadelphia, non-Baltimore).', 90),
  ('region', 'Chesapeake / Virginia','Chesapeake / Virginia','Tidewater Virginia, Colonial Williamsburg sphere.', 100),
  ('region', 'Southern',             'Southern',             'Carolinas, Georgia, and other southern states.', 110),
  ('region', 'Charleston',           'Charleston',           'Charleston, SC — city-specific.', 120),
  ('region', 'North Carolina',       'North Carolina',       'Distinct regional tradition; MESDA / Bivins scholarship.', 130),
  ('region', 'Rural / Backcountry',  'Rural / Backcountry',  'Non-urban, cross-regional vernacular and country production.', 140),
  ('region', 'National / Survey',    'National / Survey',    'No single regional focus; broad American survey.', 150),
  ('region', 'European Influence',   'European Influence',   'English or continental design sources and American reception.', 160);

-- Topic
INSERT OR IGNORE INTO vocab_terms (dimension, value, label, notes, sort_order) VALUES
  ('topic', 'Construction / Technique',     'Construction / Technique',     'Joinery methods, wood technology, hand tool practice, structural analysis.', 10),
  ('topic', 'Attribution',                  'Attribution',                  'Establishing maker identity for specific objects or groups.', 20),
  ('topic', 'Regional Style',               'Regional Style',               'Characteristics distinguishing one center from another.', 30),
  ('topic', 'Design Sources',               'Design Sources',               'Pattern books, English precedents, continental influence.', 40),
  ('topic', 'Carving / Ornament',           'Carving / Ornament',           'Surface decoration, carved elements, gilding.', 50),
  ('topic', 'Inlay / Veneer',               'Inlay / Veneer',               'Stringing, banding, figured veneers, marquetry.', 60),
  ('topic', 'Painted / Decorated Surfaces', 'Painted / Decorated Surfaces', 'Painted furniture, polychrome decoration, japanning, fancy furniture.', 70),
  ('topic', 'Shop Records',                 'Shop Records',                 'Account books, order books, daybooks, labels, bills of sale.', 80),
  ('topic', 'Conservation',                 'Conservation',                 'Technical examination, restoration practice, finish analysis.', 90),
  ('topic', 'Repair / Alteration',          'Repair / Alteration',          'Period and later repairs, structural alterations, non-original elements.', 100),
  ('topic', 'Fakes / Authentication',       'Fakes / Authentication',       'Identifying later work sold as period; authentication methodology.', 110),
  ('topic', 'Materials',                    'Materials',                    'Wood species, secondary woods, hardware, upholstery materials.', 120),
  ('topic', 'Terminology / Nomenclature',   'Terminology / Nomenclature',   'Period trade terms, form names, part names — Evans Windsor territory.', 130),
  ('topic', 'Social History',               'Social History',               'Patronage, domestic life, gender, race, use of furniture in context.', 140),
  ('topic', 'Trade / Commerce',             'Trade / Commerce',             'Furniture trade, export, retail, market geography, pricing.', 150),
  ('topic', 'Immigration',                  'Immigration',                  'Immigrant craftsmen and their influence on American regional work.', 160),
  ('topic', 'Biography / Shops',            'Biography / Shops',            'Individual craftsman or shop histories; firm records.', 170),
  ('topic', 'Connoisseurship',              'Connoisseurship',              'Methodology of attribution and quality assessment.', 180),
  ('topic', 'Historiography',               'Historiography',               'History of the field itself; canon formation.', 190),
  ('topic', 'Shaker / Religious Communities','Shaker / Religious Communities','Furniture and material culture of intentional communities.', 200),
  ('topic', 'Studio / Contemporary',        'Studio / Contemporary',        'Post-1920 studio furniture makers and contemporary craft practice.', 210);

-- Source keys
INSERT OR IGNORE INTO vocab_terms (dimension, value, label, notes, sort_order) VALUES
  ('source_key', 'chipstone',        'Chipstone Foundation — American Furniture', 'Annual journal of record for American furniture scholarship.', 10),
  ('source_key', 'met',              'Metropolitan Museum of Art',                'MetPublications — free PDF downloads.', 20),
  ('source_key', 'winterthur',       'Winterthur Museum',                         'Publications and trade catalogs.', 30),
  ('source_key', 'mesda',            'MESDA Journal',                             'Museum of Early Southern Decorative Arts.', 40),
  ('source_key', 'pma',              'Philadelphia Museum of Art',                NULL, 50),
  ('source_key', 'cleveland',        'Cleveland Museum of Art',                   NULL, 60),
  ('source_key', 'internet_archive', 'Internet Archive',                          'Public domain books.', 70),
  ('source_key', 'member',           'Member Contribution',                       'Member-contributed card.', 80);

-- Card types
INSERT OR IGNORE INTO vocab_terms (dimension, value, label, notes, sort_order) VALUES
  ('card_type', 'article', 'Article', 'Journal article (Chipstone, MESDA) — standalone unit of scholarship.', 10),
  ('card_type', 'chapter', 'Chapter', 'Chapter or section within a book.', 20),
  ('card_type', 'book',    'Book',    'Parent record for a book; chapters link via parent_id.', 30),
  ('card_type', 'catalog', 'Catalog', 'Trade catalog, exhibition checklist, or similar document-as-unit.', 40);
