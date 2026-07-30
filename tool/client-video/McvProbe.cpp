#include "McvFormat.h"

#include <fstream>
#include <iostream>
#include <iterator>
#include <vector>

int main(int argc, char** argv) {
    if (argc != 2) {
        std::cerr << "usage: mcv_probe <video.mcv>\n";
        return 2;
    }
    std::ifstream input(argv[1], std::ios::binary);
    if (!input) {
        std::cerr << "failed to open " << argv[1] << "\n";
        return 2;
    }
    std::vector<uint8_t> data{
        std::istreambuf_iterator<char>(input),
        std::istreambuf_iterator<char>()};
    bdv::McvVideo video;
    char error[256] = {};
    if (!bdv::ParseMcv(data.data(), data.size(), &video, error, sizeof(error))) {
        std::cerr << error << "\n";
        return 1;
    }
    std::cout
        << "codec=" << bdv::FourCcName(video.fourCc)
        << " size=" << video.width << "x" << video.height
        << " frames=" << video.frames.size()
        << " alpha=" << ((video.flags & bdv::kAlphaMap) != 0 ? "yes" : "no")
        << " duration_ms=" << video.durationNanoseconds / 1000000u
        << " bytes=" << data.size()
        << "\n";
    return 0;
}
