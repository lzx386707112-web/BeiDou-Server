#pragma once

#ifdef _DEBUG
#define DEBUG_MESSAGE(FORMAT, ...) DebugMessage(FORMAT, __VA_ARGS__)
#else
#define DEBUG_MESSAGE(FORMAT, ...)
#endif


void DebugMessage(const char* sFormat, ...);

void ErrorMessage(const char* sFormat, ...);

void LogMessage(const char* sFormat, ...);

#define LOG_ONCE(...)                               \
    do {                                            \
        static bool logged__ = false;               \
        if (!logged__) {                            \
            logged__ = true;                        \
            LogMessage(__VA_ARGS__);                \
        }                                           \
    } while (0)

constexpr int kLogKeyCap = 64;
#define LOG_ONCE_PER_ID(KEY, ...)                                             \
    do {                                                                      \
        static int keys__[kLogKeyCap] = {};                                   \
        static int count__ = 0;                                               \
        const int key__ = (KEY);                                              \
        bool seen__ = false;                                                  \
        for (int i__ = 0; i__ < count__; ++i__) seen__ |= keys__[i__] == key__; \
        if (!seen__ && count__ < kLogKeyCap) {                                \
            keys__[count__++] = key__;                                        \
            LogMessage(__VA_ARGS__);                                          \
        }                                                                     \
    } while (0)
