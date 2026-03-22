-- ─────────────────────────────────────────────
-- ZONES
-- ─────────────────────────────────────────────
INSERT INTO zone (id, name) VALUES
  (1, 'IH Mexico'),
  (2, 'IH Colombia');

-- ─────────────────────────────────────────────
-- SELLERS
-- ─────────────────────────────────────────────
INSERT INTO seller (id, name, lastName) VALUES
  (1, 'Ana',    'Garcia'),      -- mexico seller
  (2, 'Carlos', 'Rodriguez'),   -- colombia seller
  (3, 'Empty',  'Seller');      -- seller with no carts

-- ─────────────────────────────────────────────
-- LEADS (schools)
-- ─────────────────────────────────────────────
INSERT INTO `lead` (id, name, site, zoneId, campaign) VALUES
  (1, 'Colegio Mexico A',    'mexico',   1, 'test'),
  (2, 'Colegio Colombia A',  'colombia', 2, 'test'),
  (3, 'Colegio Mexico B',    'mexico',   1, 'test');  -- second mexico school

-- ─────────────────────────────────────────────
-- SELLER_LEAD
-- all three businessStatus values represented
-- ─────────────────────────────────────────────
INSERT INTO seller_lead (id, sellerId, leadId, businessStatus) VALUES
  (1, 1, 1, 'ganado'),
  (2, 2, 2, 'mantenido'),
  (3, 1, 3, 'perdido');

-- ─────────────────────────────────────────────
-- EXAM CAT + PRODUCTS
-- ─────────────────────────────────────────────
INSERT INTO exam_cat (id, name, shortName, presentation, dateType) VALUES
  (1, 'KET', 'KET', 'Paper', 'fixed');

INSERT INTO product (id, name, productType, purchasePrice, salePrice, examId, site) VALUES
  (1, 'KET Exam',       'exam',   500, 1000, 1,    'mexico'),
  (2, 'Cambridge Book', 'book',   100, 300,  NULL, 'mexico'),
  (3, 'English Course', 'course', 200, 500,  NULL, 'colombia');

-- ─────────────────────────────────────────────
-- CARTS
-- cart 1: lead 1 (Mexico A), Jan 2025
-- cart 2: lead 2 (Colombia A), Feb 2025
-- cart 3: lead 3 (Mexico B), Mar 2025  ← sellerLeadId=3 (was 1, bug fixed)
-- cart 4: lead 1 (Mexico A), Dec 2024
-- cart 5: DELETED — must be excluded from all results
-- cart 6: lead 1 (Mexico A), Jan 2025, NO cart_products (empty cart edge case)
-- ─────────────────────────────────────────────
INSERT INTO cart (id, sellerLeadId, total, cost, createdAt, deletedAt) VALUES
  (1, 1, 0, 0, '2025-01-15 10:00:00', NULL),
  (2, 2, 0, 0, '2025-02-15 10:00:00', NULL),
  (3, 3, 0, 0, '2025-03-15 10:00:00', NULL),  -- fixed: sellerLeadId 1 → 3
  (4, 1, 0, 0, '2024-12-15 10:00:00', NULL),
  (5, 2, 0, 0, '2025-01-20 10:00:00', '2025-01-21 10:00:00'),  -- deleted
  (6, 1, 0, 0, '2025-01-25 10:00:00', NULL);                   -- empty cart

-- ─────────────────────────────────────────────
-- CART PRODUCTS
--
-- cart 1 (lead 1, mexico, Jan 2025):
--   2 exams × 1000 = 2000  cost 1000
--   1 book × 300   = 300   cost 100
--   subtotal: revenue 2300, cost 1100
--
-- cart 2 (lead 2, colombia, Feb 2025):
--   3 exams × 1000 = 3000  cost 1500
--   1 course × 500 = 500   cost 200
--   subtotal: revenue 3500, cost 1700
--
-- cart 3 (lead 3, mexico, Mar 2025):
--   1 exam × 1000  = 1000  cost 500
--   subtotal: revenue 1000, cost 500
--
-- cart 4 (lead 1, mexico, Dec 2024):
--   2 books × 300  = 600   cost 200
--   subtotal: revenue 600, cost 200
--
-- cart 5 (deleted — must NOT appear in results):
--   1 exam × 1000  = 1000  cost 500
--
-- cart 6 (empty — no cart_products):
--   no rows
--
-- TOTALS (excluding deleted cart 5):
--   total_revenue:  2300 + 3500 + 1000 + 600 = 7400
--   total_cost:     1100 + 1700 + 500  + 200 = 3500
--   profit_margin:  (7400 - 3500) / 7400 * 100 = 52.7%
--   exam_revenue:   2000 + 3000 + 1000 = 6000
--   book_revenue:   300 + 600 = 900
--   course_revenue: 500
--   total_exams:    2 + 3 + 1 = 6
--   total_books:    1 + 2 = 3
--   total_courses:  1
--   total_clients:  3 (leads 1, 2, 3)
--
-- MEXICO ONLY (leads 1 and 3):
--   revenue: 2300 + 1000 + 600 = 3900
--
-- COLOMBIA ONLY (lead 2):
--   revenue: 3500
--
-- DATE RANGE 2025-01-01 to 2025-02-28:
--   revenue: 2300 + 3500 = 5800
--
-- DATE RANGE 2025-01-01 to 2025-01-31:
--   revenue: 2300 (only cart 1)
-- ─────────────────────────────────────────────
INSERT INTO cart_product (id, cartId, productId, quantity, total, cost) VALUES
  -- cart 1: lead 1, mexico jan
  (1, 1, 1, 2, 2000, 1000),
  (2, 1, 2, 1, 300,  100),
  -- cart 2: lead 2, colombia feb
  (3, 2, 1, 3, 3000, 1500),
  (4, 2, 3, 1, 500,  200),
  -- cart 3: lead 3, mexico mar
  (5, 3, 1, 1, 1000, 500),
  -- cart 4: lead 1, mexico dec 2024
  (6, 4, 2, 2, 600,  200),
  -- cart 5: deleted (should NOT appear)
  (7, 5, 1, 1, 1000, 500);