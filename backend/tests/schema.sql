SET FOREIGN_KEY_CHECKS = 0;

CREATE TABLE IF NOT EXISTS `zone` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8_unicode_ci NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

CREATE TABLE IF NOT EXISTS `seller` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8_unicode_ci NOT NULL,
  `lastName` varchar(255) COLLATE utf8_unicode_ci NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

CREATE TABLE IF NOT EXISTS `lead` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8_unicode_ci NOT NULL,
  `globalState` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT 'active',
  `zoneId` int(11) DEFAULT NULL,
  `cct` int(11) NOT NULL DEFAULT 0,
  `support` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `site` varchar(255) COLLATE utf8_unicode_ci NOT NULL,
  `type` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `nomenclature` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `cambridge_user` char(50) COLLATE utf8_unicode_ci DEFAULT NULL,
  `writingTest` varchar(2) COLLATE utf8_unicode_ci DEFAULT NULL,
  `corporation_id` int(11) DEFAULT NULL,
  `alias` varchar(255) COLLATE utf8_unicode_ci DEFAULT NULL,
  `flow` varchar(100) COLLATE utf8_unicode_ci DEFAULT NULL,
  `campaign` varchar(200) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `deletedAt` date DEFAULT NULL,
  `projectId` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `FK_d5e1d990e43b127b29803dd1864` (`zoneId`),
  CONSTRAINT `FK_lead_zone` FOREIGN KEY (`zoneId`) REFERENCES `zone` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

CREATE TABLE IF NOT EXISTS `lead_address` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `street` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `extNum` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `intNum` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `colony` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `stateName` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `city` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `postalCode` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `corner1` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `corner2` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `comments` text COLLATE utf8_unicode_ci NOT NULL,
  `isFavorite` int(11) NOT NULL DEFAULT '0',
  `leadId` int(11) DEFAULT NULL,
  `levelId` int(11) DEFAULT NULL,
  `lat` varchar(100) COLLATE utf8_unicode_ci DEFAULT NULL,
  `lng` varchar(100) COLLATE utf8_unicode_ci DEFAULT NULL,
  `deletedAt` date DEFAULT NULL,
  `venueId` int(10) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `FK_72bb603c0dc4386b61120986def` (`leadId`),
  CONSTRAINT `FK_lead_address_lead` FOREIGN KEY (`leadId`) REFERENCES `lead` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

CREATE TABLE IF NOT EXISTS `seller_lead` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `promotionalStatus` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT 'new',
  `businessStatus` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT 'Carga de lead',
  `leadId` int(11) DEFAULT NULL,
  `sellerId` int(11) DEFAULT NULL,
  `campaignId` int(11) DEFAULT NULL,
  `deletedAt` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_seller_lead_seller` (`sellerId`),
  KEY `idx_seller_lead_lead` (`leadId`),
  CONSTRAINT `FK_seller_lead_lead` FOREIGN KEY (`leadId`) REFERENCES `lead` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
  CONSTRAINT `FK_seller_lead_seller` FOREIGN KEY (`sellerId`) REFERENCES `seller` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

CREATE TABLE IF NOT EXISTS `exam_cat` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8_unicode_ci NOT NULL,
  `presentation` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `dateType` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `duration` int(10) DEFAULT NULL,
  `oralDuration` int(10) DEFAULT NULL,
  `shortName` varchar(20) COLLATE utf8_unicode_ci DEFAULT NULL,
  `readingAndWriting` int(11) DEFAULT NULL,
  `reading` int(11) DEFAULT NULL,
  `writing` int(11) DEFAULT NULL,
  `listening` int(11) DEFAULT NULL,
  `speacking` int(11) DEFAULT NULL,
  `break1` int(11) DEFAULT NULL,
  `break2` int(11) DEFAULT NULL,
  `break3` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

CREATE TABLE IF NOT EXISTS `product` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8_unicode_ci NOT NULL,
  `purchasePrice` decimal(10,2) NOT NULL DEFAULT 0,
  `salePrice` decimal(10,2) NOT NULL DEFAULT 0,
  `productType` varchar(255) COLLATE utf8_unicode_ci NOT NULL,
  `isbn` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `edition` int(11) NOT NULL DEFAULT 0,
  `publishing` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `presentation` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `tab` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `userTarget` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `schoolLevel` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `criteria1` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `criteria2` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `criteria3` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `criteria4` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `stock` int(11) NOT NULL DEFAULT 0,
  `dateType` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `site` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `duration` int(11) DEFAULT NULL,
  `duration2` int(11) DEFAULT NULL,
  `saleUsdPrice` int(11) DEFAULT 0,
  `examId` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `product_exam_cat` FOREIGN KEY (`examId`) REFERENCES `exam_cat` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

CREATE TABLE IF NOT EXISTS `cart` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `saleType` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `billingStatus` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT 'Propuesta',
  `createdAt` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `deletedAt` datetime(6) DEFAULT NULL,
  `sellerLeadId` int(11) DEFAULT NULL,
  `generalDiscount` int(11) NOT NULL DEFAULT 0,
  `proration` int(11) NOT NULL DEFAULT 0,
  `subTotal` int(11) NOT NULL DEFAULT 0,
  `total` int(11) NOT NULL DEFAULT 0,
  `originId` int(11) DEFAULT NULL,
  `cost` int(11) NOT NULL DEFAULT 0,
  `updatedAt` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  `bookCommission` float DEFAULT NULL,
  `examCommission` float DEFAULT NULL,
  `projectId` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_cart_sellerLead` (`sellerLeadId`),
  CONSTRAINT `FK_cart_seller_lead` FOREIGN KEY (`sellerLeadId`) REFERENCES `seller_lead` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

CREATE TABLE IF NOT EXISTS `payment` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `status` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT 'Pendiente',
  `cartId` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_payment_cart` (`cartId`),
  CONSTRAINT `FK_payment_cart` FOREIGN KEY (`cartId`) REFERENCES `cart` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

CREATE TABLE IF NOT EXISTS `cart_product` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `quantity` int(11) NOT NULL DEFAULT 0,
  `discount` int(11) NOT NULL DEFAULT 0,
  `cost` int(11) NOT NULL DEFAULT 0,
  `dueDate` datetime NOT NULL DEFAULT '2000-01-01 00:00:00',
  `testDate` date NOT NULL DEFAULT '2000-01-01',
  `createdAt` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  `cartId` int(11) DEFAULT NULL,
  `productId` int(11) DEFAULT NULL,
  `gradeLevelId` int(11) DEFAULT NULL,
  `taxes` int(11) NOT NULL DEFAULT 0,
  `subTotal` int(11) NOT NULL DEFAULT 0,
  `total` int(11) NOT NULL DEFAULT 0,
  `deliveryDate` datetime NOT NULL DEFAULT '2000-01-01 00:00:00',
  `examId` int(11) DEFAULT NULL,
  `endDate` date NOT NULL DEFAULT '2000-01-01',
  `scholarship` float DEFAULT 0,
  `deletedAt` datetime DEFAULT NULL,
  `closeDate` date DEFAULT NULL,
  `asesorCloseDate` date DEFAULT NULL,
  `comercialCloseDate` date DEFAULT NULL,
  `financeCloseDate` date DEFAULT NULL,
  `examsCloseDate` date DEFAULT NULL,
  `originId` int(11) DEFAULT NULL,
  `payrollId` int(10) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_cart_product_cart` (`cartId`),
  KEY `idx_cart_product_product` (`productId`),
  CONSTRAINT `FK_cart_product_cart` FOREIGN KEY (`cartId`) REFERENCES `cart` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION,
  CONSTRAINT `FK_cart_product_product` FOREIGN KEY (`productId`) REFERENCES `product` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

CREATE TABLE IF NOT EXISTS `auth` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `password` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `user` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `area` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `sellerId` int(11) DEFAULT NULL,
  `bossId` int(11) DEFAULT NULL,
  `site` varchar(255) COLLATE utf8_unicode_ci NOT NULL DEFAULT '',
  `collageId` int(11) DEFAULT NULL,
  `cambridgeUser` varchar(50) COLLATE utf8_unicode_ci DEFAULT NULL,
  `zoneId` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `FK_user_zone` (`zoneId`),
  CONSTRAINT `FK_auth_zone` FOREIGN KEY (`zoneId`) REFERENCES `zone` (`id`) ON DELETE SET NULL,
  CONSTRAINT `FK_auth_seller` FOREIGN KEY (`sellerId`) REFERENCES `seller` (`id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;
