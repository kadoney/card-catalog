# SAPFM Card Catalog — Controlled Vocabularies

Revised after full Chipstone *American Furniture* run scan (1993–2023).  
All fields store JSON arrays. Multiple values allowed per card.  
Use exact strings as listed. Extend by editing this document — update D1 `vocab_terms` table to match.

---

## Period

| Value | Notes |
|---|---|
| `Early Colonial` | Pre-1690. Joined furniture, Pilgrim Century. |
| `William & Mary` | 1690–1730. Turned ornament, bun feet, japanning. |
| `Baroque / Late Baroque` | 1700–1740. Boston Georgian chairs, early high-style work that sits between W&M and Queen Anne. |
| `Queen Anne` | 1725–1755. Cabriole leg, splat back, pad foot. |
| `Chippendale` | 1750–1790. Ball-and-claw, carved ornament, Rococo. |
| `Federal / Neoclassical` | 1785–1820. Inlay, taper leg, Hepplewhite/Sheraton sources. |
| `Empire` | 1815–1840. Archaeological classicism, heavy forms, Lannuier. |
| `Victorian` | 1840–1900. Revival styles, Reform movement, Eastlake. |
| `Colonial Revival` | 1880–1940. Revival of early American forms; Potthast Brothers, reproduction furniture. |
| `Arts & Crafts` | 1880–1920. Mission, Stickley, Greene & Greene, craft revival. |
| `Shaker` | Distinct community-based tradition; not period-bound but typically 1820–1900. |
| `Modern / Studio` | Post-1920. Studio furniture makers, contemporary craft. Maloof, Bennett, etc. |
| `Survey / Multiple` | Articles spanning multiple periods. |

---

## Form

| Value | Notes |
|---|---|
| `Case pieces` | Chests, chests of drawers, highboys, lowboys, secretaries, bookcases, bureau tables. |
| `Seating` | Chairs, settees, stools, benches — general seating forms. |
| `Easy Chairs / Upholstered Seating` | Easy chairs, wing chairs, sofas — forms where upholstery construction is central. |
| `Windsor` | Windsor chairs and related stick-construction seating. Distinct constructional tradition. |
| `Vernacular` | Non-fashionable, rural, or utilitarian forms across all types. |
| `Tables` | All table forms: dining, card, tea, pembroke, side, work, mixing. |
| `Beds` | Bedsteads, cradles, related sleeping furniture. |
| `Clocks / Tall Case` | Clock cases and related timekeeping furniture cases. |
| `Textiles / Covers` | Protective covers, upholstery fabric, textile furnishings. Baumgarten territory. |
| `Survey / Multiple` | Articles spanning multiple forms. |

---

## Region

| Value | Notes |
|---|---|
| `New England` | Connecticut, Massachusetts, Rhode Island, Vermont, New Hampshire, Maine — broad regional. |
| `Boston` | Boston and immediate surrounds — use when city-specific scholarship. |
| `Newport` | Newport, RI — Townsend-Goddard tradition; use when city-specific. |
| `Rural New England` | Non-urban New England production; country and vernacular work. |
| `New York` | New York State broadly; use for city when not city-specific. |
| `New York City` | Manhattan cabinetmaking specifically — Phyfe, Lannuier, Meier-Hagen. |
| `Philadelphia` | Philadelphia and Delaware Valley — use when city-specific. |
| `Baltimore` | Baltimore as a distinct furniture center; Federal period especially strong. |
| `Mid-Atlantic` | Pennsylvania, Delaware, Maryland broadly (non-Philadelphia, non-Baltimore). |
| `Chesapeake / Virginia` | Tidewater Virginia, Colonial Williamsburg sphere; distinct from broader Southern. |
| `Southern` | Carolinas, Georgia, and other southern states broadly. |
| `Charleston` | Charleston, SC — use when city-specific. |
| `North Carolina` | Distinct regional tradition; MESDA / Bivins scholarship. |
| `Rural / Backcountry` | Non-urban, cross-regional category for vernacular and country production. |
| `National / Survey` | No single regional focus; broad American survey. |
| `European Influence` | Articles primarily about English or continental design sources and their American reception. |

---

## Topic

| Value | Notes |
|---|---|
| `Construction / Technique` | Joinery methods, wood technology, hand tool practice, structural analysis. |
| `Attribution` | Establishing maker identity for specific objects or groups. |
| `Regional Style` | Characteristics distinguishing one center's production from another. |
| `Design Sources` | Pattern books, English precedents, continental influence on American work. |
| `Carving / Ornament` | Surface decoration, carved elements, gilding. |
| `Inlay / Veneer` | Stringing, banding, figured veneers, marquetry — Federal period especially. |
| `Painted / Decorated Surfaces` | Painted furniture, polychrome decoration, japanning, fancy furniture. |
| `Shop Records` | Account books, order books, daybooks, labels, bills of sale. |
| `Conservation` | Technical examination, restoration practice, finish analysis, scientific methods. |
| `Repair / Alteration` | Period and later repairs, structural alterations, identifying non-original elements. |
| `Fakes / Authentication` | Identifying later work sold as period; connoisseurship methodology around authentication. |
| `Materials` | Wood species, secondary woods, hardware, upholstery materials, finish chemistry. |
| `Terminology / Nomenclature` | Period trade terms, form names, part names — Evans Windsor territory. |
| `Social History` | Patronage, domestic life, gender, race, use of furniture in its original context. |
| `Trade / Commerce` | Furniture trade, export, retail, market geography, pricing. |
| `Immigration` | Immigrant craftsmen and their influence on American regional work. |
| `Biography / Shops` | Individual craftsman or shop histories; firm records. |
| `Connoisseurship` | Methodology of attribution and quality assessment. |
| `Historiography` | History of the field itself; who gets studied and why; canon formation. |
| `Shaker / Religious Communities` | Furniture and material culture of intentional communities. |
| `Studio / Contemporary` | Post-1920 studio furniture makers and contemporary craft practice. |

---

## Source Keys

Used in `source_key` field for machine filtering. Extend as corpus grows.

| Value | Description |
|---|---|
| `chipstone` | Chipstone Foundation — *American Furniture* journal |
| `met` | Metropolitan Museum of Art — MetPublications |
| `winterthur` | Winterthur Museum — publications and trade catalogs |
| `mesda` | Museum of Early Southern Decorative Arts journal |
| `pma` | Philadelphia Museum of Art |
| `cleveland` | Cleveland Museum of Art |
| `internet_archive` | Public domain books via Internet Archive |
| `member` | Member-contributed card |

---

## Card Types

| Value | When to use |
|---|---|
| `article` | Journal article (Chipstone, MESDA) — standalone unit of scholarship |
| `chapter` | Chapter or section within a book |
| `book` | Parent record for a book; chapters link via `parent_id` |
| `catalog` | Trade catalog, exhibition checklist, or similar document-as-unit |

---

*Last revised: April 2026 — after full Chipstone TOC scan 1993–2023.*  
*Extend vocabulary by PR to this file; update `vocab_terms` D1 table to match.*
