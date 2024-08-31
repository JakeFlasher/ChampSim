#include "champsim-trace-decoder.h"
#include "propagator.h"
#include "tracereader.h"
#include <argp.h>
#include <array>
#include <cassert>
#include <cstddef>
#include <cstdlib>
#include <unordered_set>
#include <unordered_map>
#include <vector>
#include <fstream>
#include <iostream>
#include <lzma.h>
#include <sstream>
#include <iomanip>
#include <filesystem>

using namespace clueless;

void process_trace_file(const std::string &trace_file_path, const std::string &output_stable_loads, size_t nwarmup, size_t nsimulate);

int main(int argc, char *argv[]) {
  if (argc != 5) {
    std::cerr << "Usage: " << argv[0] << " <trace_file> <nwarmup> <nsimulate> <output_stable_loads>\n";
    return EXIT_FAILURE;
  }

  std::string trace_file_path = argv[1];
  size_t nwarmup = std::stoull(argv[2]);
  size_t nsimulate = std::stoull(argv[3]);
  std::string output_stable_loads = argv[4];

  process_trace_file(trace_file_path, output_stable_loads, nwarmup, nsimulate);

  return EXIT_SUCCESS;
}

void process_trace_file(const std::string &trace_file_path, const std::string &output_stable_loads, size_t nwarmup, size_t nsimulate) {
  tracereader reader(trace_file_path.c_str());
  champsim_trace_decoder decoder;
  propagator prop;

  std::ofstream stable_loads_file(output_stable_loads, std::ios::binary);
  if (!stable_loads_file.is_open()) {
    std::cerr << "Failed to open stable loads file for writing." << std::endl;
    return;
  }

  // Skip warmup instructions
  for (size_t i = 0; i < nwarmup; ++i) {
    reader.read_single_instr();
  }

  std::unordered_map<uint64_t, size_t> last_occurrence;
  std::unordered_map<unsigned, size_t> last_write_to_reg;
  std::unordered_map<uint64_t, size_t> last_store_to_mem;

  size_t actual_simulated_instr_count = 0;

  for (size_t i = 0; i < nsimulate; ++i) {
    auto input_ins = reader.read_single_instr();
    const auto &decoded_instr = decoder.decode(input_ins);

    bool is_global_stable_load = false;

    if (decoded_instr.op == propagator::instr::opcode::OP_LOAD) {
      auto address = decoded_instr.address;

      // Check if this is the first occurrence or if conditions are met
      if (last_occurrence.find(address) == last_occurrence.end()) {
        last_occurrence[address] = i; // Preserve the first encounter
      } else {
        bool condition1 = true;
        bool condition2 = true;

        for (const auto &reg : decoded_instr.src_reg) {
          if (last_write_to_reg.find(reg) != last_write_to_reg.end() &&
              last_write_to_reg[reg] > last_occurrence[address]) {
            condition1 = false;
            break;
          }
        }

        if (last_store_to_mem.find(address) != last_store_to_mem.end() &&
            last_store_to_mem[address] > last_occurrence[address]) {
          condition2 = false;
        }

        if (condition1 && condition2) {
          stable_loads_file.write(reinterpret_cast<const char*>(&i), sizeof(i));
          is_global_stable_load = true;
        }
      }

      last_occurrence[address] = i;
    }

    if (!is_global_stable_load) {
      ++actual_simulated_instr_count;
    }

    if (decoded_instr.op == propagator::instr::opcode::OP_STORE) {
      last_store_to_mem[decoded_instr.address] = i;
    }

    for (const auto &reg : decoded_instr.dst_reg) {
      last_write_to_reg[reg] = i;
    }
  }

  stable_loads_file.close();

  std::string base_name = std::filesystem::path(trace_file_path).stem().string();
  std::cout << "Trace: " << base_name << "\n";
//  std::cout << "Warm-up Count: " << nwarmup / 1e6 << "M\n";
//  std::cout << "Simulate Count: " << nsimulate / 1e6 << "M\n";
  std::cout << "Profiled Count: " << actual_simulated_instr_count << "\n";
}
