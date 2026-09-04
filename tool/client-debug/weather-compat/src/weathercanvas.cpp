#include "pch.h"
#include "weathercanvas.h"
#include "debug.h"
#include "wvs/util.h"
#include "ztl/ztl.h"
#include <vector>
#include <algorithm>

// Building new sprites at runtime, from sprites the map already has.
//
// Two features need it and neither can be done any other way. A cast shadow is the
// object's own silhouette sheared onto the ground, and a swaying plant is that same
// object sheared a few degrees each way: IWzGr2DLayer can offset, mirror, tint and set a
// rect, but it cannot SHEAR, so the lean has to exist in the pixels.
//
// THE FAST PATH IS _LockAddress. It hands back the raw pixel buffer and its pitch, so a
// whole sprite is one lock, a loop over memory, and one unlock. The alternative, Getpixel,
// is a COM call PER PIXEL: a 300x300 object is 90000 calls, and there can be sixty of them
// on a map.
//
// THE FALLBACK IS CopyEx, which takes a destination SIZE and a source RECT and therefore
// scales. A shear is then one row-copy per source row, each nudged sideways. It needs no
// pixel access at all, and it costs the soft edge, because there is no way to blur through
// a blit. Nothing in this DLL had ever called _LockAddress before this, which is exactly
// why the fallback exists rather than being assumed unnecessary.

#define ADDR_NONE 0

namespace {

// A locked canvas. Non-copyable, unlocks itself, and reports whether the lock actually
// produced a usable address rather than merely succeeding.
//
// The buffer lives on IWzRawCanvas, NOT on IWzCanvas: two separate interfaces on the same
// object, and only the raw one has _LockAddress. Everything else here, Create, CopyEx,
// width and height, is on IWzCanvas, so both are needed and this is the bridge.
// Master switch for the raw-pixel shearing path. See WeatherCanvas_HasPixelPath for why
// it defaults to 0 and what turning it on buys.
#ifndef WEATHER_PIXEL_PATH_ENABLED
#define WEATHER_PIXEL_PATH_ENABLED 0
#endif

struct CanvasLock {
    IWzRawCanvasPtr p;
    unsigned char* pBits = nullptr;
    int nPitch = 0;
    // Whether raw__LockAddress actually SUCCEEDED, which is not the same as whether p is
    // valid. Unlock must be called exactly once per successful lock and never otherwise:
    // this struct previously unlocked on a canvas it had failed to lock, and unlocked
    // twice when the variant test rejected the address. Both were harmless only because
    // the QueryInterface above always failed, so p was always null and Unlock always
    // returned immediately. Fixing the QI turned two latent unbalanced unlocks into live
    // ones, which hangs the renderer.
    bool bLocked = false;

    // bWant is the CALLER's opt-in. A lock is only ever acquired for a caller that
    // genuinely needs pixels, so a caller that does not is guaranteed the blit path.
    CanvasLock(IWzCanvasPtr c, bool bWant) {
        if (!c || !bWant) {
            return;
        }
#if !WEATHER_PIXEL_PATH_ENABLED
        // A KILL SWITCH over the per-call opt-in above, kept because this path has broken
        // the client twice. Set it to 0 and every caller gets CopyEx and shadows turn off,
        // whatever they asked for.
        //
        // It lives HERE and not only in WeatherCanvas_HasPixelPath, because Project decides
        // by lkS.ok() && lkD.ok() and never asks that function: gating only there left the
        // raw path fully live for every sway sprite, which is what corrupted Leafre.
        return;
#else

        // get_rawCanvas, NOT QueryInterface. Canvas.dll's canvas coclass does not
        // implement IWzRawCanvas at all -- its ATL interface map holds only IWzCanvas, one
        // private interface and IUnknown -- so the QI returned E_NOINTERFACE every time
        // and this whole struct could never produce a buffer. The raw canvas is a
        // SEPARATE object, reached only through this accessor. Same call another module in this DLL
        // has been using successfully.
        try {
            IWzRawCanvas* raw = nullptr;
            if (FAILED(c->get_rawCanvas(0, 0, &raw)) || !raw) {
                return;
            }
            p.Attach(raw);      // takes the reference get_rawCanvas handed out
        } catch (const _com_error&) {
            return;
        }
        try {
            int pitch = 0;
            VARIANT v;
            VariantInit(&v);
            if (FAILED(p->raw__LockAddress(&pitch, &v))) {
                return;             // never locked: Unlock must not run
            }
            bLocked = true;
            // VT_BYREF|VT_UI4 (0x4013) is what every _LockAddress in this client actually
            // returns: Canvas.dll builds it with `and eax, 0x4013` at 0x50006C1B and
            // Gr2D_DX8.dll writes the literal at 0x50406E35. Testing for a bare VT_I4 /
            // VT_UI4 / VT_INT therefore matched nothing, which is the second reason the
            // pixel path was dead. lVal and byref are the same union slot on win32, and
            // the client's own consumer at 0x005DAA43 reads that slot straight as the
            // buffer, so both spellings are accepted.
            unsigned char* bits = nullptr;
            const int vt = V_VT(&v) & VT_TYPEMASK;
            if (vt == VT_I4 || vt == VT_UI4 || vt == VT_INT || vt == VT_UINT) {
                bits = (V_VT(&v) & VT_BYREF)
                     ? reinterpret_cast<unsigned char*>(V_BYREF(&v))
                     : reinterpret_cast<unsigned char*>((uintptr_t)(unsigned int)V_I4(&v));
            }
            if (bits && pitch > 0) {
                pBits = bits;
                nPitch = pitch;
            } else {
                Unlock();
            }
        } catch (const _com_error&) {
            pBits = nullptr;
            nPitch = 0;
        }
#endif
    }
    ~CanvasLock() { Unlock(); }
    CanvasLock(const CanvasLock&) = delete;
    CanvasLock& operator=(const CanvasLock&) = delete;

    bool ok() const { return pBits != nullptr && nPitch > 0; }

    void Unlock() {
        if (!p || !bLocked) {
            return;
        }
        // Cleared FIRST, so a throw below cannot leave the flag set for the destructor to
        // unlock a second time.
        bLocked = false;
        // NULL, exactly as the client's own consumer does at 0x005DAA9C. Passing a zeroed
        // RECT is not the same thing: it names an empty dirty region.
        try {
            p->raw__UnlockAddress(nullptr);
        } catch (const _com_error&) {
        }
        pBits = nullptr;
        nPitch = 0;
    }
};

// Column running totals for the vertical blur pass. Reused for the same reason vAcc and
// vTmp are, and for the same thread.
static std::vector<int>& ColScratch(int dw) {
    static std::vector<int> v;
    if ((int)v.size() < dw) {
        v.assign((size_t)dw, 0);
    }
    return v;
}

}  // namespace


// Can this client generate sprites AT ALL? That is a different question from whether it
// hands out a raw pixel buffer, and conflating the two is what silently disabled the
// whole foliage bend.
//
// WeatherCanvas_Project has two ways to shear: writing pixels through _LockAddress, and
// blitting one source row at a time with CopyEx. The blit path needs no buffer, produces
// the same geometry, and for a SWAY -- which keeps the source's own colours and wants a
// hard edge anyway -- it is not a downgrade at all. It is only a downgrade for a shadow,
// which needs to accumulate a silhouette and soften it.
//
// This used to return false whenever the lock failed, so on a client whose Gr2D hands out
// no buffer the sway decided it was unusable and fell back to translating the whole plant
// sideways. That is the "it slides instead of bending" report, and no amount of pivot or
// amplitude work could have fixed it.
bool WeatherCanvas_Probe() {
    static int s_nResult = -1;
    if (s_nResult >= 0) {
        return s_nResult != 0;
    }
    s_nResult = 0;
    IWzCanvasPtr probe;
    try {
        PcCreateObject<IWzCanvasPtr>(L"Canvas", probe, nullptr);
        if (!probe) {
            LOG_ONCE("weathercanvas: cannot create a Canvas; generated sprites are off");
            return false;
        }
        probe->Create(8, 8, 0, CANVAS_PIXFORMAT::CP_A8R8G8B8);
    } catch (const _com_error&) {
        LOG_ONCE("weathercanvas: Canvas::Create threw; generated sprites are off");
        return false;
    }
    s_nResult = 1;          // a canvas exists: the CopyEx path is available
    return true;
}

// Can it hand out a raw pixel buffer? Only the paths that ACCUMULATE need this: a shadow
// has to build a silhouette and blur it, which CopyEx cannot do.
bool WeatherCanvas_HasPixelPath() {
    static int s_nResult = -1;
    if (s_nResult >= 0) {
        return s_nResult != 0;
    }
    s_nResult = 0;
#if !WEATHER_PIXEL_PATH_ENABLED
    // Held off by the kill switch.
    //
    // The lock genuinely works once get_rawCanvas replaces the QueryInterface that could
    // never succeed. But turning it on activates a branch of WeatherCanvas_Project that
    // had never executed in the lifetime of this client, and the first in-game test of it
    // hung on Leafre -- the map that drives the most Project calls, through the biggest
    // canvases, on its tree backs. Two unbalanced-unlock defects in CanvasLock have since
    // been fixed and are the likeliest cause, but that is a hypothesis, not a verified
    // result, and a hang is not an acceptable thing to ship on a hypothesis.
    //
    // With this off, sway and the Leafre backs take the CopyEx path they have always
    // taken and cast shadows stay off, exactly as before this review. Every other fix in
    // the weather system is unaffected.
    //
    // TO TEST IT: build with WEATHER_PIXEL_PATH_ENABLED=1, then walk into Leafre and
    // Henesys. What it buys is soft-edged cast shadows and alpha-scanned sway pivots.
    LOG_ONCE("weathercanvas: pixel path held off by WEATHER_PIXEL_PATH_ENABLED; shearing "
             "through CopyEx and casting no shadows");
    return false;
#else
    if (!WeatherCanvas_Probe()) {
        return false;
    }
    IWzCanvasPtr probe;
    try {
        PcCreateObject<IWzCanvasPtr>(L"Canvas", probe, nullptr);
        if (!probe) {
            return false;
        }
        probe->Create(8, 8, 0, CANVAS_PIXFORMAT::CP_A8R8G8B8);
    } catch (const _com_error&) {
        return false;
    }
    CanvasLock lk(probe, true);
    s_nResult = lk.ok() ? 1 : 0;
    if (s_nResult) {
        DEBUG_MESSAGE("weathercanvas: _LockAddress works, pitch %d; using the pixel path",
                      lk.nPitch);
    } else {
        LOG_ONCE("weathercanvas: _LockAddress gave no buffer; shearing through CopyEx "
                 "instead, which cannot soften an edge");
    }
    return s_nResult != 0;
#endif
}


IWzCanvasPtr WeatherCanvas_Project(IWzCanvasPtr pSrc, const PROJECT& cfg, POINT* pAnchor,
                                   int* pnBaseRow) {
    if (!pSrc || !pAnchor) {
        return nullptr;
    }
    int sw = 0, sh = 0;
    try {
        sw = pSrc->width;
        sh = pSrc->height;
    } catch (const _com_error&) {
        return nullptr;
    }
    if (sw <= 0 || sh <= 0 || sw > 2048 || sh > 2048) {
        return nullptr;
    }

    // The WHOLE sprite, kept before the window narrows sw/sh. CopyEx source coordinates
    // are in the sprite's own space whatever window we are drawing, so the clear pixel is
    // bounded against this and not against the window.
    const int nFullW = sw, nFullH = sh;

    // The source WINDOW. Everything below measures from here, so a caller that asked for
    // one plant out of a four plant sprite gets a canvas the size of that plant and a
    // pivot at that plant's own base, rather than the bitmap's.
    int sx0 = 0, sy0 = 0;
    if (cfg.rcSrc.right > cfg.rcSrc.left && cfg.rcSrc.bottom > cfg.rcSrc.top) {
        const int wx0 = (cfg.rcSrc.left < 0) ? 0 : (int)cfg.rcSrc.left;
        const int wy0 = (cfg.rcSrc.top < 0) ? 0 : (int)cfg.rcSrc.top;
        const int wx1 = (cfg.rcSrc.right > sw) ? sw : (int)cfg.rcSrc.right;
        const int wy1 = (cfg.rcSrc.bottom > sh) ? sh : (int)cfg.rcSrc.bottom;
        if (wx1 - wx0 >= 2 && wy1 - wy0 >= 2) {
            sx0 = wx0; sy0 = wy0;
            sw = wx1 - wx0;
            sh = wy1 - wy0;
        }
    }

    // A point h above the base lands at (x + h*L, base - h*S). L is the lean and S the
    // squash, so the output is as wide as the sprite plus however far the top of it
    // travels, and as tall as the squashed sprite.
    const float L = cfg.fLean;

    const float S = (cfg.fSquash > 0.02f) ? cfg.fSquash : 0.02f;

    // WHERE THE PIVOT IS, and this is the difference between a plant that sways and a
    // plant that slides.
    //
    // Pivoting on the canvas BOTTOM only roots the sprite if the plant reaches it, and
    // most do not: a bush sits in a box with transparent padding underneath, so shearing
    // about the box bottom lifts the visible base off the ground and swings it. The pivot
    // has to be the lowest row that actually has pixels in it.
    //
    // Found by scanning the source's alpha, which means it needs the lock. Without one
    // the fallback below pivots on the canvas bottom and a padded sprite will drift, which
    // is one more reason the blit path is a standby rather than an equal.
    // Told, or found, or the canvas bottom as a last resort.
    int nBaseRow = sh - 1;
    if (cfg.nPivotRow >= 0 && cfg.nPivotRow < sh) {
        nBaseRow = cfg.nPivotRow;
    }

    // HOW MUCH OF THE PLANT BENDS, as opposed to how far its top travels.
    //
    // A straight shear moves a row in proportion to its height, so at half height a plant
    // has moved half as far as its tip. On something with a long bare stem and a heavy top
    // -- a sunflower -- that reads as a head waving on a rigid pole: the stem IS moving,
    // just too little to see against its own length.
    //
    // Raising the height ratio to a power below 1 lifts the middle without touching the
    // tip: at half height, 0.5^0.72 is 0.61, so the mid-stem travels 23% further than a
    // straight shear puts it while the head lands in exactly the same place. The result is
    // a bow rather than a lean, which is also what a stem in wind actually does.
    //
    // NOT applied to a stacked segment or to a hanging rope. nBaseOffset stacking works
    // precisely because the shear is linear -- each segment's bottom lands where the one
    // below's top did -- and a curve breaks that join, which is a ladder coming apart.
    const float kBow = 0.72f;
    const bool bBow = (cfg.nBaseOffset == 0) && !cfg.bHangFromTop && cfg.bKeepColour;
    const float fBowH = (float)((nBaseRow > 0) ? nBaseRow : 1);
    auto LeanAt = [&](float hLean) -> float {
        if (!bBow || hLean <= 0.0f) {
            return hLean * L;
        }
        const float t = hLean / fBowH;
        return fBowH * powf((t > 1.0f) ? 1.0f : t, kBow) * L;
    };
    const int nPad = (cfg.nPadOverride > 0)
                   ? cfg.nPadOverride
                   : (int)(fabsf(L) * (float)(sh + cfg.nBaseOffset)) + 4;
    const int dw = sw + nPad * 2;
    const int dh = (int)((float)sh * S) + 4;
    if (dw <= 0 || dh <= 0 || dw > 4096 || dh > 1024) {
        return nullptr;
    }

    IWzCanvasPtr pDst;
    try {
        PcCreateObject<IWzCanvasPtr>(L"Canvas", pDst, nullptr);
        if (!pDst) {
            return nullptr;
        }
        pDst->Create(dw, dh, 0, CANVAS_PIXFORMAT::CP_A8R8G8B8);
        // CLEAR IT. Create() does not promise a zeroed buffer, and the allocator hands
        // back recycled memory, which here is usually the frames just freed.
        //
        // HERE, once, rather than inside a branch: not every path below writes every
        // pixel. The bKeepColour path writes only the sheared band, so with a pad of n it
        // leaves n uncleared columns down each side and a few rows top and bottom, and a
        // swayed plant renders inside a frozen ghost of a previous lean. That path was
        // unreachable until the raw-canvas lock started working, so the blit branch's own
        // stretch-clear was covering for it.
        //
        // 0x00FFFFFF, NOT 0. Colour 0 clears nothing: Canvas.dll's A8R8G8B8 fill at
        // 0x50009BE2 branches on alpha, and for alpha 0 it stores the pixel it just
        // loaded straight back. 0x00FFFFFF is the reserved sentinel the dispatcher at
        // 0x50009B8C converts into a rep stosd of zero. This tree had already measured
        // that three times (in three unrelated modules) and
        // two avatar sway modules both carried the same bug, now fixed with it.
        pDst->raw_DrawRectangle(0, 0, dw, dh, 0x00FFFFFF);
    } catch (const _com_error&) {
        return nullptr;
    }

    // The pivot's row in the output, with room BELOW it for whatever the sprite has
    // beneath the pivot.
    //
    // This used to be dh - 2, the bottom of the canvas, which works only when the pivot is
    // the lowest row of the sprite. It is not: a prop that bends from partway up has real
    // art below the pivot, and with a fixed bottom every one of those rows had nowhere to
    // land and was clamped onto the same output line -- so the bottom half of a hay bale
    // collapsed into a single row and read as missing. Anchoring on the pivot gives the
    // rows below it their own space.
    const int nBaseY = (int)((float)nBaseRow * S) + 2;
    pAnchor->x = nPad;          // where the source's left edge is in the output
    pAnchor->y = nBaseY;        // where the source's BASE is in the output

    // THE SOURCE IS USUALLY NOT A8R8G8B8. Every canvas in acc1.img -- all 1124 of them --
    // is CP_A4R4G4B4, two bytes per pixel with alpha in the top nibble. The pixel path was
    // written assuming four bytes with alpha in byte 3, so it read at double the correct
    // stride and took a colour nibble as coverage: the accumulation came out as noise and
    // the shadow rendered as nothing at all. Nobody caught it because the path had never
    // run. The destination is ours and is always created A8R8G8B8.
    int nSrcBpp = 0;
    try {
        const CANVAS_PIXFORMAT fmt = pSrc->pixelFormat;
        if (fmt == CANVAS_PIXFORMAT::CP_A8R8G8B8) {
            nSrcBpp = 4;
        } else if (fmt == CANVAS_PIXFORMAT::CP_A4R4G4B4) {
            nSrcBpp = 2;
        }
    } catch (const _com_error&) {
        nSrcBpp = 0;
    }
    const bool bWantPixels = cfg.bWantPixels && nSrcBpp != 0;
    CanvasLock lkS(pSrc, bWantPixels), lkD(pDst, bWantPixels);
    if (cfg.bWantPixels && nSrcBpp == 0) {
        LOG_ONCE("weathercanvas: source pixel format is not one this can decode; "
                 "falling back to the blit path");
    }
    // A stored canvas can be smaller than its logical size (magLevel), in which case the
    // locked rows are not sw pixels wide and every offset below would be wrong. Refuse
    // rather than read across rows.
    if (lkS.ok() && lkS.nPitch < sw * nSrcBpp) {
        LOG_ONCE("weathercanvas: locked pitch %d is under %d bytes for a %d px row; "
                 "falling back to the blit path", lkS.nPitch, sw * nSrcBpp, sw);
        lkS.Unlock();
    }

    // Alpha of one source pixel, whatever the format.
    #define SRC_ALPHA(pRow, xx)         ((nSrcBpp == 4) ? (unsigned)(pRow)[(xx) * 4 + 3]                                                           : (unsigned)(((((pRow)[(xx) * 2 + 1] >> 4) & 0xF) * 17)))
    // Only scan when the caller had no opinion: a told pivot comes from the object's
    // placement and is more trustworthy than the lowest lit pixel, which a stray bit of
    // antialiasing or a cast shadow baked into the sprite can drag downward.
    if (lkS.ok() && cfg.nPivotRow < 0) {
        for (int y = sh - 1; y >= 0; --y) {
            const unsigned char* pRow = lkS.pBits + (size_t)(sy0 + y) * lkS.nPitch;
            bool bAny = false;
            for (int x = 0; x < sw; ++x) {
                if (SRC_ALPHA(pRow, x) >= 8) {   // 8, not 0: ignore antialias dust
                    bAny = true;
                    break;
                }
            }
            if (bAny) {
                nBaseRow = y;
                break;
            }
        }
    }
    if (pnBaseRow) {
        *pnBaseRow = nBaseRow;
    }
    if (!lkS.ok() || !lkD.ok()) {
        // No pixel buffer: shear by blitting one source row at a time. Same geometry,
        // hard edges, no tint control beyond what the layer colour can do.
        try {
            // CLEAR THE CANVAS FIRST. Create() does not promise to, and this path only
            // ever writes the sheared band: each row lands at its own dx, so a wedge down
            // each side -- widest at the TOP, where the lean is greatest -- is never
            // written at all. Whatever the allocator handed back stays there, and after a
            // rebuild that memory is usually the frames just freed, so the wedge shows a
            // ghost of a previous lean: a frozen, offset copy of the plant's head that
            // never moves because it is baked into the frame.
            //
            // Stretching ONE source pixel over the whole destination is the only clear
            // available without a pixel buffer, so that pixel had better be transparent.
            //
            // It used to be the source rect's corner unconditionally. That is transparent
            // on 118 of the 120 acc1 foliage sprites measured, which is why it survived --
            // and it is OPAQUE on anything that fills its own canvas. A rope and a ladder
            // both do, so both drew inside a solid box of their own corner colour.
            //
            // cfg.nClearX/Y is a measured transparent pixel for those sprites, from
            // weather_clearpx.inc. -1 keeps the old corner, which is correct wherever the
            // corner is already clear.
            // The fallback is the CANVAS corner (0,0), NOT the window corner.
            //
            // It used to be sx0/sy0, which is the same thing for an ordinary sprite and is
            // the wrong thing for a clumped one: a clump window's corner sits inside the
            // plant's own bounding box and is usually opaque, so every clumped sprite --
            // every mushroom cluster, every tuft of several plants -- cleared with a solid
            // colour and drew in a box. The ropes did not, which is why fixing their corner
            // fixed them and left the clusters untouched.
            //
            // (0,0) is safe precisely because weather_clearpx.inc lists every sprite whose
            // (0,0) is NOT transparent; a sprite absent from that table has a clear corner
            // by construction.
            const int nClrX = (cfg.nClearX >= 0 && cfg.nClearX < nFullW) ? cfg.nClearX : 0;
            const int nClrY = (cfg.nClearY >= 0 && cfg.nClearY < nFullH) ? cfg.nClearY : 0;
            pDst->CopyEx(0, 0, pSrc, CANVAS_ALPHATYPE::CA_OVERWRITE, dw, dh, nClrX, nClrY, 1, 1);
            for (int y = 0; y < sh; ++y) {
                const float hAbove = (float)(nBaseRow - y);   // signed: negative below the pivot
                // Only the LEAN is clamped: a row on the anchored side does not lean, but
                // it still has to be drawn where it belongs. The stack offset leans a row
                // further without moving it -- adding it to the vertical shifted a stacked
                // segment bodily upward and tore ladders into scattered rungs.
                const float hFree = cfg.bHangFromTop ? -hAbove : hAbove;
                float hLean = ((hFree < 0.0f) ? 0.0f : hFree) + (float)cfg.nBaseOffset;
                hLean -= (float)cfg.nRigidDepth;      // the stake holds the top still
                if (hLean < 0.0f) hLean = 0.0f;
                const int dx = nPad + (int)LeanAt(hLean);
                const int dy = nBaseY - (int)(hAbove * S);
                if (dy < 0 || dy >= dh) {
                    continue;
                }
                pDst->CopyEx(dx, dy, pSrc, CANVAS_ALPHATYPE::CA_OVERWRITE,
                             sw, 1, sx0, sy0 + y, sw, 1);
            }
        } catch (const _com_error&) {
            return nullptr;
        }
        return pDst;
    }

    // ---- keep the source's own colours: a straight sheared copy
    //
    // No accumulation and no blur. This path is only used with fSquash 1.0, so no two
    // source rows land on the same destination row and there is nothing to merge.
    if (cfg.bKeepColour) {
        for (int y = 0; y < sh; ++y) {
            const float hAbove = (float)(nBaseRow - y);   // signed: negative below the pivot
            const float hFree = cfg.bHangFromTop ? -hAbove : hAbove;
            float hLean = ((hFree < 0.0f) ? 0.0f : hFree) + (float)cfg.nBaseOffset;
            hLean -= (float)cfg.nRigidDepth;          // the stake holds the top still
            if (hLean < 0.0f) hLean = 0.0f;
            const int dxBase = nPad + (int)LeanAt(hLean);
            const int dy = nBaseY - (int)(hAbove * S);
            if (dy < 0 || dy >= dh) {
                continue;
            }
            const unsigned char* pRow = lkS.pBits + (size_t)(sy0 + y) * lkS.nPitch;
            unsigned char* pOut = lkD.pBits + (size_t)dy * lkD.nPitch;
            for (int x = 0; x < sw; ++x) {
                const int dx = dxBase + x;
                if (dx < 0 || dx >= dw) {
                    continue;
                }
                const int sxp = sx0 + x;
                if (nSrcBpp == 4) {
                    pOut[dx * 4 + 0] = pRow[sxp * 4 + 0];
                    pOut[dx * 4 + 1] = pRow[sxp * 4 + 1];
                    pOut[dx * 4 + 2] = pRow[sxp * 4 + 2];
                    pOut[dx * 4 + 3] = pRow[sxp * 4 + 3];
                } else {
                    // A4R4G4B4 -> A8R8G8B8. Nibble * 17 maps 0..15 onto 0..255 exactly.
                    const unsigned v = (unsigned)pRow[sxp * 2] | ((unsigned)pRow[sxp * 2 + 1] << 8);
                    pOut[dx * 4 + 0] = (unsigned char)((v & 0xF) * 17);
                    pOut[dx * 4 + 1] = (unsigned char)(((v >> 4) & 0xF) * 17);
                    pOut[dx * 4 + 2] = (unsigned char)(((v >> 8) & 0xF) * 17);
                    pOut[dx * 4 + 3] = (unsigned char)(((v >> 12) & 0xF) * 17);
                }
            }
        }
        return pDst;
    }

    // ---- the pixel path
    //
    // Accumulate into the destination rather than writing once per source row. A squash
    // maps several source rows onto the same destination row, and overwriting would keep
    // only the last of them, which thins the shadow into stripes.
    const int nCells = dw * dh;
    // REUSED ACROSS CALLS, not allocated per shadow. At the size ceiling these are 8 MB
    // each, and a sweep builds SHADOW_PER_FRAME of them per tick; allocating and freeing
    // 16 MB four times a frame was a large part of what made this path unusable.
    // Function-local statics are safe here because Project is only ever called from the
    // frame thread (weathersway runs from CWvsApp::CallUpdate_hook).
    static std::vector<unsigned short> vAcc;
    static std::vector<unsigned short> vTmp;
    if ((int)vAcc.size() < nCells) {
        vAcc.assign((size_t)nCells, 0);
    } else {
        std::fill(vAcc.begin(), vAcc.begin() + nCells, (unsigned short)0);
    }

    for (int y = 0; y < sh; ++y) {
        const float hAbove = (float)(nBaseRow - y);   // signed: negative below the pivot
        const float hFree = cfg.bHangFromTop ? -hAbove : hAbove;
        const float hLean = ((hFree < 0.0f) ? 0.0f : hFree) + (float)cfg.nBaseOffset;
        const int dxBase = nPad + (int)(hLean * L);
        const int dy = nBaseY - (int)(hAbove * S);
        if (dy < 0 || dy >= dh) {
            continue;
        }
        const unsigned char* pRow = lkS.pBits + (size_t)(sy0 + y) * lkS.nPitch;
        unsigned short* pAcc = &vAcc[(size_t)dy * dw];
        for (int x = 0; x < sw; ++x) {
            const unsigned a = SRC_ALPHA(pRow, sx0 + x);
            if (!a) {
                continue;
            }
            const int dx = dxBase + x;
            if (dx < 0 || dx >= dw) {
                continue;
            }
            if (pAcc[dx] < (unsigned short)a) {
                pAcc[dx] = (unsigned short)a;   // max, not sum: a silhouette has no depth
            }
        }
    }

    // Soften. A separable box blur run twice approximates a gaussian closely enough at
    // these radii and costs a fraction of a real one.
    const int r = (cfg.nBlur > 0) ? cfg.nBlur : 0;
    if (r > 0) {
        // A SLIDING WINDOW, not a re-sum per pixel, and ROW MAJOR in both directions.
        //
        // The straightforward version cost dw*dh*(2r+1) per direction per pass and walked
        // the vertical pass column major through a row major buffer. At the size ceiling
        // (4096 x 1024, r = 2) that is about 84 million operations and a cache miss on
        // most of them, per shadow, four shadows a tick. That, not the COM plumbing, is
        // what hung the client. Running sums make it dw*dh per direction regardless of r,
        // and the vertical pass keeps one running total per COLUMN so it can still walk
        // rows in order.
        if ((int)vTmp.size() < nCells) {
            vTmp.assign((size_t)nCells, 0);
        }
        for (int pass = 0; pass < 2; ++pass) {
            // Horizontal: vAcc -> vTmp
            for (int y = 0; y < dh; ++y) {
                const unsigned short* pIn = &vAcc[(size_t)y * dw];
                unsigned short* pOut = &vTmp[(size_t)y * dw];
                int sum = 0;
                for (int x = 0; x <= r && x < dw; ++x) {
                    sum += pIn[x];
                }
                for (int x = 0; x < dw; ++x) {
                    const int lo = (x - r > 0) ? (x - r) : 0;
                    const int hi = (x + r < dw - 1) ? (x + r) : (dw - 1);
                    pOut[x] = (unsigned short)(sum / (hi - lo + 1));
                    // Advance the window to be centred on x+1.
                    const int add = x + r + 1;
                    const int drop = x - r;
                    if (add < dw) sum += pIn[add];
                    if (drop >= 0) sum -= pIn[drop];
                }
            }
            // Vertical: vTmp -> vAcc, one running total per column.
            std::vector<int>& vCol = ColScratch(dw);
            std::fill(vCol.begin(), vCol.begin() + dw, 0);
            for (int y = 0; y <= r && y < dh; ++y) {
                const unsigned short* pIn = &vTmp[(size_t)y * dw];
                for (int x = 0; x < dw; ++x) vCol[x] += pIn[x];
            }
            for (int y = 0; y < dh; ++y) {
                const int lo = (y - r > 0) ? (y - r) : 0;
                const int hi = (y + r < dh - 1) ? (y + r) : (dh - 1);
                const int n = hi - lo + 1;
                unsigned short* pOut = &vAcc[(size_t)y * dw];
                for (int x = 0; x < dw; ++x) {
                    pOut[x] = (unsigned short)(vCol[x] / n);
                }
                const int addY = y + r + 1;
                const int dropY = y - r;
                if (addY < dh) {
                    const unsigned short* pAdd = &vTmp[(size_t)addY * dw];
                    for (int x = 0; x < dw; ++x) vCol[x] += pAdd[x];
                }
                if (dropY >= 0) {
                    const unsigned short* pDrop = &vTmp[(size_t)dropY * dw];
                    for (int x = 0; x < dw; ++x) vCol[x] -= pDrop[x];
                }
            }
        }
    }

    for (int y = 0; y < dh; ++y) {
        unsigned char* pRow = lkD.pBits + (size_t)y * lkD.nPitch;
        const unsigned short* pAcc = &vAcc[(size_t)y * dw];
        for (int x = 0; x < dw; ++x) {
            int a = (int)((float)pAcc[x] * cfg.fAlpha);
            if (a > 255) a = 255;
            pRow[x * 4 + 0] = cfg.uB;
            pRow[x * 4 + 1] = cfg.uG;
            pRow[x * 4 + 2] = cfg.uR;
            pRow[x * 4 + 3] = (unsigned char)a;
        }
    }
    return pDst;
}
