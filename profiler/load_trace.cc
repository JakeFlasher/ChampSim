#include "champsim-trace-decoder.h"
#include "propagator.h"
#include "tracereader.h"
#include "trace_encoder.h"
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
#include <thread>

using namespace clueless;

void process_trace_file(const std::string &trace_file_path, const std::string &output_trace_file, size_t nwarmup, size_t nsimulate, size_t heartbeat, const std::string &stable_load_file);

std::unordered_set<size_t> load_stable_loads(const std::string &stable_load_file);

int main(int argc, char *argv[]) {
  if (argc != 7) {
    std::cerr << "Usage: " << argv[0] << " <trace_file> <nwarmup> <nsimulate> <heartbeat> <stable_load_file> <output_trace_file>\n";
    return EXIT_FAILURE;
  }

  std::string trace_file_path = argv[1];
  size_t nwarmup = std::stoull(argv[2]);
  size_t nsimulate = std::stoull(argv[3]);
  size_t heartbeat = std::stoull(argv[4]);
  std::string stable_load_file = argv[5];
  std::string output_trace_file = argv[6];

  process_trace_file(trace_file_path, output_trace_file, nwarmup, nsimulate, heartbeat, stable_load_file);

  return EXIT_SUCCESS;
}

void process_trace_file(const std::string &trace_file_path, const std::string &output_trace_file, size_t nwarmup, size_t nsimulate, size_t heartbeat, const std::string &stable_load_file) {
  std::unordered_set<size_t> stable_loads = load_stable_loads(stable_load_file);
  tracereader reader(trace_file_path.c_str());
  champsim_trace_decoder decoder;
  propagator prop;
  trace_encoder encoder(output_trace_file.c_str());

  // Skip warmup instructions
  for (size_t i = 0; i < nwarmup; ++i) {
    auto warmup_instr = reader.read_single_instr();
    encoder.write_single_instr(warmup_instr);
  }

  for (size_t i = 0; i < nsimulate; ++i) {
    if (!(i % heartbeat)) {
      printf("Processed %zu instructions\n", i);
      fflush(stdout);
    }

    auto input_ins = reader.read_single_instr();

    // Skip logging if this instruction is a global stable load
    if (stable_loads.find(i) == stable_loads.end()) {
      encoder.write_single_instr(input_ins);
    }
  }

  printf("Trace file encoded to %s\n", output_trace_file.c_str());
}

std::unordered_set<size_t> load_stable_loads(const std::string &stable_load_file) {
  std::unordered_set<size_t> stable_loads;
  std::ifstream file(stable_load_file, std::ios::binary);

  if (!file.is_open()) {
    std::cerr << "Failed to open stable load file." << std::endl;
    return stable_loads;
  }

  size_t index;
  while (file.read(reinterpret_cast<char*>(&index), sizeof(index))) {
    stable_loads.insert(index);
  }

  return stable_loads;
}
