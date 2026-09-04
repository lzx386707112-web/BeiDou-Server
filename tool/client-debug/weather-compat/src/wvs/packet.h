#pragma once
#include "ztl/ztl.h"


class CInPacket {
protected:
    int m_bLoopback;
    int m_nState;
    ZArray<unsigned char> m_aRecvBuff;
    unsigned short m_uLength;
    unsigned short m_uRawSeq;
    unsigned short m_uDataLen;
    size_t m_uOffset;

protected:
    uint16_t Peek2() const {
        if (m_aRecvBuff.GetCount() == 0 || m_uOffset + 2 > m_uLength) return 0;
        return *reinterpret_cast<const uint16_t*>(&m_aRecvBuff[m_uOffset]);
    }

public:
    uint16_t Peek2Public() const { return Peek2(); }
    size_t GetOffset() const { return m_uOffset; }
    void SetOffset(size_t offset) { m_uOffset = offset; }
    bool CanRead(size_t size) const {
        return m_uOffset + size <= static_cast<size_t>(m_aRecvBuff.GetCount());
    }
    template <typename T>
    T Decode() {
        static_assert(sizeof(T) <= 8, "Decode<T> only supports up to 8 bytes");
        if (!CanRead(sizeof(T))) return T{};
        T value = *reinterpret_cast<const T*>(&m_aRecvBuff[m_uOffset]);
        m_uOffset += sizeof(T);
        return value;
    }
};

static_assert(sizeof(CInPacket) == 0x18);


class COutPacket {
protected:
    int m_bLoopback;
    ZArray<unsigned char> m_aSendBuff;
    unsigned int m_uOffset;
    int m_bIsEncryptedByShanda;

public:
    explicit COutPacket(int nType) : m_aSendBuff(0x100) {
        Init(nType, 0, 0);
    }
    void Encode1(unsigned char n) {
        EncodeBuffer(&n, 1);
    }
    void Encode2(unsigned short n) {
        EncodeBuffer(&n, 2);
    }
    void Encode4(unsigned int n) {
        EncodeBuffer(&n, 4);
    }
    void EncodeStr(ZXString<char> s) {
        int n = s.GetLength();
        Encode2(n);
        EncodeBuffer(s, n);
    }
    void EncodeBuffer(const void* p, size_t uSize) {
        EnlargeBuffer(uSize);
        memcpy(&m_aSendBuff[m_uOffset], p, uSize);
        m_uOffset += uSize;
    }
    void Init(int nType, int bLoopback, int bTypeHeader1Byte) {
        m_bLoopback = bLoopback;
        m_uOffset = 0;
        if (nType != 0x7FFFFFFF) {
            if (bTypeHeader1Byte) {
                Encode1(nType);
            } else {
                Encode2(nType);
            }
        }
        m_bIsEncryptedByShanda = 0;
    }

protected:
    void EnlargeBuffer(size_t uSize) {
        size_t uCur = m_aSendBuff.GetCount();
        size_t uReq = m_uOffset + uSize;
        if (uCur < uReq) {
            do {
                uCur *= 2;
            } while (uCur < uReq);
            m_aSendBuff.Realloc(uCur, 0);
        }
    }
};

static_assert(sizeof(COutPacket) == 0x10);
