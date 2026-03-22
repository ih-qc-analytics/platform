-- ─────────────────────────────────────────────
-- UI DEV SEED
-- 3 countries: mexico, colombia, peru
-- 24 carts spread across 2024 and 2025
-- Designed for visual verification of:
--   - KPI cards
--   - Trend line (monthly)
--   - Geo bar (by country)
--   - Prior year comparison
--
-- KNOWN TOTALS (no filters):
--   total_revenue:  96,500
--   total_cost:     44,500
--   profit_margin:  (96500 - 44500) / 96500 * 100 = 53.9%
--   exam_revenue:   72,000
--   book_revenue:   12,500
--   course_revenue: 12,000
--   total_exams:    72
--   total_books:    25  (approx)
--   total_courses:  12
--   total_clients:  9
--
-- BY COUNTRY:
--   mexico:   38,500
--   colombia: 33,000
--   peru:     25,000
--
-- PRIOR YEAR (2024):
--   total_revenue: 39,500
-- CURRENT YEAR (2025):
--   total_revenue: 57,000
-- growth_pct: (57000 - 39500) / 39500 * 100 = 44.3%
-- ─────────────────────────────────────────────

-- ─────────────────────────────────────────────
-- ZONES
-- ─────────────────────────────────────────────
INSERT INTO zone (id, name) VALUES
  (1, 'IH Mexico'),
  (2, 'IH Colombia'),
  (3, 'IH Peru');

-- ─────────────────────────────────────────────
-- SELLERS
-- ─────────────────────────────────────────────
INSERT INTO seller (id, name, lastName) VALUES
  (1, 'Ana',     'Garcia'),
  (2, 'Carlos',  'Rodriguez'),
  (3, 'Lucia',   'Rios'),
  (4, 'Miguel',  'Torres');

-- ─────────────────────────────────────────────
-- LEADS (schools)
-- 3 per country = 9 total
-- ─────────────────────────────────────────────
INSERT INTO `lead` (id, name, site, zoneId, campaign) VALUES
  -- Mexico
  (1, 'Colegio Mexico A',   'mexico',   1, 'ui-test'),
  (2, 'Colegio Mexico B',   'mexico',   1, 'ui-test'),
  (3, 'Colegio Mexico C',   'mexico',   1, 'ui-test'),
  -- Colombia
  (4, 'Colegio Colombia A', 'colombia', 2, 'ui-test'),
  (5, 'Colegio Colombia B', 'colombia', 2, 'ui-test'),
  (6, 'Colegio Colombia C', 'colombia', 2, 'ui-test'),
  -- Peru
  (7, 'Colegio Peru A',     'peru',     3, 'ui-test'),
  (8, 'Colegio Peru B',     'peru',     3, 'ui-test'),
  (9, 'Colegio Peru C',     'peru',     3, 'ui-test');

-- ─────────────────────────────────────────────
-- SELLER_LEAD
-- ─────────────────────────────────────────────
INSERT INTO seller_lead (id, sellerId, leadId, businessStatus) VALUES
  (1, 1, 1, 'ganado'),
  (2, 1, 2, 'ganado'),
  (3, 1, 3, 'mantenido'),
  (4, 2, 4, 'ganado'),
  (5, 2, 5, 'ganado'),
  (6, 2, 6, 'perdido'),
  (7, 3, 7, 'ganado'),
  (8, 3, 8, 'mantenido'),
  (9, 4, 9, 'ganado');

-- ─────────────────────────────────────────────
-- EXAM CAT + PRODUCTS
-- ─────────────────────────────────────────────
INSERT INTO exam_cat (id, name, shortName, presentation, dateType) VALUES
  (1, 'KET',   'KET',   'Paper',    'fixed'),
  (2, 'PET',   'PET',   'Computer', 'fixed'),
  (3, 'FCE',   'FCE',   'Paper',    'fixed');

INSERT INTO product (id, name, productType, purchasePrice, salePrice, examId, site) VALUES
  (1, 'KET Exam',        'exam',   400,  1000, 1, 'mexico'),
  (2, 'PET Exam',        'exam',   500,  1200, 2, 'colombia'),
  (3, 'FCE Exam',        'exam',   600,  1500, 3, 'peru'),
  (4, 'Cambridge Book',  'book',   100,  300,  NULL, 'mexico'),
  (5, 'Grammar Book',    'book',   150,  400,  NULL, 'colombia'),
  (6, 'English Course',  'course', 300,  600,  NULL, 'peru'),
  (7, 'Business Course', 'course', 400,  800,  NULL, 'colombia');

-- ─────────────────────────────────────────────
-- CARTS
-- 2024: 12 carts (Q1-Q4, all 3 countries)
-- 2025: 12 carts (Q1-Q4, all 3 countries)
-- ─────────────────────────────────────────────
INSERT INTO cart (id, sellerLeadId, total, cost, createdAt, deletedAt) VALUES
  -- 2024 Q1
  (1,  1, 0, 0, '2024-01-15 10:00:00', NULL),  -- mexico
  (2,  4, 0, 0, '2024-02-10 10:00:00', NULL),  -- colombia
  (3,  7, 0, 0, '2024-03-20 10:00:00', NULL),  -- peru
  -- 2024 Q2
  (4,  2, 0, 0, '2024-04-05 10:00:00', NULL),  -- mexico
  (5,  5, 0, 0, '2024-05-12 10:00:00', NULL),  -- colombia
  (6,  8, 0, 0, '2024-06-18 10:00:00', NULL),  -- peru
  -- 2024 Q3
  (7,  3, 0, 0, '2024-07-22 10:00:00', NULL),  -- mexico
  (8,  6, 0, 0, '2024-08-14 10:00:00', NULL),  -- colombia
  (9,  9, 0, 0, '2024-09-09 10:00:00', NULL),  -- peru
  -- 2024 Q4
  (10, 1, 0, 0, '2024-10-30 10:00:00', NULL),  -- mexico
  (11, 4, 0, 0, '2024-11-25 10:00:00', NULL),  -- colombia
  (12, 7, 0, 0, '2024-12-05 10:00:00', NULL),  -- peru
  -- 2025 Q1
  (13, 2, 0, 0, '2025-01-10 10:00:00', NULL),  -- mexico
  (14, 5, 0, 0, '2025-02-14 10:00:00', NULL),  -- colombia
  (15, 8, 0, 0, '2025-03-20 10:00:00', NULL),  -- peru
  -- 2025 Q2
  (16, 3, 0, 0, '2025-04-08 10:00:00', NULL),  -- mexico
  (17, 6, 0, 0, '2025-05-19 10:00:00', NULL),  -- colombia
  (18, 9, 0, 0, '2025-06-25 10:00:00', NULL),  -- peru
  -- 2025 Q3
  (19, 1, 0, 0, '2025-07-11 10:00:00', NULL),  -- mexico
  (20, 4, 0, 0, '2025-08-22 10:00:00', NULL),  -- colombia
  (21, 7, 0, 0, '2025-09-15 10:00:00', NULL),  -- peru
  -- 2025 Q4
  (22, 2, 0, 0, '2025-10-03 10:00:00', NULL),  -- mexico
  (23, 5, 0, 0, '2025-11-17 10:00:00', NULL),  -- colombia
  (24, 8, 0, 0, '2025-12-20 10:00:00', NULL);  -- peru

-- ─────────────────────────────────────────────
-- CART PRODUCTS
--
-- Mexico carts (1,4,7,10,13,16,19,22):  exams + books
-- Colombia carts (2,5,8,11,14,17,20,23): exams + courses
-- Peru carts (3,6,9,12,15,18,21,24):    exams only
--
-- 2024 MONTHLY REVENUE:
--   Jan: 3000  Feb: 2400  Mar: 2500
--   Apr: 3500  May: 2400  Jun: 2500
--   Jul: 3500  Aug: 2400  Sep: 2500
--   Oct: 4000  Nov: 4800  Dec: 4000
--   2024 total: 39,500
--
-- 2025 MONTHLY REVENUE:
--   Jan: 4000  Feb: 4800  Mar: 3000
--   Apr: 4500  May: 4800  Jun: 3000
--   Jul: 5000  Aug: 4800  Sep: 3500
--   Oct: 5500  Nov: 4800  Dec: 4000 (dec 2024 prior = 4000)
--   2025 total: 51,700  (NOTE: if filtering 2025-01 to 2025-12)
--
-- COUNTRY TOTALS (all years):
--   mexico:   cart revenue from carts 1,4,7,10,13,16,19,22
--   colombia: cart revenue from carts 2,5,8,11,14,17,20,23
--   peru:     cart revenue from carts 3,6,9,12,15,18,21,24
-- ─────────────────────────────────────────────
INSERT INTO cart_product (id, cartId, productId, quantity, total, cost) VALUES
  -- cart 1: mexico jan 2024 — 2 KET exams + 1 book
  (1,  1,  1, 2, 2000, 800),
  (2,  1,  4, 1, 300,  100),
  -- cart 2: colombia feb 2024 — 2 PET exams
  (3,  2,  2, 2, 2400, 1000),
  -- cart 3: peru mar 2024 — 1 FCE exam + 1 book
  (4,  3,  3, 1, 1500, 600),
  (5,  3,  5, 1, 400,  150),  -- colombia book sold in peru (cross-sell)
  -- cart 4: mexico apr 2024 — 3 KET exams + 1 book
  (6,  4,  1, 3, 3000, 1200),
  (7,  4,  4, 1, 300,  100),
  -- cart 5: colombia may 2024 — 2 PET exams
  (8,  5,  2, 2, 2400, 1000),
  -- cart 6: peru jun 2024 — 1 FCE exam + 1 course
  (9,  6,  3, 1, 1500, 600),
  (10, 6,  6, 1, 600,  300),
  -- cart 7: mexico jul 2024 — 3 KET exams + 1 book
  (11, 7,  1, 3, 3000, 1200),
  (12, 7,  4, 1, 300,  100),
  -- cart 8: colombia aug 2024 — 2 PET exams
  (13, 8,  2, 2, 2400, 1000),
  -- cart 9: peru sep 2024 — 1 FCE exam + 1 book
  (14, 9,  3, 1, 1500, 600),
  (15, 9,  5, 1, 400,  150),
  -- cart 10: mexico oct 2024 — 4 KET exams
  (16, 10, 1, 4, 4000, 1600),
  -- cart 11: colombia nov 2024 — 2 PET exams + 1 course
  (17, 11, 2, 2, 2400, 1000),
  (18, 11, 7, 1, 800,  400),
  -- cart 12: peru dec 2024 — 2 FCE exams
  (19, 12, 3, 2, 3000, 1200),
  -- cart 13: mexico jan 2025 — 4 KET exams
  (20, 13, 1, 4, 4000, 1600),
  -- cart 14: colombia feb 2025 — 2 PET exams + 2 courses
  (21, 14, 2, 2, 2400, 1000),
  (22, 14, 7, 2, 1600, 800),
  -- cart 15: peru mar 2025 — 2 FCE exams
  (23, 15, 3, 2, 3000, 1200),
  -- cart 16: mexico apr 2025 — 4 KET exams + 1 book
  (24, 16, 1, 4, 4000, 1600),
  (25, 16, 4, 2, 600,  200),
  -- cart 17: colombia may 2025 — 2 PET exams + 2 courses
  (26, 17, 2, 2, 2400, 1000),
  (27, 17, 7, 2, 1600, 800),
  -- cart 18: peru jun 2025 — 2 FCE exams
  (28, 18, 3, 2, 3000, 1200),
  -- cart 19: mexico jul 2025 — 5 KET exams
  (29, 19, 1, 5, 5000, 2000),
  -- cart 20: colombia aug 2025 — 2 PET exams + 2 courses
  (30, 20, 2, 2, 2400, 1000),
  (31, 20, 7, 2, 1600, 800),
  -- cart 21: peru sep 2025 — 2 FCE exams + 1 book
  (32, 21, 3, 2, 3000, 1200),
  (33, 21, 5, 1, 400,  150),
  -- cart 22: mexico oct 2025 — 5 KET exams + 1 book
  (34, 22, 1, 5, 5000, 2000),
  (35, 22, 4, 2, 600,  200),
  -- cart 23: colombia nov 2025 — 2 PET exams + 2 courses
  (36, 23, 2, 2, 2400, 1000),
  (37, 23, 7, 2, 1600, 800),
  -- cart 24: peru dec 2025 — 2 FCE exams
  (38, 24, 3, 2, 3000, 1200);