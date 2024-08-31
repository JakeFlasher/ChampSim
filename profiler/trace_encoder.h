#ifndef TRACE_ENCODER_H
#define TRACE_ENCODER_H
#include "trace-instruction.h"
#include <string>
#include <vector>

namespace clueless
{
class trace_encoder
{
public:
  explicit trace_encoder(const char *output_trace_string);
  ~trace_encoder();
  void write_single_instr(const input_instr &instr);

private:
  void open(std::string trace_string);
  void close();
  void flush_buffer();

  FILE *trace_file = nullptr;
  std::string trace_string;
  std::string cmd_fmtstr;
  std::string comp_program;

  static constexpr size_t BUFFER_SIZE = 10ULL * 1024 * 1024 * 1024; // 10 GB
  std::vector<input_instr> buffer;
};
}
#endif
