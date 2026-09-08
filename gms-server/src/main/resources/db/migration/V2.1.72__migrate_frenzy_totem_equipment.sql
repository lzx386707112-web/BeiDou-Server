INSERT INTO inventoryequipment (inventoryitemid)
SELECT inventoryitemid
FROM inventoryitems
WHERE itemid = 3019999
  AND NOT EXISTS (
      SELECT 1
      FROM inventoryequipment
      WHERE inventoryequipment.inventoryitemid = inventoryitems.inventoryitemid
  );

CREATE TEMPORARY TABLE frenzy_totem_equip_positions (
    inventoryitemid INT UNSIGNED NOT NULL PRIMARY KEY,
    position INT NOT NULL
);

INSERT INTO frenzy_totem_equip_positions (inventoryitemid, position)
WITH RECURSIVE slot_numbers AS (
    SELECT 1 AS position
    UNION ALL
    SELECT position + 1
    FROM slot_numbers
    WHERE position < 96
),
totems AS (
    SELECT inventoryitemid,
           characterid,
           ROW_NUMBER() OVER (
               PARTITION BY characterid
               ORDER BY inventoryitemid
           ) AS item_rank
    FROM inventoryitems
    WHERE itemid = 3019999
      AND inventorytype <> -1
      AND inventorytype <> 1
      AND characterid IS NOT NULL
),
free_slots AS (
    SELECT owners.characterid,
           slot_numbers.position,
           ROW_NUMBER() OVER (
               PARTITION BY owners.characterid
               ORDER BY slot_numbers.position
           ) AS slot_rank
    FROM (SELECT DISTINCT characterid FROM totems) owners
    JOIN characters
      ON characters.id = owners.characterid
    CROSS JOIN slot_numbers
    LEFT JOIN inventoryitems occupied
      ON occupied.characterid = owners.characterid
     AND occupied.inventorytype = 1
     AND occupied.position = slot_numbers.position
    WHERE occupied.inventoryitemid IS NULL
      AND slot_numbers.position <= characters.equipslots
)
SELECT totems.inventoryitemid, free_slots.position
FROM totems
JOIN free_slots
  ON free_slots.characterid = totems.characterid
 AND free_slots.slot_rank = totems.item_rank;

UPDATE inventoryitems item
JOIN frenzy_totem_equip_positions target
  ON target.inventoryitemid = item.inventoryitemid
SET item.inventorytype = 1,
    item.position = target.position,
    item.quantity = 1;

DROP TEMPORARY TABLE frenzy_totem_equip_positions;
