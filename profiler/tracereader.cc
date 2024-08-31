#include "tracereader.h"
#include <cassert>
#include <fstream>
#include <iostream>
#include <sstream>

namespace clueless
{
tracereader::tracereader (const char *_ts) : trace_string (_ts)
{
  std::string last_dot = trace_string.substr (trace_string.find_last_of ("."));
  std::ifstream testfile (trace_string);
  if (!testfile.good ())
    {
      std::cerr << "TRACE FILE NOT FOUND" << std::endl;
      assert (0);
    }
  cmd_fmtstr = "%1$s -dc %2$s";
  if (last_dot[1] == 'g') // gzip format
    decomp_program = "gzip";
  else if (last_dot[1] == 'x') // xz
    decomp_program = "xz";
  else
    {
      std::cout << "ChampSim does not support traces other than gz or xz "
                   "compression!"
                << std::endl;
      assert (0);
    }
  log_file.open("decoded_log.csv");
  log_file << "IP,is_branch,branch_taken,dest_regs,source_regs,dest_mem,source_mem\n"; // CSV header
  open (trace_string);
}

tracereader::~tracereader ()
{
  close ();
  if (log_file.is_open())
    log_file.close();
}
input_instr
tracereader::read_single_instr ()
{
  input_instr trace_read_instr;
  while (!fread (&trace_read_instr, sizeof (trace_read_instr), 1, trace_file))
    {
      // reached end of file for this trace
      std::cout << "*** Reached end of trace: " << trace_string << std::endl;
      // close the trace file and re-open it
      close ();
      open (trace_string);
    }
  return trace_read_instr;
}
/*
input_instr tracereader::read_single_instr(bool &eof) {
  input_instr trace_read_instr;
  if (!fread(&trace_read_instr, sizeof(trace_read_instr), 1, trace_file)) {
    // reached end of file for this trace
    std::cout << "*** Reached end of trace: " << trace_string << std::endl;
    eof = true;
    return {};
  }
  eof = false;
  return trace_read_instr;
}
*/
void
tracereader::log_decoded_instr(const input_instr& instr)
{
  std::stringstream ss;
  
  ss << instr.ip << ","
     << static_cast<int>(instr.is_branch) << ","
     << static_cast<int>(instr.branch_taken) << ",";
  
  for (size_t i = 0; i < NUM_INSTR_DESTINATIONS; ++i) {
    ss << static_cast<int>(instr.destination_registers[i]);
    if (i < NUM_INSTR_DESTINATIONS - 1)
      ss << " ";
  }
  ss << ",";
  
  for (size_t i = 0; i < NUM_INSTR_SOURCES; ++i) {
    ss << static_cast<int>(instr.source_registers[i]);
    if (i < NUM_INSTR_SOURCES - 1)
      ss << " ";
  }
  ss << ",";
  
  for (size_t i = 0; i < NUM_INSTR_DESTINATIONS; ++i) {
    ss << instr.destination_memory[i];
    if (i < NUM_INSTR_DESTINATIONS - 1)
      ss << " ";
  }
  ss << ",";
  
  for (size_t i = 0; i < NUM_INSTR_SOURCES; ++i) {
    ss << instr.source_memory[i];
    if (i < NUM_INSTR_SOURCES - 1)
      ss << " ";
  }
  
  log_file << ss.str() << "\n";
}

void
tracereader::open (std::string trace_string)
{
  char gunzip_command[4096];
  sprintf (gunzip_command, cmd_fmtstr.c_str (), decomp_program.c_str (),
           trace_string.c_str ());
  trace_file = popen (gunzip_command, "r");
  if (trace_file == NULL)
    {
      std::cerr << std::endl
                << "*** CANNOT OPEN TRACE FILE: " << trace_string << " ***"
                << std::endl;
      assert (0);
    }
}

void
tracereader::close ()
{
  if (trace_file != NULL)
    {
      pclose (trace_file);
    }
}
}
