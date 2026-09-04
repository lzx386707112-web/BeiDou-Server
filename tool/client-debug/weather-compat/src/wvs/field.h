#pragma once
#include "hook.h"
#include "wvs/stage.h"
#include "wvs/wnd.h"
#include "ztl/ztl.h"


class CMapLoadable : public CStage {
public:
    MEMBER_AT(IWzPropertyPtr, 0x2C, m_pPropFieldInfo)
    MEMBER_AT(IWzPropertyPtr, 0x30, m_pPropField)
    MEMBER_AT(RECT, 0xF0, m_rcViewRange)
    MEMBER_HOOK(void, 0x00641EF1, RestoreViewRange) // resolution.cpp
    MEMBER_HOOK(void, 0x00639B3D, LoadMap)
    MEMBER_HOOK(void, 0x006399EF, Update)
    MEMBER_HOOK(void, 0x0063A100, RestoreTile)
    MEMBER_HOOK(void, 0x0063AA7E, RestoreObj)
    MEMBER_HOOK(void, 0x0063CBBA, RestoreBack)
    MEMBER_HOOK(void*, 0x0063CD4E, MakeBack, int nIndex, void* pProp)
    MEMBER_HOOK(void*, 0x0063AD16, MakeObj, int nLayer, IWzProperty* pObjProp)
};

class CNpcPool {
public:
    MEMBER_HOOK(void, 0x006D9993, OnNpcEnterField, void* pPacket)
};


class CField : public CMapLoadable {
public:
    MEMBER_AT(ZRef<CWnd>, 0x1C8, m_pClock) // ZRef<CClock>
};


inline CField* get_field() {
    return reinterpret_cast<CField*(__cdecl*)()>(0x00437A0C)();
}
