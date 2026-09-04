#pragma once
#include "ztl/ztl.h"
#include <vector>

// Generating sprites at runtime from sprites the map already has.
//
// Shared by the cast shadows and the foliage sway, which want the same thing for
// different reasons: both need a SHEARED copy of an object, and IWzGr2DLayer has no
// shear. See weathercanvas.cpp for why there are two code paths and which one is which.

struct PROJECT {
    // A point h above the base lands at (x + h*fLean, base - h*fSquash).
    //
    // fLean is how far the top travels sideways, as a multiple of the sprite's height:
    // 0 is straight down, 2.0 leans two heights to the right. fSquash is how much of the
    // height survives; for a shadow lying on a side-view ground line it is small and
    // CONSTANT, because that ground is a line with no depth.
    float fLean;
    float fSquash;

    float fAlpha;          // 0..1, applied to the whole result
    int   nBlur;           // box radius in px, 0 for a hard edge
    unsigned char uR, uG, uB;   // the flat colour the silhouette is filled with

    // Keep the SOURCE's own colours instead of flattening to uR/uG/uB. A shadow wants a
    // silhouette; a swaying plant wants to still look like the plant.
    bool bKeepColour = false;

    // ASK FOR THE RAW PIXEL PATH. Off by default, and that default is load bearing.
    //
    // Only an accumulating, blurred silhouette actually needs pixels; a sheared copy does
    // not, and the CopyEx blit produces identical geometry for it. When the pixel path was
    // switched on globally it therefore bought shadows nothing extra and dragged every
    // foliage sway sprite onto a code path that had never executed, which hung and then
    // corrupted the client. Per call keeps the blast radius to the one caller that needs
    // it. NOTHING IN THIS BUNDLE SETS IT: the only module that did was the cast shadows,
    // which are excluded, so every caller here takes the CopyEx path and no raw canvas is
    // ever locked. The parameter is kept because the shear is the reusable half.
    bool bWantPixels = false;

    // Force the horizontal padding instead of deriving it from fLean. A set of frames
    // that will be swapped between MUST all be the same size, or switching frames shifts
    // the sprite. 0 means derive it.
    int nPadOverride = 0;

    // Read only this window of the source, and treat it as the whole sprite.
    //
    // For foliage that is SEVERAL plants in one bitmap. A shear has one pivot, so four
    // mushrooms in one sprite all lean about the base of the bitmap and the outer ones
    // swing through an arc instead of standing on their stems. Projecting each plant's
    // own window separately gives each one its own pivot at its own base.
    //
    // right <= left means "the whole canvas", which is what every existing caller gets
    // by leaving it alone. Everything downstream measures from the WINDOW, so a caller
    // passing a window gets back a canvas the size of that window plus the padding, and
    // nPivotRow is relative to the window's top.
    RECT rcSrc = { 0, 0, 0, 0 };

    // How far this sprite's pivot sits ABOVE the real base of the thing it belongs to.
    //
    // For a lone bush that is 0: it is rooted where it stands. For the third segment of a
    // ladder it is the height of the two below, so the segment leans by the amount the
    // whole ladder has leant by the time it gets that high, and its bottom edge lands
    // exactly where the segment below's top edge did. Without it every segment restarts
    // its lean from zero and the ladder comes apart at each joint.
    int nBaseOffset = 0;

    // The source row to pivot on, or -1 to find it by scanning the alpha.
    //
    // Scanning needs the pixel buffer, and on a client where _LockAddress hands one back
    // it is the better answer. Where it does not, the blit path has no pixels to look at
    // and would fall back to the canvas BOTTOM, which is wrong for any sprite with
    // transparent padding under the plant: it swings from a point below itself.
    //
    // A caller that knows where the object is ROOTED should say so. The engine places a
    // map object's canvas origin at its obj entry's y, so `entryY - layerTop` is the base
    // row, needs no pixel access, and is what the engine itself treats as ground contact.
    int nPivotRow = -1;

    // WHICH SOURCE PIXEL THE BLIT PATH CLEARS WITH, or -1 to use the source rect's corner.
    //
    // Only the CopyEx path reads this, and only because it cannot zero its destination:
    // with no pixel buffer the sole clear available is stretching ONE source pixel over
    // the whole canvas. The corner is transparent on almost every foliage sprite, which is
    // why that held up, and it is opaque on anything that fills its own canvas -- a rope, a
    // ladder -- where it floods the padding with a solid colour and the sprite draws inside
    // a visible box.
    //
    // weather_clearpx.inc carries a measured transparent pixel for every sprite whose
    // corner is not already one. The pixel path ignores this entirely.
    int nClearX = -1;
    int nClearY = -1;

    // How far below the anchor stays RIGID before any bending starts, in the same units
    // as nBaseOffset (depth below the column's anchor).
    //
    // For a rope this is the stake. A rope tied to a post does not start curving at the
    // knot: the top of it is held straight and the free length below swings. Measured down
    // the whole COLUMN, not per segment, so a stacked rope has one rigid head rather than
    // a rigid section at the top of every segment.
    int nRigidDepth = 0;

    // HANG FROM THE PIVOT INSTEAD OF STANDING ON IT.
    //
    // A plant is rooted at the bottom and leans more the higher up you go. A rope or a
    // ladder is the other way round: it is fixed at its TOP anchor and swings further the
    // further DOWN you are. Same shear, opposite sign, so this flips which side of the
    // pivot moves. nBaseOffset then means depth below the column's anchor rather than
    // height above its floor.
    bool bHangFromTop = false;
};

// Both are answered once and cached; safe to call every frame.
//
// True when a canvas can be created at all, so WeatherCanvas_Project can shear -- through
// the pixel buffer if there is one, otherwise by blitting rows with CopyEx. This is what a
// SWAY needs: it keeps the source's colours and does not care about soft edges.
bool WeatherCanvas_Probe();

// True only when _LockAddress hands out a real buffer. What the accumulating paths need:
// a shadow builds a silhouette and blurs it, and CopyEx can do neither.
bool WeatherCanvas_HasPixelPath();

// Project pSrc through cfg and return a NEW canvas, or null on any failure.
//
// pAnchor comes back holding where the source sits inside the result: x is the source's
// left edge, y is its BASE. A caller places the result by lining those up with wherever
// the original object's own base is, which is the only way the shadow stays attached to
// its object as the lean changes the canvas size.
// pnBaseRow, when given, comes back with the source row the projection PIVOTED on: the
// lowest row with real pixels in it, not the canvas bottom. A caller aligning the result
// must use that row, because a sprite with transparent padding below the plant has a
// visible base well above its canvas edge.
IWzCanvasPtr WeatherCanvas_Project(IWzCanvasPtr pSrc, const PROJECT& cfg, POINT* pAnchor,
                                   int* pnBaseRow = nullptr);
