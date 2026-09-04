// HAND MAINTAINED, not derived. Every id here was named one at a time; see below
// for why no rule can find them.
//
// Maps that must never get weather, regardless of what their backmost background
// canvas says. The (bank, index) rule in weather.cpp is right for the overwhelming
// majority of maps, but it cannot see the cases where an INTERIOR reuses its town's
// sky bank: Orbis and Ludibrium shops, the Ludibrium maze, Rien's library. Those
// need naming one by one, and this is that list.
//
// Where a WHOLE art key turned out to be enclosed it was dropped from
// weather_skytable.inc instead, which is cheaper and self-maintaining. Kerning
// Square and the tree dungeons went that way, so their ids below are now redundant
// but harmless.
//
// SORTED ASCENDING. FieldHasSky binary-searches it, so the order is load bearing.
// Add ids in place; do not append.

    101000001,    // Victoria Road : Ellinia Weapon Store
    101000002,    // Victoria Road : Ellinia Department Store
    101000003,    // Victoria Road : Magic Library
    101020001,    // Victoria Road : The Tree Tunnel At the Forest Up North
    101020002,    // Victoria Road : Tree Dungeon, Forest Up North I
    101020003,    // Victoria Road : Tree Dungeon, Forest Up North II
    101020004,    // Victoria Road : Tree Dungeon, Forest Up North III
    101020005,    // Victoria Road : Tree Dungeon, Forest Up North IV
    101020006,    // Victoria Road : Tree Dungeon, Forest Up North V
    101020007,    // Victoria Road : Tree Dungeon, Forest Up North VI
    101020008,    // Victoria Road : Tree Dungeon, Forest Up North VII
    101020009,    // Victoria Road : Tree Dungeon, Forest Up North
    101020010,    // Victoria Road : Tree Dungeon, Forest Up North IX
    101030105,    // Victoria Road : Remains <Tomb> I
    101030106,    // Victoria Road : Remains <Tomb> II
    101030107,    // Victoria Road : Remains <Tomb> III
    101030108,    // Victoria Road : Remains <Tomb> IV
    101030110,    // Victoria Road : Camp 1
    101030111,    // Victoria Road : Camp 2
    101030112,    // Victoria Road : Camp 3
    101050100,    // Fairy Forest : Dark Cave Path
    102000001,    // Victoria Road : Perion Weapon Store
    102000002,    // Victoria Road : Perion Department Store
    102000003,    // Victoria Road : Warriors' Sanctuary
    103000001,    // Victoria Road : Kerning City Self-Defence Item Store
    103000002,    // Victoria Road : Kerning City Pharmacy
    103000003,    // Victoria Road : Thieves' Hideout
    103000004,    // Victoria Road : Naora Hospital
    103000005,    // Victoria Road : Kerning City Hair Salon
    103000006,    // Victoria Road : Kerning City Repair Shop
    103000100,    // Victoria Road : Subway Ticketing Booth
    103040000,    // Kerning Square  : Kerning Square Lobby
    103040100,    // Kerning Square  : 1st Floor 2nd Floor Area A
    103040101,    // Kerning Square  : 1st Floor 2nd Floor Area B
    103040102,    // Kerning Square  : 1st Floor 2nd Floor Area C
    103040103,    // Kerning Square  : 1st Floor 2nd Floor Area D
    103040200,    // Kerning Square  : 3rd Floor 4th Floor Area A
    103040201,    // Kerning Square  : 3rd Floor 4th Floor Area B
    103040202,    // Kerning Square  : 3rd Floor 4th Floor Area C
    103040203,    // Kerning Square  : 3rd Floor 4th Floor Area D
    103040300,    // Kerning Square  : 5th Floor 6th Floor Area A
    103040301,    // Kerning Square  : 5th Floor 6th Floor Area B
    103040302,    // Kerning Square  : 5th Floor 6th Floor Area C
    103040303,    // Kerning Square  : 5th Floor 6th Floor Area D
    103040400,    // Kerning Square  : 7th Floor 8th Floor Area A
    103040410,    // Kerning Square  : 7th Floor 8th Floor Area B
    103040420,    // Kerning Square  : 7th Floor 8th Floor Area C
    103040430,    // Kerning Square  : 7th Floor 8th Floor Area D
    103040440,    // Kerning Square  : VIP Zone Area A
    103040450,    // Kerning Square  : VIP Zone Area B
    103040460,    // Kerning Square  : VIP Zone Area C
    103050101,    // Victoria Road : Lady Syl's Room
    104000001,    // Victoria Road : Lith Harbor Armor Shop
    104000002,    // Victoria Road : Lith Harbor Department Store
    105040400,    // Dungeon : Sleepywood Hotel
    105040401,    // Dungeon : Regular Sauna
    105040402,    // Dungeon : VIP Sauna
    105050000,    // Dungeon : Ant Tunnel I
    105050100,    // Dungeon : Ant Tunnel II
    105050200,    // Dungeon : Ant Tunnel III
    105050300,    // Dungeon : Ant Tunnel IV
    105050400,    // Dungeon : Dark Cave
    105060000,    // Dungeon : Dangerous Steam
    105060100,    // Dungeon : Deep Ant Tunnel I
    105070000,    // Dungeon : Deep Ant Tunnel II
    105070001,    // Dungeon : Ant Tunnel Park
    105070002,    // Dungeon : The Grave of Mushmom
    105070100,    // Dungeon : The Cave of Evil Eye I
    105070200,    // Dungeon : The Cave of Evil Eye II
    105070300,    // Dungeon : The Cave of Evil Eye III
    105070400,    // Dungeon : The Cave of Evil Eye IV
    105080000,    // Dungeon : Drake Hunting Ground
    105090000,    // Dungeon : The Tunnel That Lost Light I
    105090100,    // Dungeon : The Tunnel That Lost Light II
    105090200,    // Dungeon : Another Entrance
    105090300,    // Dungeon : Drake's Meal Table
    105090301,    // Dungeon : Wild Cargo's Area
    105090310,    // Dungeon : Drake Area
    105090311,    // Dungeon : Cold Cradle
    105090312,    // Dungeon : Drake's Nest
    105090400,    // Dungeon : Another Path
    106020000,    // Mushroom Castle : Mushroom Forest Field
    106020100,    // Mushroom Castle : Secluded Mushroom Forest
    106020200,    // Mushroom Castle : Isolated Mushroom Forest
    106020300,    // Mushroom Castle : Deep Inside Mushroom Forest
    106020400,    // Mushroom Castle : Split Road of Destiny
    106020401,    // Mushroom Castle : Steep Downhill 1
    106020402,    // Mushroom Castle : Steep Downhill 2
    106020403,    // Mushroom Castle : Shadow Cliffs
    106020500,    // Mushroom Castle : Castle Wall Edge
    106020501,    // Mushroom Castle : Castle Wall Edge
    106020600,    // Mushroom Castle : Outer Castle Wall
    106020601,    // Mushroom Castle : On the Watch
    106020700,    // Mushroom Castle : Skyscraper 1
    106020800,    // Mushroom Castle : Skyscraper 2
    106020900,    // Mushroom Castle : West Castle Tower
    106021000,    // Mushroom Castle : Skyscraper 3
    106021001,    // Mushroom Castle : Security Room
    106021100,    // Mushroom Castle : Skyscraper 4
    106021200,    // Mushroom Castle : Skyscraper 5
    106021201,    // Mushroom Castle : Central Castle Tower
    106021300,    // Mushroom Castle : Skyscraper 6
    106021400,    // Mushroom Castle : East Castle Tower
    106021402,    // Mushroom Castle : The Last Castle Tower
    106021800,    // Mushroom Castle : Dead End
    120000101,    // The Nautilus : Navigation Room
    140000001,    // Snow Island : Lilin's Home
    140000010,    // Snow Island : Rien Library 1st Floor
    140000011,    // Snow Island : Rien Library 2nd Floor
    140000012,    // Snow Island : Rien Library 3rd Floor
    140030000,    // Snow Island : Mirror Cave
    140090000,    // Snow Island : Ice Cave
    180000000,    // Hidden Street : GM Room
    200000001,    // Orbis : Orbis Weapon Store
    200000002,    // Orbis : Orbis Department Store
    200000110,    // Orbis : Station Tunnel <To Ellinia>
    200000150,    // Orbis : Station Tunnel <To Ariant>
    200000201,    // Orbis Park : Orbis Plastic Surgery
    200000202,    // Orbis Park : Orbis Hair Salon
    200090001,    // During the Ride : Cabin <To Ellinia>
    200090011,    // During the Ride : Cabin <To Orbis>
    211000001,    // El Nath : Chief's Residence
    211000101,    // El Nath : El Nath Weapon Store
    211000102,    // El Nath : El Nath Department Store
    211041500,    // El Nath : Dead Mine I
    211041600,    // El Nath : Dead Mine II
    211041700,    // El Nath : Dead Mine III
    211041800,    // El Nath : Dead Mine IV
    211041900,    // El Nath : The Passage
    211042000,    // El Nath : The Cave of Trial I
    211042100,    // El Nath : The Cave of Trial II
    211042101,    // Hidden Street : Cave Within the Cave
    211042200,    // El Nath : The Cave of Trial III
    211042300,    // El Nath : The Door to Zakum
    211042400,    // El Nath : Entrance to Zakum Altar
    220000001,    // Ludibrium : Ludibrium Weapon Store
    220000002,    // Ludibrium : Ludibrium Pharmacy
    220000003,    // Ludibrium : Ludibrium Plastic Surgery
    220000004,    // Ludibrium : Ludibrium Hair Salon
    220000005,    // Ludibrium : Ludibrium Skin Care
    220000100,    // Ludibrium : Ludibrium Ticketing Place
    220000302,    // Ludibrium : Manager Karl's House
    220000303,    // Ludibrium : Tara and Sarah's House
    220000304,    // Ludibrium : Chloe's House
    220000307,    // Ludibrium : Mason's House
    220020600,    // Ludibrium : Toy Factory <Aparatus Room>
    221000001,    // Omega Sector : Tunnel
    221000200,    // Omega Sector : Silo
    222020400,    // Hidden Street : Time Control Room
    230000000,    // Aquarium : Aquarium
    230000001,    // Aquarium : The Center Hall
    230000002,    // Aquarium : Department Store
    230000003,    // Aquarium : Zoo
    230010000,    // Aqua Road : Ocean I.C
    230010001,    // Hidden Street : Penguin's Playground
    230010100,    // Aqua Road : Crystal Gorge
    230010200,    // Aqua Road : Red Coral Forest
    230010201,    // Aqua Road : Snowy Whale's Island
    230010300,    // Aqua Road : Turban Shell Hill
    230010400,    // Aqua Road : Forked Road : West Sea
    230020000,    // Aqua Road : Forked Road : East Sea
    230020100,    // Aqua Road : The Seaweed Tower
    230020101,    // Hidden Street : The Hidden Town
    230020200,    // Aqua Road : Sand Castle Playground
    230020201,    // Aqua Road : Two Palm Trees
    230020300,    // Aqua Road : Big Fish Valley
    230030000,    // Aqua Road : Blue Seaweed Road
    230030001,    // Hidden Street : Fish Resting Spot
    230030100,    // Aqua Road : Mushroom Coral Hill
    230030101,    // Aqua Road : Tae Gong's Ferry
    230030200,    // Aqua Road : The Sharp Unknown
    230040000,    // Aqua Road : Deep Sea Gorge I
    230040001,    // Aqua Road : Carta's Cave
    230040100,    // Aqua Road : Deep Sea Gorge II
    230040200,    // Aqua Road : Dangerous Sea Gorge I
    230040300,    // Aqua Road : Dangerous Sea Gorge II
    230040301,    // Aqua Road : A Small Cave
    230040400,    // Aqua Road : The Grave of a Wrecked Ship
    230040401,    // Aqua Road : A Small Wrecked Ship
    230040410,    // Aqua Road : The Dangerous Cave
    230040420,    // Aqua Road : The Cave of Pianus
    240000001,    // Leafre : Chief's House
    240000002,    // Leafre : Department Store
    240000003,    // Leafre : Yaku's House
    240000004,    // Leafre : Ito's House
    240000005,    // Leafre : Kumo's House
    240000006,    // Leafre : Pam's House
    240040700,    // Leafre : Cave of Life - Entrance
    240050000,    // Cave of Life : Cave Entrance
    240050100,    // Cave of Life : Room of Maze
    240050101,    // Cave of Life : 1st Room of Maze
    240050102,    // Cave of Life : 2nd Room of Maze
    240050103,    // Cave of Life : 3rd Room of Maze
    240050104,    // Cave of Life : 4th Room of Maze
    240050105,    // Cave of Life : 5th Room of Maze
    240050200,    // Cave of Life : Cave of Choice
    240050300,    // Cave of Life : Cave of Light
    240050310,    // Cave of Life : Cave of Darkness
    240050400,    // Cave of Life : Entrance to Horntail's Cave
    240050500,    // Cave of Life : Cave Exit
    240050600,    // Cave of Life : Cave : The Road in Between
    240060000,    // Cave of Life : The Cave of Trial I
    240060100,    // Cave of Life : The Cave of Trial II
    240060200,    // Cave of Life : Horntail's Cave
    250000001,    // Mu Lung : Tae Sang's House
    250000002,    // Mu Lung : Mu Lung Department Store
    250000003,    // Mu Lung : Mu Lung Hair Salon
    260010301,    // Hidden Street : Bellamoa's Cave
    261000001,    // Magatia : Home of the Missing Alchemist
    261000002,    // Magatia : Weapon & Armor Shop
    261000010,    // Magatia : Zenumist Society
    261000011,    // Magatia : Zenumist - Hidden Room
    261000020,    // Magatia : Alcadno Society
    261000021,    // Magatia : Alcadno - Hidden Room
    261040000,    // Hidden Street : Black Magician's Lab
    270010111,    // Time Lane : Memory Keeper's Room
    270020211,    // Time Lane : Sorcerer's Room
    270030411,    // Time Lane : Record Keeper's Room
    300000011,    // Camp Conference Room : Library
    300000012,    // Camp Conference Room : Cellar
    600010001,    // New Leaf City Town Street : NLC Subway Station
    670010750,    // Hidden Street : Stage 7 - Amos' Vault for Couples
    670010800,    // Hidden Street : Stage 7 - Amos' Vault
    680000001,    // Amoria : Amoria Wedding Shop
    680000002,    // Amoria : Amoria Hair Salon
    680000003,    // Amoria : Amoria Plastic Surgery
    680000100,    // Amoria : White Wedding Lounge
    680000110,    // Amoria : White Wedding Altar
    680000200,    // Amoria : Saint Maple Lounge
    680000210,    // Amoria : Saint Maple Altar
    680000401,    // Amoria : The Love Pinata
    682010100,    // Haunted House : Olivia's Secret Room 1
    682010101,    // Haunted House : Olivia's Secret Room 2
    682010102,    // Haunted House : Olivia's Secret Room 3
    800010100,    // Zipangu : Hall of Mushroom
    809050001,    // Ludibrium : Ludibrium Maze 2
    809050002,    // Ludibrium : Ludibrium Maze 3
    809050003,    // Ludibrium : Ludibrium Maze 4
    809050004,    // Ludibrium : Ludibrium Maze 5
    809050005,    // Ludibrium : Ludibrium Maze 6
    809050006,    // Ludibrium : Ludibrium Maze 7
    809050007,    // Ludibrium : Ludibrium Maze 8
    809050008,    // Ludibrium : Ludibrium Maze 9
    809050009,    // Ludibrium : Ludibrium Maze 10
    809050010,    // Ludibrium : Ludibrium Maze 11
    809050011,    // Ludibrium : Ludibrium Maze 12
    809050012,    // Ludibrium : Ludibrium Maze 13
    809050013,    // Ludibrium : Ludibrium Maze 14
    809050014,    // Ludibrium : Ludibrium Maze 15
    809050015,    // Ludibrium : Ludibrium Maze 16
    809050016,    // Ludibrium : Exit of the Maze
    809050017,    // Ludibrium : Exit of the Maze
    920010500,    // Hidden Street : Tower of Goddess <Sealed Room>
    920010600,    // Hidden Street : Tower of Goddess <Lounge>
    920010601,    // Hidden Street : Tower of Goddess <Room 301>
    920010602,    // Hidden Street : Tower of Goddess <Room 302>
    920010603,    // Hidden Street : Tower of Goddess <Room 303>
    922000010,    // Hidden Street : Doll's House
    924010000,    // Hidden Street : Cave of Black Witches
    924010100,    // Hidden Street : Cave of Black Witches
    924010200,    // Hidden Street : Cave of Black Witches
    926010010,    // Hidden Street : Tomb of Pharaoh Yeti
    926010070,    // Hidden Street : Tomb of Pharaoh Yeti
    990000420,    // Sharenian : Room of Courage
