/* Only reads the bounded native table; candidate pointers live in the caller frame. */
typedef unsigned char byte;
typedef unsigned int word;

static word slot_key(byte *candidate) {
    word key = *(unsigned short *)(candidate + 0x86);
    if (key) return key;
    /* Legacy servers sent zero in the reserved slot field. */
    key = *(word *)candidate / 10000;
    return key >= 130 ? 130 : key;
}

static int priority(byte *candidate, word hovered) {
    return candidate[4] ? 2 : (*(word *)candidate == hovered ? 1 : 0);
}

word collect_slots(byte *image, word matched, word hovered, byte **out) {
    byte *table = image + 0x18c9c0;
    word set = *(word *)(table + matched), count = 0;
    word views = *(word *)(image + 0xa8b0);
    if (views > 96) views = 96;
    for (word view = 0; view < views; ++view) {
        byte *panel = table + view * 0x4058;
        if (*(word *)panel != set) continue;
        word slots = *(word *)(panel + 0x68);
        if (slots > 8) slots = 8;
        for (word slot = 0; slot < slots; ++slot) {
            byte *row = panel + slot * 0x554;
            word alternatives = *(word *)(row + 0x6c);
            if (alternatives > 10) alternatives = 10;
            for (word alt = 0; alt < alternatives; ++alt) {
                byte *candidate = row + 0x70 + alt * 0x88;
                word key = slot_key(candidate), index = 0;
                while (index < count && slot_key(out[index]) != key) ++index;
                if (index == count) {
                    if (count == 96 * 8) return count;
                    out[count++] = candidate;
                }
                else if (priority(candidate, hovered) > priority(out[index], hovered))
                    out[index] = candidate;
            }
        }
    }
    return count;
}
