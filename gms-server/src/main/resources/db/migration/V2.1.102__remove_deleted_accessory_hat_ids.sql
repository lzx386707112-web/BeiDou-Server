-- Remove hats and accessories that no longer exist in the client/server catalog.
CREATE TEMPORARY TABLE `_removed_equipment_ranges` (
    `startid` INT NOT NULL,
    `endid` INT NOT NULL,
    PRIMARY KEY (`startid`, `endid`)
);

INSERT INTO `_removed_equipment_ranges` (`startid`, `endid`) VALUES
(1002473, 1002475),
(1002716, 1002716),
(1002739, 1002740),
(1002749, 1002750),
(1002880, 1002880),
(1002940, 1002940),
(1003105, 1003107),
(1003273, 1003275),
(1003413, 1003413),
(1003824, 1003824),
(1004764, 1004773),
(1032269, 1032309),
(1122019, 1122038),
(1122039, 1122057),
(1122122, 1122126),
(1122128, 1122147),
(1122224, 1122245),
(1122337, 1122351),
(1122380, 1122420),
(1132022, 1132035),
(1132044, 1132083),
(1132249, 1132258),
(1132298, 1132298);

-- Static acquisition and crafting sources.
DELETE target FROM `drop_data` AS target INNER JOIN `_removed_equipment_ranges` AS removed ON target.itemid BETWEEN removed.startid AND removed.endid;
DELETE target FROM `drop_data_global` AS target INNER JOIN `_removed_equipment_ranges` AS removed ON target.itemid BETWEEN removed.startid AND removed.endid;
DELETE target FROM `reactordrops` AS target INNER JOIN `_removed_equipment_ranges` AS removed ON target.itemid BETWEEN removed.startid AND removed.endid;
DELETE target FROM `shopitems` AS target INNER JOIN `_removed_equipment_ranges` AS removed ON target.itemid BETWEEN removed.startid AND removed.endid;
DELETE target FROM `gachapon` AS target INNER JOIN `_removed_equipment_ranges` AS removed ON target.itemId BETWEEN removed.startid AND removed.endid;
DELETE target FROM `gachapon_reward` AS target INNER JOIN `_removed_equipment_ranges` AS removed ON target.item_id BETWEEN removed.startid AND removed.endid;
DELETE target FROM `fishing_items` AS target INNER JOIN `_removed_equipment_ranges` AS removed ON target.item_id BETWEEN removed.startid AND removed.endid;
DELETE target FROM `modified_cash_item` AS target INNER JOIN `_removed_equipment_ranges` AS removed ON target.item_id BETWEEN removed.startid AND removed.endid;
DELETE target FROM `makercreatedata` AS target INNER JOIN `_removed_equipment_ranges` AS removed ON target.itemid BETWEEN removed.startid AND removed.endid OR target.req_item BETWEEN removed.startid AND removed.endid OR target.catalyst BETWEEN removed.startid AND removed.endid;
DELETE target FROM `makerrecipedata` AS target INNER JOIN `_removed_equipment_ranges` AS removed ON target.itemid BETWEEN removed.startid AND removed.endid OR target.req_item BETWEEN removed.startid AND removed.endid;
DELETE target FROM `makerrewarddata` AS target INNER JOIN `_removed_equipment_ranges` AS removed ON target.itemid BETWEEN removed.startid AND removed.endid OR target.rewardid BETWEEN removed.startid AND removed.endid;
DELETE target FROM `makerreagentdata` AS target INNER JOIN `_removed_equipment_ranges` AS removed ON target.itemid BETWEEN removed.startid AND removed.endid;

-- Player-owned, mail, market, and auxiliary storage copies. Dependent rows go first.
DELETE target
FROM `dueyitems` AS target
INNER JOIN `inventoryitems` AS item ON item.inventoryitemid = target.inventoryitemid
INNER JOIN `_removed_equipment_ranges` AS removed ON item.itemid BETWEEN removed.startid AND removed.endid;

DELETE target
FROM `inventorymerchant` AS target
INNER JOIN `inventoryitems` AS item ON item.inventoryitemid = target.inventoryitemid
INNER JOIN `_removed_equipment_ranges` AS removed ON item.itemid BETWEEN removed.startid AND removed.endid;

DELETE target
FROM `inventoryequipment` AS target
INNER JOIN `inventoryitems` AS item ON item.inventoryitemid = target.inventoryitemid
INNER JOIN `_removed_equipment_ranges` AS removed ON item.itemid BETWEEN removed.startid AND removed.endid;

DELETE target FROM `inventoryitems` AS target INNER JOIN `_removed_equipment_ranges` AS removed ON target.itemid BETWEEN removed.startid AND removed.endid;
DELETE target FROM `mts_cart` AS target INNER JOIN `_removed_equipment_ranges` AS removed ON target.itemid BETWEEN removed.startid AND removed.endid;
DELETE target FROM `mts_items` AS target INNER JOIN `_removed_equipment_ranges` AS removed ON target.itemid BETWEEN removed.startid AND removed.endid;
DELETE target FROM `extrastorage` AS target INNER JOIN `_removed_equipment_ranges` AS removed ON target.itemid BETWEEN removed.startid AND removed.endid;

DROP TEMPORARY TABLE `_removed_equipment_ranges`;
