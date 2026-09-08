CREATE TEMPORARY TABLE frenzy_totem_keep (
    inventoryitemid INT UNSIGNED NOT NULL PRIMARY KEY
);

INSERT INTO frenzy_totem_keep (inventoryitemid)
SELECT inventoryitemid
FROM (
    SELECT item.inventoryitemid,
           ROW_NUMBER() OVER (
               PARTITION BY item.characterid, item.type
               ORDER BY
                   CASE WHEN item.inventorytype = -1 THEN 0 ELSE 1 END,
                   CASE
                       WHEN COALESCE(equipment.str, 0)
                          + COALESCE(equipment.dex, 0)
                          + COALESCE(equipment.`int`, 0)
                          + COALESCE(equipment.luk, 0)
                          + COALESCE(equipment.hp, 0)
                          + COALESCE(equipment.mp, 0) > 0
                       THEN 0 ELSE 1
                   END,
                   item.inventoryitemid
           ) AS item_rank
    FROM inventoryitems item
    LEFT JOIN inventoryequipment equipment
      ON equipment.inventoryitemid = item.inventoryitemid
    WHERE item.itemid = 1189999
      AND item.characterid IS NOT NULL
) ranked
WHERE item_rank = 1;

INSERT IGNORE INTO frenzy_totem_keep (inventoryitemid)
SELECT inventoryitemid
FROM (
    SELECT item.inventoryitemid,
           ROW_NUMBER() OVER (
               PARTITION BY item.accountid, item.type
               ORDER BY
                   CASE
                       WHEN COALESCE(equipment.str, 0)
                          + COALESCE(equipment.dex, 0)
                          + COALESCE(equipment.`int`, 0)
                          + COALESCE(equipment.luk, 0)
                          + COALESCE(equipment.hp, 0)
                          + COALESCE(equipment.mp, 0) > 0
                       THEN 0 ELSE 1
                   END,
                   item.inventoryitemid
           ) AS item_rank
    FROM inventoryitems item
    LEFT JOIN inventoryequipment equipment
      ON equipment.inventoryitemid = item.inventoryitemid
    WHERE item.itemid = 1189999
      AND item.characterid IS NULL
      AND item.accountid IS NOT NULL
) ranked
WHERE item_rank = 1;

DELETE merchant
FROM inventorymerchant merchant
JOIN inventoryitems item
  ON item.inventoryitemid = merchant.inventoryitemid
LEFT JOIN frenzy_totem_keep keep
  ON keep.inventoryitemid = item.inventoryitemid
WHERE item.itemid = 1189999
  AND keep.inventoryitemid IS NULL;

DELETE equipment
FROM inventoryequipment equipment
JOIN inventoryitems item
  ON item.inventoryitemid = equipment.inventoryitemid
LEFT JOIN frenzy_totem_keep keep
  ON keep.inventoryitemid = item.inventoryitemid
WHERE item.itemid = 1189999
  AND keep.inventoryitemid IS NULL;

DELETE item
FROM inventoryitems item
LEFT JOIN frenzy_totem_keep keep
  ON keep.inventoryitemid = item.inventoryitemid
WHERE item.itemid = 1189999
  AND keep.inventoryitemid IS NULL;

DROP TEMPORARY TABLE frenzy_totem_keep;
