-- UI DEV seed aligned to the payment + student_payments report model.
--
-- Edge cases intentionally covered:
-- - approved payments with student allocations
-- - approved payments without student_payments
-- - multiple approved payments on one cart
-- - multiple students allocated to the same cart_product
-- - multiple addresses on one lead
-- - pending payments
-- - deleted carts
-- - book / course / exam / empty-productType rows

INSERT INTO zone (id, name) VALUES
  (1, 'IH Mexico'),
  (2, 'IH Colombia'),
  (3, 'IH Peru');

INSERT INTO seller (id, name, lastName) VALUES
  (1, 'Ana', 'Garcia'),
  (2, 'Carlos', 'Rodriguez'),
  (3, 'Lucia', 'Rios'),
  (4, 'Miguel', 'Torres');

INSERT INTO `lead` (id, name, site, zoneId, campaign) VALUES
  (1, 'Colegio Mexico Uno', 'mexico', 1, 'ui-dev'),
  (2, 'Colegio Mexico Dos', 'mexico', 1, 'ui-dev'),
  (3, 'Colegio Colombia Uno', 'colombia', 2, 'ui-dev'),
  (4, 'Colegio Peru Uno', 'peru', 3, 'ui-dev'),
  (5, 'Colegio Colombia Dos', 'colombia', 2, 'ui-dev'),
  (6, 'Colegio Mexico Tres', 'mexico', 1, 'ui-dev');

INSERT INTO lead_address (id, leadId, stateName, city, comments, deletedAt) VALUES
  (1, 1, 'CDMX', 'Mexico City', '', NULL),
  (2, 2, 'Jalisco', 'Guadalajara', '', NULL),
  (3, 2, 'CDMX', 'Mexico City', '', NULL),
  (4, 3, 'Antioquia', 'Medellin', '', NULL),
  (5, 4, 'Lima', 'Lima', '', NULL),
  (6, 5, 'Bogota', 'Bogota', '', NULL),
  (7, 6, 'Puebla', 'Puebla', '', NULL),
  (8, 1, 'CDMX', 'Mexico City', '', '2025-01-01');

INSERT INTO seller_lead (id, sellerId, leadId, businessStatus) VALUES
  (1, 1, 1, 'mantenido'),
  (2, 1, 2, 'ganado'),
  (3, 2, 3, 'mantenido'),
  (4, 3, 4, 'mantenido'),
  (5, 2, 5, 'ganado'),
  (6, 4, 6, 'ganado');

INSERT INTO exam_cat (id, name, shortName, presentation, dateType) VALUES
  (1, 'KET', 'KET', 'Paper', 'fixed'),
  (2, 'PET', 'PET', 'Paper', 'fixed'),
  (3, 'FCE', 'FCE', 'Paper', 'fixed'),
  (4, 'IELTS Academic', 'IELTS', 'Paper', 'fixed'),
  (5, 'MET', 'MET', 'Computer', 'fixed'),
  (6, 'TKT', 'TKT', 'Paper', 'fixed'),
  (7, 'Placement Tests', 'PLACEMENT', 'Computer', 'fixed'),
  (8, 'TEA', 'TEA', 'Paper', 'fixed');

INSERT INTO product (id, name, productType, purchasePrice, salePrice, examId, site) VALUES
  (1, 'KET Exam', 'exam', 500, 1000, 1, 'mexico'),
  (2, 'PET Exam', 'exam', 600, 1200, 2, 'mexico'),
  (3, 'FCE Exam', 'exam', 700, 1500, 3, 'colombia'),
  (4, 'IELTS Exam', 'exam', 800, 1700, 4, 'peru'),
  (5, 'MET Exam', 'exam', 650, 1300, 5, 'colombia'),
  (6, 'TKT Exam', 'exam', 450, 900, 6, 'mexico'),
  (7, 'Placement Test', 'exam', 200, 500, 7, 'mexico'),
  (8, 'Prep Book', 'book', 100, 300, NULL, 'mexico'),
  (9, 'Prep Course', 'course', 300, 600, NULL, 'colombia'),
  (10, 'Admin Fee', '', 0, 500, NULL, 'mexico'),
  (11, 'TEA Exam', 'exam', 550, 1100, 8, 'colombia');

INSERT INTO cart (id, sellerLeadId, total, cost, createdAt, deletedAt) VALUES
  (1, 1, 1000, 500, '2024-06-15 10:00:00', NULL),
  (2, 3, 1300, 650, '2024-07-10 10:00:00', NULL),
  (3, 4, 1700, 800, '2024-09-01 10:00:00', NULL),
  (4, 1, 2000, 1000, '2025-01-10 10:00:00', NULL),
  (5, 2, 1500, 700, '2025-02-05 10:00:00', NULL),
  (6, 1, 900, 450, '2025-03-08 10:00:00', NULL),
  (7, 3, 3600, 1700, '2025-04-01 10:00:00', NULL),
  (8, 5, 3500, 1750, '2025-05-10 10:00:00', NULL),
  (9, 4, 1700, 800, '2025-06-01 10:00:00', NULL),
  (10, 6, 500, 200, '2025-06-28 10:00:00', NULL),
  (11, 6, 500, 0, '2025-07-31 10:00:00', NULL),
  (12, 3, 1500, 700, '2025-09-10 10:00:00', NULL),
  (13, 4, 888, 444, '2025-10-01 10:00:00', '2025-10-02 10:00:00');

INSERT INTO payment (
  id, quantity, status, createdAt, updatedAt, cartId, `use`, comments, billingStatus,
  studentId, paymentDate
) VALUES
  (1, 1000, 'Aprobado', '2024-06-15 10:00:00', '2024-06-15 10:00:00', 1, '', '', '', 0, '2024-06-20'),
  (2, 1300, 'Aprobado', '2024-07-10 10:00:00', '2024-07-10 10:00:00', 2, '', '', '', 0, '2024-07-12'),
  (3, 1700, 'Aprobado', '2024-09-01 10:00:00', '2024-09-01 10:00:00', 3, '', '', '', 0, '2024-09-05'),
  (4, 2000, 'Aprobado', '2025-01-10 10:00:00', '2025-01-10 10:00:00', 4, '', '', '', 0, '2025-01-15'),
  (5, 1500, 'Aprobado', '2025-02-05 10:00:00', '2025-02-05 10:00:00', 5, '', '', '', 0, '2025-02-07'),
  (6, 900, 'Aprobado', '2025-03-08 10:00:00', '2025-03-08 10:00:00', 6, '', '', '', 0, '2025-03-10'),
  (7, 3600, 'Aprobado', '2025-04-01 10:00:00', '2025-04-01 10:00:00', 7, '', '', '', 0, '2025-04-02'),
  (8, 3500, 'Aprobado', '2025-05-10 10:00:00', '2025-05-10 10:00:00', 8, '', '', '', 0, '2025-05-12'),
  (9, 1700, 'Aprobado', '2025-06-01 10:00:00', '2025-06-01 10:00:00', 9, '', '', '', 0, '2025-06-03'),
  (10, 500, 'Aprobado', '2025-06-28 10:00:00', '2025-06-28 10:00:00', 10, '', '', '', 0, '2025-07-02'),
  (11, 300, 'Aprobado', '2025-08-01 10:00:00', '2025-08-01 10:00:00', 11, '', '', '', 0, '2025-08-04'),
  (12, 200, 'Aprobado', '2025-08-02 10:00:00', '2025-08-02 10:00:00', 11, '', '', '', 0, '2025-08-05'),
  (13, 1500, 'Pendiente', '2025-09-10 10:00:00', '2025-09-10 10:00:00', 12, '', '', '', 0, '2025-09-11'),
  (14, 888, 'Aprobado', '2025-10-01 10:00:00', '2025-10-01 10:00:00', 13, '', '', '', 0, '2025-10-02');

INSERT INTO cart_product (id, cartId, productId, quantity, total, cost, testDate, deletedAt) VALUES
  (1, 1, 1, 1, 1000, 500, '2024-06-25', NULL),
  (2, 2, 5, 1, 1300, 650, '2024-07-20', NULL),
  (3, 3, 4, 1, 1700, 800, '2024-09-10', NULL),
  (4, 4, 1, 2, 2000, 1000, '2025-01-20', NULL),
  (5, 5, 2, 1, 1200, 600, '2025-02-15', NULL),
  (6, 5, 8, 1, 300, 100, '2025-02-15', NULL),
  (7, 6, 6, 1, 900, 450, '2025-03-20', NULL),
  (8, 7, 3, 2, 3000, 1400, '2025-04-15', NULL),
  (9, 7, 9, 1, 600, 300, '2025-04-15', NULL),
  (10, 8, 11, 2, 2200, 1100, '2025-05-18', NULL),
  (11, 8, 5, 1, 1300, 650, '2025-05-18', NULL),
  (12, 9, 4, 1, 1700, 800, '2025-06-10', NULL),
  (13, 10, 7, 1, 500, 200, '2025-07-15', NULL),
  (14, 11, 10, 1, 500, 0, '2025-08-10', NULL),
  (15, 12, 3, 1, 1500, 700, '2025-09-20', NULL),
  (16, 13, 1, 1, 888, 444, '2025-10-10', NULL),
  (17, 5, 2, 1, 1200, 600, '2025-02-16', '2025-02-16 10:00:00');

INSERT INTO student (id, cartProductId) VALUES
  (1, 1),
  (2, 2),
  (3, 3),
  (4, 4),
  (5, 4),
  (6, 5),
  (7, 6),
  (8, 7),
  (9, 8),
  (10, 8),
  (11, 9),
  (12, 10),
  (13, 11),
  (14, 12),
  (15, 13);

INSERT INTO student_payments (student_id, payment_id, amount) VALUES
  (1, 1, 1000.00),
  (2, 2, 1300.00),
  (3, 3, 1700.00),
  (4, 4, 1000.00),
  (5, 4, 1000.00),
  (6, 5, 1200.00),
  (7, 5, 300.00),
  (8, 6, 900.00),
  (9, 7, 1500.00),
  (10, 7, 1500.00),
  (11, 7, 600.00),
  (12, 8, 2200.00),
  (13, 8, 1300.00),
  (14, 9, 1700.00),
  (15, 10, 500.00);
