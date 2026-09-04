#include "pch.h"
#include "wvs/util.h"

int get_screen_width() {
    IWzGr2DPtr& gr = get_gr();
    return gr ? static_cast<int>(gr->Getwidth()) : 800;
}

int get_screen_height() {
    IWzGr2DPtr& gr = get_gr();
    return gr ? static_cast<int>(gr->Getheight()) : 600;
}
