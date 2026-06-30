# Character 分类数据库/职业范围扫描

口径：
- `String.wz/Eqp.img.xml`：服务端 `ItemInformationProvider.getName/getAllItems()` 的装备名称来源，作为“数据库/可搜索物品名”主口径。
- `handbook/Equip/*.txt`：GM `!id`/静态手册类查询文件，作为辅助口径。
- “当前职业装备池”：按 `EquipMetadataCache` / `ItemInformationProviderUtilities` 当前硬编码范围，主要是 v83 五大职业及公共装备；不含外观 Body/Head/Hair/Face，也不含未来职业武器段。

## 汇总

| 分类 | Character资源数 | 不在String.wz(Eqp) | 不在handbook | 不在当前职业装备池/reqJob异常 |
|---|---:|---:|---:|---:|
| Body | 0 | 0 | 0 | 0 |
| Head | 0 | 0 | 0 | 0 |
| Hair | 15627 | 2319 | 14111 | 15627 |
| Face | 6162 | 137 | 5622 | 6162 |
| Cap | 3387 | 476 | 2475 | 2104 |
| Coat | 733 | 6 | 270 | 3 |
| Longcoat | 2207 | 272 | 1721 | 972 |
| Pants | 620 | 13 | 214 | 118 |
| Shoes | 1340 | 109 | 921 | 710 |
| Glove | 619 | 17 | 383 | 365 |
| Cape | 1008 | 68 | 830 | 783 |
| Shield | 143 | 6 | 86 | 81 |
| Weapon | 5261 | 1455 | 4083 | 4206 |
| FaceAcc | 579 | 15 | 441 | 413 |
| Glass | 232 | 5 | 142 | 138 |
| Earring | 273 | 10 | 206 | 202 |

## 分类备注

- Body、Head：当前服务端 `gms-server/wz/Character.wz` 目录为空；如果客户端工具里显示，是角色基础外观资源，不是装备物品。
- Hair、Face：属于发型/脸型外观，不是装备池。它们很多不在 `String.wz/Eqp`，也不会按装备刷出。
- FaceAcc、Glass、Earring：实际来自 `Character.wz/Accessory`，按 ID 段拆分：101=FaceAcc，102=Glass，103=Earring。
- Weapon：当前职业装备池只认 130/131/132/133/137/138/140/141/142/143/144/145/146/147/148/149 段；121/122/123/124/152/153/154/155/156/157/158/159/170 等段会被标为不属于当前职业装备池。

## 完整明细文件

- 全量：`tool/reports/character_category_db_scan.csv`
- 不在 String.wz/Eqp：`tool/reports/character_missing_string_eqp.csv`
- 不在 handbook：`tool/reports/character_missing_handbook.csv`
- 不在当前职业装备池：`tool/reports/character_outside_current_equip_pool.csv`

## 不在当前职业装备池的 ID 段摘要

- Hair: 15627 (300xxx=80, 301xxx=80, 302xxx=80, 303xxx=80, 304xxx=80, 305xxx=80, 306xxx=80, 307xxx=80, 308xxx=80, 309xxx=82, 310xxx=80, 311xxx=80, 312xxx=80, 313xxx=80, 314xxx=80, 315xxx=80, 316xxx=80, 317xxx=80, 318xxx=80, 319xxx=80, 320xxx=80, 321xxx=80, 322xxx=80, 323xxx=80, 324xxx=80, 325xxx=80, 326xxx=80, 327xxx=80, 328xxx=80, 329xxx=80, 330xxx=80, 331xxx=80, 332xxx=80, 333xxx=80, 334xxx=80, 335xxx=80, 336xxx=80, 337xxx=80, 338xxx=80, 339xxx=80, 340xxx=80, 341xxx=80, 342xxx=80, 343xxx=80, 344xxx=80, 345xxx=80, 346xxx=80, 347xxx=80, 348xxx=80, 349xxx=80, 350xxx=80, 351xxx=80, 352xxx=80, 353xxx=80, 354xxx=80, 355xxx=80, 356xxx=80, 357xxx=80, 358xxx=80, 359xxx=80, 360xxx=80, 361xxx=80, 362xxx=80, 363xxx=80, 364xxx=80, 365xxx=80, 366xxx=80, 367xxx=80, 368xxx=80, 369xxx=80, 370xxx=80, 371xxx=80, 372xxx=80, 373xxx=80, 374xxx=80, 375xxx=80, 376xxx=80, 377xxx=80, 378xxx=80, 379xxx=80, 380xxx=80, 381xxx=81, 382xxx=80, 383xxx=80, 384xxx=80, 385xxx=80, 386xxx=80, 387xxx=80, 388xxx=80, 389xxx=80, 390xxx=80, 391xxx=80, 392xxx=80, 393xxx=80, 394xxx=80, 395xxx=80, 396xxx=80, 397xxx=80, 398xxx=80, 399xxx=80, 400xxx=80, 401xxx=24, 402xxx=40, 403xxx=80, 404xxx=80, 405xxx=80, 406xxx=80, 407xxx=80, 408xxx=80, 409xxx=80, 410xxx=32, 411xxx=64, 412xxx=24, 413xxx=48, 414xxx=80, 415xxx=72, 416xxx=80, 417xxx=80, 418xxx=80, 419xxx=80, 420xxx=72, 421xxx=40, 430xxx=24, 431xxx=64, 432xxx=72, 433xxx=80, 434xxx=32, 435xxx=24, 436xxx=80, 437xxx=64, 438xxx=56, 439xxx=32, 440xxx=80, 441xxx=80, 442xxx=16, 443xxx=80, 444xxx=80, 445xxx=80, 446xxx=24, 447xxx=24, 448xxx=72, 449xxx=64, 450xxx=80, 451xxx=56, 452xxx=64, 453xxx=80, 454xxx=64, 455xxx=64, 456xxx=72, 457xxx=72, 458xxx=64, 459xxx=40, 460xxx=80, 461xxx=64, 462xxx=40, 463xxx=72, 464xxx=80, 465xxx=72, 466xxx=80, 467xxx=80, 468xxx=80, 469xxx=72, 470xxx=80, 471xxx=48, 472xxx=32, 473xxx=80, 474xxx=56, 475xxx=64, 476xxx=80, 477xxx=80, 478xxx=72, 479xxx=80, 480xxx=80, 481xxx=64, 482xxx=32, 483xxx=64, 484xxx=72, 485xxx=80, 486xxx=80, 487xxx=72, 488xxx=80, 489xxx=72, 600xxx=80, 601xxx=80, 602xxx=80, 603xxx=80, 604xxx=72, 605xxx=64, 606xxx=72, 607xxx=64, 608xxx=56, 609xxx=80, 610xxx=80, 611xxx=80, 612xxx=80, 613xxx=80, 614xxx=80, 615xxx=72, 616xxx=64, 617xxx=80, 618xxx=64, 619xxx=80, 630xxx=72, 631xxx=72, 632xxx=40, 633xxx=8, 634xxx=16, 640xxx=72, 641xxx=80, 642xxx=48, 643xxx=80, 644xxx=72, 645xxx=56, 646xxx=72, 647xxx=48, 649xxx=16, 680xxx=56)
- Face: 6162 (200xxx=98, 201xxx=95, 202xxx=95, 203xxx=95, 204xxx=95, 205xxx=95, 206xxx=95, 207xxx=95, 208xxx=94, 210xxx=98, 211xxx=96, 212xxx=96, 213xxx=96, 214xxx=96, 215xxx=96, 216xxx=96, 217xxx=96, 218xxx=93, 222xxx=1, 230xxx=90, 231xxx=90, 232xxx=90, 233xxx=90, 234xxx=90, 235xxx=90, 236xxx=90, 237xxx=90, 238xxx=80, 240xxx=88, 241xxx=86, 242xxx=86, 243xxx=86, 244xxx=86, 245xxx=86, 246xxx=86, 247xxx=86, 248xxx=74, 250xxx=94, 251xxx=95, 252xxx=95, 253xxx=95, 254xxx=95, 255xxx=95, 256xxx=95, 257xxx=95, 258xxx=71, 260xxx=88, 261xxx=89, 262xxx=89, 263xxx=89, 264xxx=90, 265xxx=89, 266xxx=89, 267xxx=89, 268xxx=70, 270xxx=71, 271xxx=71, 272xxx=71, 273xxx=71, 274xxx=71, 275xxx=71, 276xxx=71, 277xxx=71, 278xxx=48, 280xxx=72, 281xxx=72, 282xxx=72, 283xxx=72, 284xxx=72, 285xxx=72, 286xxx=72, 287xxx=72, 288xxx=46, 500xxx=2, 501xxx=2, 502xxx=2, 503xxx=2, 504xxx=2, 505xxx=2, 506xxx=2, 507xxx=2, 508xxx=2, 510xxx=1, 511xxx=1, 512xxx=1, 513xxx=1, 514xxx=1, 515xxx=1, 516xxx=1, 517xxx=1, 518xxx=1)
- Cap: 2104 (100xxx=2104)
- Coat: 3 (104xxx=3)
- Longcoat: 972 (100xxx=1, 105xxx=971)
- Pants: 118 (106xxx=118)
- Shoes: 710 (100xxx=1, 107xxx=709)
- Glove: 365 (108xxx=365)
- Cape: 783 (110xxx=783)
- Shield: 81 (109xxx=79, 119xxx=2)
- Weapon: 4206 (109xxx=1, 124xxx=67, 125xxx=86, 126xxx=49, 127xxx=41, 128xxx=41, 129xxx=37, 130xxx=179, 131xxx=114, 132xxx=134, 133xxx=148, 134xxx=99, 135xxx=342, 136xxx=123, 137xxx=133, 138xxx=154, 139xxx=6, 140xxx=177, 141xxx=96, 142xxx=102, 143xxx=128, 144xxx=133, 145xxx=142, 146xxx=128, 147xxx=126, 148xxx=142, 149xxx=144, 150xxx=11, 151xxx=11, 152xxx=1, 158xxx=12, 159xxx=38, 160xxx=8, 169xxx=63, 170xxx=990)
- FaceAcc: 413 (101xxx=413)
- Glass: 138 (102xxx=138)
- Earring: 202 (103xxx=202)
