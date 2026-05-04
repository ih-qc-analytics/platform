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
  (1, 'Ana', 'Garcia'),
  (2, 'Carlos', 'Rodriguez'),
  (3, 'Lucia', 'Rios'),
  (4, 'Empty', 'Seller');

-- ─────────────────────────────────────────────
-- LEADS
-- ─────────────────────────────────────────────
INSERT INTO `lead` (id, name, site, zoneId, campaign) VALUES
  (1, 'Colegio Mexico A', 'mexico', 1, 'asesor-test'),
  (2, 'Colegio Mexico B', 'mexico', 1, 'asesor-test'),
  (3, 'Colegio Colombia A', 'colombia', 2, 'asesor-test'),
  (4, 'Colegio Peru A', 'peru', 3, 'asesor-test'),
  (5, 'Colegio Colombia B', 'colombia', 2, 'asesor-test');

-- ─────────────────────────────────────────────
-- LEAD ADDRESS
-- ─────────────────────────────────────────────
INSERT INTO lead_address (id, stateName, city, comments, leadId) VALUES
  (1, 'CDMX', 'Mexico City', '', 1),
  (2, 'Jalisco', 'Guadalajara', '', 2),
  (3, 'Bogota', 'Bogota', '', 3),
  (4, 'Lima', 'Lima', '', 4),
  (5, 'Antioquia', 'Medellin', '', 5);

-- ─────────────────────────────────────────────
-- SELLER_LEAD
-- ─────────────────────────────────────────────
INSERT INTO seller_lead (id, sellerId, leadId, businessStatus) VALUES
  (1, 1, 1, 'ganado'),
  (2, 1, 2, 'mantenido'),
  (3, 2, 3, 'perdido'),
  (4, 3, 4, 'ganado'),
  (5, 2, 5, 'ganado');

-- ─────────────────────────────────────────────
-- EXAM CAT
-- ─────────────────────────────────────────────
INSERT INTO exam_cat (id, name, shortName, presentation, dateType) VALUES
  (1, 'A1', 'A1', 'Paper', 'fixed'),
  (2, 'Starters', 'STR', 'Paper', 'fixed'),
  (3, 'a1 starters', 'A1S', 'Computer', 'fixed'),
  (4, 'PET', 'PET', 'Paper', 'fixed'),
  (5, 'pet', 'PET2', 'Computer', 'fixed');

-- ─────────────────────────────────────────────
-- PRODUCTS
-- ─────────────────────────────────────────────
INSERT INTO product (id, name, productType, purchasePrice, salePrice, examId, site) VALUES
  (1, 'A1 Exam', 'exam', 500, 1000, 1, 'mexico'),
  (2, 'Starters Exam', 'exam', 450, 900, 2, 'mexico'),
  (3, 'A1 Starters Exam', 'exam', 450, 900, 3, 'mexico'),
  (4, 'PET Exam', 'exam', 600, 1200, 4, 'colombia'),
  (5, 'pet Exam', 'exam', 600, 1200, 5, 'peru'),
  (6, 'Practice Book', 'book', 100, 300, NULL, 'mexico'),
  (7, 'Prep Course', 'course', 250, 600, NULL, 'colombia');

-- ─────────────────────────────────────────────
-- CARTS
-- cart 6 is prior year
-- cart 7 is deleted
-- cart 8 contains a deleted cart_product
-- ─────────────────────────────────────────────
INSERT INTO cart (id, sellerLeadId, total, cost, createdAt, deletedAt) VALUES
  (1, 1, 0, 0, '2025-01-10 10:00:00', NULL),
  (2, 2, 0, 0, '2025-02-20 10:00:00', NULL),
  (3, 3, 0, 0, '2025-03-15 10:00:00', NULL),
  (4, 4, 0, 0, '2025-04-05 10:00:00', NULL),
  (5, 5, 0, 0, '2025-05-18 10:00:00', NULL),
  (6, 1, 0, 0, '2024-12-15 10:00:00', NULL),
  (7, 4, 0, 0, '2025-06-01 10:00:00', '2025-06-02 10:00:00'),
  (8, 5, 0, 0, '2025-05-20 10:00:00', NULL);

-- ─────────────────────────────────────────────
-- CART PRODUCTS
--
-- 2025 active totals:
-- Ana:    5000 revenue, A1 starters exams = 5, schools = 2
-- Carlos: 5400 revenue, PET exams = 4, schools = 2
-- Lucia:  1200 revenue, PET exams = 1, schools = 1
--
-- deleted cart_product on cart 8 must be excluded
-- deleted cart 7 must be excluded
-- 2024 cart 6 must be excluded by year filter
-- ─────────────────────────────────────────────
INSERT INTO cart_product (id, cartId, productId, quantity, total, cost, deletedAt) VALUES
  (1, 1, 1, 2, 2000, 1000, NULL),
  (2, 1, 2, 1, 900, 450, NULL),
  (3, 1, 6, 1, 300, 100, NULL),
  (4, 2, 3, 2, 1800, 900, NULL),
  (5, 3, 4, 3, 3600, 1800, NULL),
  (6, 3, 7, 1, 600, 250, NULL),
  (7, 4, 5, 1, 1200, 600, NULL),
  (8, 5, 5, 1, 1200, 600, NULL),
  (9, 6, 1, 1, 1000, 500, NULL),
  (10, 7, 5, 1, 1300, 650, NULL),
  (11, 8, 4, 2, 2400, 1200, '2025-05-21 10:00:00');
