// Render parameters for every sky, one row per WeatherProfile.
//
// THE ORDER IS THE WIRE FORMAT. Row N is profile id N, and the ids are defined by
// server/server/weather/WeatherProfile.java. Nothing but that comment
// and this one keeps the two ends equal: insert a row in the middle and every
// existing sky shifts by one.
//
// The server knows only the id and the name. Everything about what a sky LOOKS like
// lives here, which is why adding a purely visual variant needs no server change.
//
//  cloud   0..1  target alpha of the three scrolling cloud sheets
//  rain    0..1  target alpha of the four falling rain sheets
//  native  BlowWeather item id, 0 for none. Every id here was verified present in
//          this client's Item/Cash/0512.img (see IMPLEMENTATION.md).
//          5120999, 5120998, 5120997, 5120996 and 5120995 are NOT stock items. They are art pointers into
//          Client/Data/Effect/WeatherParticles.img, added by add_weather_items.py
//          and built by build_weather_particles.py. They exist because the stock
//          nodes are SHARED: weather/flower is also Floral Fest and Rookie Floral Fest,
//          weather/maple is also item 5120248, and weather/snow is Blizzard AND plain
//          Snow, so restyling any in place would hit the others. blizzardSnow is the same
//          flake with a `count` of 280 rather than the default 100, which is 84..151
//          particles against 30..54.
//          BlowWeather reads only info/path and info/type, and info/path is a full ResMan
//          path, which is why the art lives in its own file and MapHelper.img is never
//          touched. All five are deliberately absent from the server's item data.
//  R G B   the night tint this sky fades toward. Lower is darker.
//  boost   0..1  extra darkening applied REGARDLESS of the time of day, so an
//          overcast noon is dim. This is the thing the old three-scalar model could
//          not express at all.
//  fade    per-frame step toward the target. 0.015 is about 2 s; storms roll in
//          slower than they clear.
//  snd     which ambient loop plays: 0 none, 1 rain, 2 wind. The windy skies are the
//          ones with cloud but nothing falling, plus the two that blow things around.
//
//        name        cloud  rain  native    R     G     B    boost  fade    snd
/* 0 */ { L"clear",    0.00f, 0.00f,       0, 0x4A, 0x5A, 0x8C, 0.00f, 0.015f, 0 },
/* 1 */ { L"rain",     0.85f, 1.00f,       0, 0x42, 0x50, 0x78, 0.18f, 0.015f, 1 },
// SNOW IS THE ONE FALLING SKY WITH NO NATIVE ITEM. It draws two imported sheets
// instead, injected by weatherfx.cpp as g_aSnow and faded on g_fSnowLevel: a far
// plane behind the map and a near one in front of the player. The particle blower
// cannot express that, because it picks a variant per particle at random, so size,
// brightness and fall speed come out uncorrelated and the depth reads as noise.
// 5120995 (snowFall) is consequently unreferenced now. It is left in the art pointer
// set rather than deleted: the blizzard still blows 5120997 out of the same file, and
// an id removed from Item/Cash/0512.img is the sort of change that strands a profile
// row on an info node that no longer resolves.
/* 2 */ { L"snow",     0.70f, 0.00f,       0, 0x60, 0x6A, 0x92, 0.10f, 0.015f, 0 },
/* 3 */ { L"overcast", 1.00f, 0.00f,       0, 0x58, 0x5E, 0x74, 0.22f, 0.012f, 2 },
/* 4 */ { L"storm",    1.00f, 1.00f,       0, 0x30, 0x38, 0x58, 0.38f, 0.008f, 1 },
// THE BLIZZARD KEEPS ITS PARTICLE AND GAINS A SHEET, unlike snow, which swapped one
// for the other. The imported veil peaks at alpha 102 of 255 and is soft, blurred,
// diagonal streaks: it reads as air full of driven snow, and on its own it would make
// a blizzard LESS violent than the plain snow beside it, which is backwards. The 280
// count particle stays as the hard near flakes, the sheet is the blur behind them, and
// the fog is what you cannot see through. Three layers, three jobs.
//
// To make the sheet exclusive instead, set this to 0 and nothing else changes.
/* 5 */ { L"blizzard", 1.00f, 0.00f, 5120997, 0x6E, 0x76, 0x9C, 0.28f, 0.010f, 2 },
/* 6 */ { L"leaves",   0.35f, 0.00f, 5120998, 0x54, 0x54, 0x82, 0.04f, 0.015f, 2 },
/* 7 */ { L"blossom",  0.30f, 0.00f, 5120999, 0x50, 0x5C, 0x8E, 0.02f, 0.015f, 2 },
// The sandstorm is the one sky that also swaps the BACKDROP: weatherfx.cpp fades in
// nightDesert back/19, a dust choked orange sky, over the map's own. Everything else here
// is ordinary. The tint is warm rather than cold, which no other sky is, and the boost is
// the second highest after a storm because a sandstorm is dark in the middle of the day.
// Cloud stays at 0: the swapped backdrop IS the overcast, and adding the white cloud
// sheets on top of it read as fog rather than as dust.
/* 8 */ { L"sandstorm", 0.00f, 0.00f, 5120996, 0x9E, 0x74, 0x46, 0.34f, 0.009f, 2 },
