-- Remove 315 approved weapons/shoes; preserve all 39 user-retained IDs.
CREATE TEMPORARY TABLE `_removed_unreferenced_equipment_ids` (
    `itemid` INT NOT NULL PRIMARY KEY
);

INSERT INTO `_removed_unreferenced_equipment_ids` (`itemid`) VALUES
(1070033), (1070034), (1070035), (1070036), (1070038), (1070039), (1070040), (1070041), (1070043), (1070044), (1070045), (1070046),
(1071050), (1071051), (1071052), (1071053), (1071055), (1071056), (1071057), (1071058), (1071060), (1071061), (1071062), (1071063),
(1302060), (1302124), (1302125), (1302126), (1302141), (1302164), (1302165), (1302166), (1302167), (1302168), (1302176), (1302177),
(1302178), (1302179), (1302186), (1302189), (1302190), (1302250), (1302254), (1302255), (1302256), (1302259), (1302273), (1302294),
(1302295), (1312046), (1312049), (1312052), (1312055), (1312057), (1312074), (1312075), (1312076), (1312077), (1312088), (1312089),
(1312090), (1312091), (1312092), (1312093), (1312139), (1312140), (1312141), (1312146), (1312152), (1322074), (1322077), (1322080),
(1322083), (1322085), (1322109), (1322110), (1322111), (1322112), (1322128), (1322129), (1322130), (1322131), (1322132), (1322133),
(1322185), (1322186), (1322187), (1322192), (1322201), (1332093), (1332094), (1332095), (1332136), (1332137), (1332138), (1332139),
(1332140), (1332141), (1332154), (1332155), (1332156), (1332157), (1332210), (1332211), (1332212), (1332217), (1332224), (1332244),
(1372056), (1372063), (1372066), (1372069), (1372072), (1372088), (1372089), (1372090), (1372091), (1372092), (1372093), (1372103),
(1372104), (1372105), (1372106), (1372165), (1372166), (1372167), (1372171), (1372176), (1382074), (1382075), (1382076), (1382094),
(1382112), (1382113), (1382114), (1382115), (1382116), (1382117), (1382128), (1382129), (1382130), (1382131), (1382171), (1382196),
(1382197), (1382198), (1382203), (1382207), (1402068), (1402075), (1402078), (1402081), (1402084), (1402098), (1402099), (1402100),
(1402101), (1402102), (1402103), (1402115), (1402116), (1402117), (1402118), (1402181), (1402182), (1402183), (1402188), (1402195),
(1412043), (1412044), (1412057), (1412073), (1412074), (1412075), (1412076), (1412129), (1412134), (1422046), (1422047), (1422075),
(1422076), (1422077), (1422078), (1422132), (1422138), (1432058), (1432059), (1432089), (1432090), (1432091), (1432092), (1432093),
(1432094), (1432103), (1432104), (1432105), (1432106), (1432161), (1432166), (1442083), (1442084), (1442096), (1442099), (1442102),
(1442105), (1442124), (1442125), (1442126), (1442127), (1442128), (1442129), (1442140), (1442141), (1442142), (1442143), (1442154),
(1442185), (1442206), (1442207), (1442208), (1442212), (1442222), (1452077), (1452078), (1452079), (1452117), (1452118), (1452119),
(1452120), (1452121), (1452122), (1452133), (1452134), (1452135), (1452136), (1452193), (1452194), (1452195), (1452199), (1452204),
(1462069), (1462070), (1462071), (1462105), (1462106), (1462107), (1462108), (1462109), (1462110), (1462122), (1462123), (1462124),
(1462125), (1462182), (1462183), (1462187), (1462192), (1472093), (1472094), (1472095), (1472104), (1472107), (1472110), (1472112),
(1472128), (1472129), (1472130), (1472131), (1472132), (1472133), (1472145), (1472146), (1472147), (1472148), (1472201), (1472202),
(1472203), (1472208), (1472213), (1482041), (1482042), (1482043), (1482090), (1482091), (1482092), (1482093), (1482094), (1482095),
(1482106), (1482107), (1482108), (1482109), (1482155), (1482156), (1482157), (1482162), (1482167), (1492042), (1492043), (1492044),
(1492089), (1492090), (1492092), (1492093), (1492094), (1492105), (1492106), (1492107), (1492108), (1492166), (1492167), (1492168),
(1492173), (1492178), (1702855);

-- Static acquisition and crafting sources.
DELETE target FROM `drop_data` AS target INNER JOIN `_removed_unreferenced_equipment_ids` AS removed ON removed.itemid = target.itemid;
DELETE target FROM `drop_data_global` AS target INNER JOIN `_removed_unreferenced_equipment_ids` AS removed ON removed.itemid = target.itemid;
DELETE target FROM `reactordrops` AS target INNER JOIN `_removed_unreferenced_equipment_ids` AS removed ON removed.itemid = target.itemid;
DELETE target FROM `shopitems` AS target INNER JOIN `_removed_unreferenced_equipment_ids` AS removed ON removed.itemid = target.itemid;
DELETE target FROM `gachapon` AS target INNER JOIN `_removed_unreferenced_equipment_ids` AS removed ON removed.itemid = target.itemId;
DELETE target FROM `gachapon_reward` AS target INNER JOIN `_removed_unreferenced_equipment_ids` AS removed ON removed.itemid = target.item_id;
DELETE target FROM `fishing_items` AS target INNER JOIN `_removed_unreferenced_equipment_ids` AS removed ON removed.itemid = target.item_id;
DELETE target FROM `modified_cash_item` AS target INNER JOIN `_removed_unreferenced_equipment_ids` AS removed ON removed.itemid = target.item_id;
DELETE target FROM `makercreatedata` AS target INNER JOIN `_removed_unreferenced_equipment_ids` AS removed ON removed.itemid IN (target.itemid, target.req_item, target.catalyst);
DELETE target FROM `makerrecipedata` AS target INNER JOIN `_removed_unreferenced_equipment_ids` AS removed ON removed.itemid IN (target.itemid, target.req_item);
DELETE target FROM `makerrewarddata` AS target INNER JOIN `_removed_unreferenced_equipment_ids` AS removed ON removed.itemid IN (target.itemid, target.rewardid);
DELETE target FROM `makerreagentdata` AS target INNER JOIN `_removed_unreferenced_equipment_ids` AS removed ON removed.itemid = target.itemid;

-- Player-owned, mail, market, and auxiliary storage copies. Dependent rows go first.
DELETE target
FROM `dueyitems` AS target
INNER JOIN `inventoryitems` AS item ON item.inventoryitemid = target.inventoryitemid
INNER JOIN `_removed_unreferenced_equipment_ids` AS removed ON removed.itemid = item.itemid;

DELETE target
FROM `inventorymerchant` AS target
INNER JOIN `inventoryitems` AS item ON item.inventoryitemid = target.inventoryitemid
INNER JOIN `_removed_unreferenced_equipment_ids` AS removed ON removed.itemid = item.itemid;

DELETE target
FROM `inventoryequipment` AS target
INNER JOIN `inventoryitems` AS item ON item.inventoryitemid = target.inventoryitemid
INNER JOIN `_removed_unreferenced_equipment_ids` AS removed ON removed.itemid = item.itemid;

DELETE target FROM `inventoryitems` AS target INNER JOIN `_removed_unreferenced_equipment_ids` AS removed ON removed.itemid = target.itemid;
DELETE target FROM `mts_cart` AS target INNER JOIN `_removed_unreferenced_equipment_ids` AS removed ON removed.itemid = target.itemid;
DELETE target FROM `mts_items` AS target INNER JOIN `_removed_unreferenced_equipment_ids` AS removed ON removed.itemid = target.itemid;
DELETE target FROM `extrastorage` AS target INNER JOIN `_removed_unreferenced_equipment_ids` AS removed ON removed.itemid = target.itemid;

DROP TEMPORARY TABLE `_removed_unreferenced_equipment_ids`;
