#include <iostream>
#include <fstream>
#include <vector>
#include <lzma.h>
#include "trace_instruction.h"
#include "champsim-trace-decoder.h"
#include "tracereader.h"
using namespace clueless;

// Function to compress data using LZMA and write to file
bool write_compressed_trace(const std::vector<input_instr>& instructions, const std::string& output_file) {
    lzma_stream strm = LZMA_STREAM_INIT;
    lzma_ret ret = lzma_easy_encoder(&strm, LZMA_PRESET_DEFAULT, LZMA_CHECK_CRC64);
    if (ret != LZMA_OK) {
        std::cerr << "Failed to initialize LZMA encoder: " << ret << std::endl;
        return false;
    }

    std::ofstream outfile(output_file, std::ios::binary);
    if (!outfile.is_open()) {
        std::cerr << "Failed to open output file: " << output_file << std::endl;
        lzma_end(&strm);
        return false;
    }

    std::vector<uint8_t> inbuf(sizeof(input_instr));
    std::vector<uint8_t> outbuf(8192);

    strm.next_out = outbuf.data();
    strm.avail_out = outbuf.size();

    for (const auto& instr : instructions) {
        std::memcpy(inbuf.data(), &instr, sizeof(input_instr));
        strm.next_in = inbuf.data();
        strm.avail_in = inbuf.size();

        while (strm.avail_in > 0) {
            ret = lzma_code(&strm, LZMA_RUN);
            if (ret != LZMA_OK && ret != LZMA_STREAM_END) {
                std::cerr << "LZMA encoding error: " << ret << std::endl;
                lzma_end(&strm);
                return false;
            }

            if (strm.avail_out == 0 || ret == LZMA_STREAM_END) {
                outfile.write(reinterpret_cast<char*>(outbuf.data()), outbuf.size() - strm.avail_out);
                strm.next_out = outbuf.data();
                strm.avail_out = outbuf.size();
            }
        }
    }

    ret = lzma_code(&strm, LZMA_FINISH);
    if (ret != LZMA_STREAM_END) {
        std::cerr << "LZMA encoding finish error: " << ret << std::endl;
        lzma_end(&strm);
        return false;
    }

    if (strm.avail_out < outbuf.size()) {
        outfile.write(reinterpret_cast<char*>(outbuf.data()), outbuf.size() - strm.avail_out);
    }

    lzma_end(&strm);
    outfile.close();
    return true;
}

int main(int argc, char* argv[]) {
    if (argc != 3) {
        std::cerr << "Usage: " << argv[0] << " <input_trace_file> <output_trace_file>" << std::endl;
        return 1;
    }

    std::string input_trace_file = argv[1];
    std::string output_trace_file = argv[2];

    tracereader reader(input_trace_file);
    champsim_trace_decoder decoder;

    std::vector<input_instr> instructions;
    while (reader.has_next()) {
        auto input_ins = reader.read_single_instr();
        const auto& decoded_ins = decoder.decode(input_ins);

        input_instr instr{
            decoded_ins.ip,
            decoded_ins.is_branch,
            decoded_ins.branch_taken,
            {0}, {0}, {0}, {0}
        };

        std::copy(decoded_ins.destination_registers.begin(), decoded_ins.destination_registers.end(), instr.destination_registers);
        std::copy(decoded_ins.source_registers.begin(), decoded_ins.source_registers.end(), instr.source_registers);
        std::copy(decoded_ins.destination_memory.begin(), decoded_ins.destination_memory.end(), instr.destination_memory);
        std::copy(decoded_ins.source_memory.begin(), decoded_ins.source_memory.end(), instr.source_memory);

        instructions.push_back(instr);
    }

    if (!write_compressed_trace(instructions, output_trace_file)) {
        std::cerr << "Failed to write compressed trace file." << std::endl;
        return 1;
    }

    std::cout << "Successfully wrote compressed trace file to " << output_trace_file << std::endl;
    return 0;
}
