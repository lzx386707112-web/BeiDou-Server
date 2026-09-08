UPDATE inventoryequipment equipment
JOIN inventoryitems item
  ON item.inventoryitemid = equipment.inventoryitemid
SET equipment.str = 20,
    equipment.dex = 20,
    equipment.`int` = 20,
    equipment.luk = 20,
    equipment.hp = 2000,
    equipment.mp = 2000
WHERE item.itemid = 1189999
  AND equipment.str = 0
  AND equipment.dex = 0
  AND equipment.`int` = 0
  AND equipment.luk = 0
  AND equipment.hp = 0
  AND equipment.mp = 0;
