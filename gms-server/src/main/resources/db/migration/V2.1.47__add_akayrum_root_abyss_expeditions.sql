ALTER TABLE bosslog_daily
    MODIFY COLUMN `bosstype` ENUM ('ZAKUM','CHAOS_ZAKUM','HORNTAIL','CHAOS_HORNTAIL','CYGNUS','VONBON','PIERRE','CQ','VELLUM','AKAYRUM','PINKBEAN','SCARGA','PAPULATUS') NOT NULL;

ALTER TABLE bosslog_weekly
    MODIFY COLUMN `bosstype` ENUM ('ZAKUM','CHAOS_ZAKUM','HORNTAIL','CHAOS_HORNTAIL','CYGNUS','VONBON','PIERRE','CQ','VELLUM','AKAYRUM','PINKBEAN','SCARGA','PAPULATUS') NOT NULL;

-- [阿卡伊勒]摩诃的委托：说明文件指定 8220019 以 20% 概率掉落碎裂的矛碎片。
INSERT INTO `drop_data` (`dropperid`, `itemid`, `minimum_quantity`, `maximum_quantity`, `questid`, `chance`) VALUES
(8220019, 4033080, 1, 1, 31171, 200000)
ON DUPLICATE KEY UPDATE
    `minimum_quantity` = VALUES(`minimum_quantity`),
    `maximum_quantity` = VALUES(`maximum_quantity`),
    `questid` = VALUES(`questid`),
    `chance` = VALUES(`chance`);
