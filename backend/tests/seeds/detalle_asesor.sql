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
  (1, 'Ana', 'Garcia'),
  (2, 'Carlos', 'Lopez');

-- ─────────────────────────────────────────────
-- LEADS (schools)
-- Ana manages 1–3 (Mexico), Carlos manages 4–6 (Colombia)
-- ─────────────────────────────────────────────
INSERT INTO `lead` (id, name, site, zoneId, campaign) VALUES
  (1, 'Colegio Alpha',   'mexico',   1, 'detalle-test'),
  (2, 'Colegio Beta',    'mexico',   1, 'detalle-test'),
  (3, 'Colegio Gamma',   'mexico',   1, 'detalle-test'),
  (4, 'Colegio Delta',   'colombia', 2, 'detalle-test'),
  (5, 'Colegio Epsilon', 'colombia', 2, 'detalle-test'),
  (6, 'Colegio Zeta',    'colombia', 2, 'detalle-test');

-- ─────────────────────────────────────────────
-- LEAD ADDRESSES
-- ─────────────────────────────────────────────
INSERT INTO lead_address (id, stateName, city, comments, leadId) VALUES
  (1, 'CDMX',         'Mexico City', '', 1),
  (2, 'Jalisco',      'Guadalajara', '', 2),
  (3, 'Jalisco',      'Guadalajara', '', 3),
  (4, 'Cundinamarca', 'Bogota',      '', 4),
  (5, 'Antioquia',    'Medellin',    '', 5),
  (6, 'Antioquia',    'Medellin',    '', 6);

-- ─────────────────────────────────────────────
-- SELLER_LEAD
-- ─────────────────────────────────────────────
INSERT INTO seller_lead (id, sellerId, leadId, businessStatus) VALUES
  (1, 1, 1, 'ganado'),
  (2, 1, 2, 'ganado'),
  (3, 1, 3, 'mantenido'),
  (4, 2, 4, 'ganado'),
  (5, 2, 5, 'perdido'),
  (6, 2, 6, 'ganado');

-- ─────────────────────────────────────────────
-- EXAM CATS
-- ─────────────────────────────────────────────
INSERT INTO exam_cat (id, name, shortName, presentation, dateType) VALUES
  (1, 'KET', 'KET', 'Paper', 'fixed'),
  (2, 'PET', 'PET', 'Paper', 'fixed'),
  (3, 'FCE', 'FCE', 'Paper', 'fixed');

-- ─────────────────────────────────────────────
-- PRODUCTS
-- product 4 is a book (non-exam) to verify exam filter
-- ─────────────────────────────────────────────
INSERT INTO product (id, name, productType, purchasePrice, salePrice, examId, site) VALUES
  (1, 'KET Exam', 'exam', 500, 1000, 1, 'mexico'),
  (2, 'PET Exam', 'exam', 600, 1200, 2, 'mexico'),
  (3, 'FCE Exam', 'exam', 700, 1400, 3, 'colombia'),
  (4, 'Prep Book', 'book', 100, 200, NULL, 'mexico');

-- ─────────────────────────────────────────────
-- CARTS
-- cart 7 → 2024 (prior year, no date filter = included)
-- cart 8 → deleted (excluded always)
-- ─────────────────────────────────────────────
INSERT INTO cart (id, sellerLeadId, total, cost, createdAt, deletedAt) VALUES
  (1, 1, 0, 0, '2025-01-15 10:00:00', NULL),
  (2, 2, 0, 0, '2025-02-10 10:00:00', NULL),
  (3, 3, 0, 0, '2025-03-05 10:00:00', NULL),
  (4, 4, 0, 0, '2025-06-20 10:00:00', NULL),
  (5, 5, 0, 0, '2025-07-15 10:00:00', NULL),
  (6, 6, 0, 0, '2025-08-01 10:00:00', NULL),
  (7, 1, 0, 0, '2024-06-10 10:00:00', NULL),
  (8, 1, 0, 0, '2025-01-20 10:00:00', '2025-01-21 10:00:00');

-- ─────────────────────────────────────────────
-- CART PRODUCTS
--
-- Active exam rows (ids 1–6): one per cart 1–6
-- cp 7: prior year (cart 7) — included without date filter
-- cp 8: deleted cart (cart 8) — always excluded
-- cp 9: book product (cart 1) — excluded by productType='exam'
--
-- Expected counts with no filters: cp ids 1,2,3,4,5,6,7 = 7 rows
-- Date 2025-01-01 → 2025-04-30: cp ids 1,2,3 (carts 1,2,3)
-- Country=colombia: cp ids 4,5,6
-- Search=Ana Garcia: cp ids 1,2,3,7
-- Search=Gamma: cp id 3
-- ─────────────────────────────────────────────
INSERT INTO cart_product (id, cartId, productId, quantity, total, cost, testDate, deletedAt) VALUES
  (1, 1, 1, 5, 5000, 2500, '2025-01-20', NULL),
  (2, 2, 2, 3, 3600, 1800, '2025-02-15', NULL),
  (3, 3, 3, 1, 1400,  700, '2025-03-10', NULL),
  (4, 4, 2, 6, 7200, 3600, '2025-06-25', NULL),
  (5, 5, 3, 2, 2800, 1400, '2025-07-20', NULL),
  (6, 6, 1, 4, 4000, 2000, '2025-08-05', NULL),
  (7, 7, 1, 2, 2000, 1000, '2024-06-15', NULL),
  (8, 8, 1, 1, 1000,  500, '2025-01-22', NULL),
  (9, 1, 4, 1,  200,  100, '2025-01-20', NULL);
