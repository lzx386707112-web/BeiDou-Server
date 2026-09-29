-- Remove weapons that no longer exist in the client/server resource catalog.
CREATE TEMPORARY TABLE `_removed_weapon_ids` (
    `itemid` INT NOT NULL PRIMARY KEY
);

INSERT INTO `_removed_weapon_ids` (`itemid`) VALUES
(1302062), (1302101), (1302280), (1302909), (1312803), (1322801), (1332243), (1382044), (1402137), (1412054), (1422188), (1432125), (1442053), (1452037),
(1302065), (1302102), (1302293), (1302910), (1312900), (1322803), (1332800), (1382053), (1402138), (1412089), (1422800), (1432126), (1442058), (1452046),
(1302066), (1302106), (1302304), (1302911), (1312901), (1322804), (1332801), (1382085), (1402154), (1412090), (1422801), (1432141), (1442059), (1452048),
(1302067), (1302110), (1302306), (1302912), (1312902), (1322900), (1332802), (1382088), (1402203), (1412091), (1422802), (1432150), (1442060), (1452049),
(1302071), (1302111), (1302307), (1302913), (1312903), (1322901), (1372121), (1382091), (1402215), (1412092), (1422803), (1432152), (1442061), (1452050),
(1302072), (1302114), (1302308), (1302914), (1322053), (1322902), (1372122), (1382147), (1402800), (1412093), (1422900), (1432153), (1442159), (1452052),
(1302073), (1302127), (1302309), (1302915), (1322059), (1322903), (1372123), (1382148), (1402801), (1412094), (1422901), (1432154), (1442160), (1452053),
(1302074), (1302132), (1302310), (1302916), (1322058), (1322904), (1372124), (1382149), (1402802), (1412107), (1422902), (1432155), (1442161), (1452093),
(1302075), (1302135), (1302332), (1312034), (1322057), (1332062), (1372125), (1382150), (1402803), (1412140), (1422903), (1432156), (1442162), (1452096),
(1302076), (1302138), (1302800), (1312035), (1322056), (1332064), (1372126), (1382151), (1402804), (1412151), (1432037), (1432172), (1442163), (1452099),
(1302078), (1302160), (1302801), (1312036), (1322055), (1332065), (1372182), (1382152), (1402900), (1422050), (1432041), (1432183), (1442164), (1452101),
(1302079), (1302161), (1302802), (1312101), (1322070), (1332104), (1372800), (1382214), (1402901), (1422053), (1432042), (1432188), (1442182), (1452151),
(1302088), (1302162), (1302803), (1312102), (1322098), (1332107), (1372801), (1382227), (1402902), (1422056), (1432043), (1432800), (1442194), (1452152),
(1302089), (1302163), (1302804), (1312103), (1322141), (1332110), (1372802), (1382800), (1402903), (1422058), (1432044), (1432801), (1442228), (1452153),
(1302090), (1302142), (1302900), (1312104), (1322142), (1332115), (1372803), (1382801), (1402904), (1422092), (1432045), (1432802), (1442238), (1452154),
(1302091), (1302173), (1302901), (1312105), (1322143), (1332172), (1372900), (1402040), (1412028), (1422093), (1432068), (1432803), (1442800), (1452155),
(1302092), (1302181), (1302902), (1312106), (1322144), (1332173), (1372901), (1402041), (1412029), (1422094), (1432071), (1432804), (1442801), (1452156),
(1302093), (1302195), (1302903), (1312119), (1322145), (1332174), (1372902), (1402042), (1412030), (1422095), (1432074), (1432900), (1442802), (1452173),
(1302094), (1302196), (1302904), (1312158), (1322146), (1332175), (1372903), (1402043), (1412031), (1422096), (1432076), (1432901), (1442803), (1452210),
(1302095), (1302197), (1302905), (1312169), (1322165), (1332176), (1382038), (1402133), (1412032), (1422097), (1432121), (1432902), (1442900), (1452221),
(1302098), (1302198), (1302906), (1312800), (1322208), (1332177), (1382040), (1402134), (1412041), (1422110), (1432122), (1432903), (1442901), (1452800),
(1302100), (1302199), (1302907), (1312801), (1322219), (1332196), (1382042), (1402135), (1412048), (1422145), (1432123), (1432904), (1442902), (1452801),
(1302099), (1302200), (1302908), (1312802), (1322800), (1332230), (1382043), (1402136), (1412051), (1422157), (1432124), (1442052), (1442903), (1462078),
(1462081), (1462084), (1462086), (1462118), (1462141), (1462142), (1462143), (1462144), (1462145), (1462146), (1462162), (1462168), (1462198), (1462209),
(1462800), (1462801), (1462802), (1462803), (1462804), (1462900), (1462901), (1462902), (1462903), (1462904), (1472056), (1472058), (1472059), (1472060),
(1472062), (1472064), (1472065), (1472066), (1472067), (1472098), (1472163), (1472164), (1472165), (1472166), (1472167), (1472168), (1472182), (1472219),
(1472231), (1472801), (1472802), (1472803), (1472804), (1472900), (1472901), (1472902), (1472903), (1472904), (1482025), (1482026), (1482027), (1482028),
(1482034), (1482066), (1482069), (1482072), (1482074), (1482124), (1482125), (1482126), (1482127), (1482128), (1482129), (1482143), (1482173), (1482184),
(1492026), (1492027), (1492028), (1492029), (1492032), (1492034), (1492066), (1492069), (1492072), (1492074), (1492100), (1492101), (1492124), (1492125),
(1492126), (1492127), (1492128), (1492129), (1492155), (1492184), (1492195), (1702137), (1702232), (1702353), (1302105), (1302159), (1312039), (1312064),
(1322065), (1322095), (1332081), (1332132), (1372046), (1372087), (1382062), (1382108), (1402053), (1402097), (1412035), (1412064), (1422039), (1422065),
(1432050), (1442071), (1442118), (1452062), (1452113), (1462056), (1462101), (1472077), (1472124), (1482029), (1492030), (1492087), (1482086), (1432088),
(1302108), (1312040), (1322066), (1332082), (1372047), (1302109), (1312041), (1322067), (1332083), (1372048), (1302237),
(1382063), (1402054), (1412036), (1422040), (1432051), (1382064), (1402055), (1412037), (1422041), (1432052), (1312124),
(1442072), (1452063), (1462057), (1472078), (1482036), (1442073), (1452064), (1462058), (1472079), (1482035);

-- Static acquisition and crafting sources.
DELETE target FROM `drop_data` AS target INNER JOIN `_removed_weapon_ids` AS removed ON removed.itemid = target.itemid;
DELETE target FROM `drop_data_global` AS target INNER JOIN `_removed_weapon_ids` AS removed ON removed.itemid = target.itemid;
DELETE target FROM `reactordrops` AS target INNER JOIN `_removed_weapon_ids` AS removed ON removed.itemid = target.itemid;
DELETE target FROM `shopitems` AS target INNER JOIN `_removed_weapon_ids` AS removed ON removed.itemid = target.itemid;
DELETE target FROM `gachapon` AS target INNER JOIN `_removed_weapon_ids` AS removed ON removed.itemid = target.itemId;
DELETE target FROM `gachapon_reward` AS target INNER JOIN `_removed_weapon_ids` AS removed ON removed.itemid = target.item_id;
DELETE target FROM `fishing_items` AS target INNER JOIN `_removed_weapon_ids` AS removed ON removed.itemid = target.item_id;
DELETE target FROM `modified_cash_item` AS target INNER JOIN `_removed_weapon_ids` AS removed ON removed.itemid = target.item_id;
DELETE target FROM `makercreatedata` AS target INNER JOIN `_removed_weapon_ids` AS removed ON removed.itemid IN (target.itemid, target.req_item, target.catalyst);
DELETE target FROM `makerrecipedata` AS target INNER JOIN `_removed_weapon_ids` AS removed ON removed.itemid IN (target.itemid, target.req_item);
DELETE target FROM `makerrewarddata` AS target INNER JOIN `_removed_weapon_ids` AS removed ON removed.itemid IN (target.itemid, target.rewardid);
DELETE target FROM `makerreagentdata` AS target INNER JOIN `_removed_weapon_ids` AS removed ON removed.itemid = target.itemid;

-- Player-owned, mail, market, and auxiliary storage copies. Dependent rows go first.
DELETE target
FROM `dueyitems` AS target
INNER JOIN `inventoryitems` AS item ON item.inventoryitemid = target.inventoryitemid
INNER JOIN `_removed_weapon_ids` AS removed ON removed.itemid = item.itemid;

DELETE target
FROM `inventorymerchant` AS target
INNER JOIN `inventoryitems` AS item ON item.inventoryitemid = target.inventoryitemid
INNER JOIN `_removed_weapon_ids` AS removed ON removed.itemid = item.itemid;

DELETE target
FROM `inventoryequipment` AS target
INNER JOIN `inventoryitems` AS item ON item.inventoryitemid = target.inventoryitemid
INNER JOIN `_removed_weapon_ids` AS removed ON removed.itemid = item.itemid;

DELETE target FROM `inventoryitems` AS target INNER JOIN `_removed_weapon_ids` AS removed ON removed.itemid = target.itemid;
DELETE target FROM `mts_cart` AS target INNER JOIN `_removed_weapon_ids` AS removed ON removed.itemid = target.itemid;
DELETE target FROM `mts_items` AS target INNER JOIN `_removed_weapon_ids` AS removed ON removed.itemid = target.itemid;
DELETE target FROM `extrastorage` AS target INNER JOIN `_removed_weapon_ids` AS removed ON removed.itemid = target.itemid;

DROP TEMPORARY TABLE `_removed_weapon_ids`;
