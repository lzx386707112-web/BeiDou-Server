cmake_minimum_required(VERSION 3.20)
cmake_policy(SET CMP0091 NEW)
project(BeiDouWeatherCompat LANGUAGES CXX)

set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

if(NOT MSVC OR NOT CMAKE_SIZEOF_VOID_P EQUAL 4)
    message(FATAL_ERROR "Build with 32-bit MSVC (Visual Studio generator, -A Win32)")
endif()

include(FetchContent)
FetchContent_Declare(detours
    GIT_REPOSITORY https://github.com/microsoft/Detours.git
    GIT_TAG 9764cebcb1a75940e68fa83d6730ffaf0f669401
    GIT_SHALLOW FALSE)
FetchContent_Declare(wzlib
    GIT_REPOSITORY https://github.com/iw2d/WzLib.git
    GIT_TAG 098795e27ea388beff147c5f89c7bff09af398ea
    GIT_SHALLOW FALSE)
FetchContent_MakeAvailable(detours wzlib)

add_library(WeatherDetours STATIC
    ${detours_SOURCE_DIR}/src/creatwth.cpp
    ${detours_SOURCE_DIR}/src/modules.cpp
    ${detours_SOURCE_DIR}/src/detours.cpp
    ${detours_SOURCE_DIR}/src/disolx86.cpp
    ${detours_SOURCE_DIR}/src/disasm.cpp
    ${detours_SOURCE_DIR}/src/image.cpp)
target_include_directories(WeatherDetours PUBLIC ${detours_SOURCE_DIR}/src)
target_compile_options(WeatherDetours PRIVATE /Brepro)

add_library(BeiDouWeatherCompat SHARED
    src/WeatherCompat.cpp src/hook.cpp src/debug.cpp
    src/util.cpp
    src/weather.cpp src/weatherfx.cpp src/weathercanvas.cpp
    src/weathersound.cpp src/weathersplash.cpp src/weatherwind.cpp
    src/weatheraccum.cpp src/weatherpuddle.cpp
    src/weathersway.cpp src/lamps.cpp)
target_compile_features(BeiDouWeatherCompat PRIVATE cxx_std_17)
target_compile_definitions(BeiDouWeatherCompat PRIVATE WIN32_LEAN_AND_MEAN NOMINMAX)
target_compile_options(BeiDouWeatherCompat PRIVATE /Brepro)
target_link_options(BeiDouWeatherCompat PRIVATE /Brepro)
target_include_directories(BeiDouWeatherCompat PRIVATE src)
target_precompile_headers(BeiDouWeatherCompat PRIVATE src/pch.h)
target_link_libraries(BeiDouWeatherCompat PRIVATE WeatherDetours WzLib winmm ws2_32)
set_target_properties(BeiDouWeatherCompat PROPERTIES OUTPUT_NAME BeiDouWeatherCompat)
