#ifndef DRAM_STATS_H
#define DRAM_STATS_H

#include <cstdint>
#include <string>

#include "chrono.h"

struct dram_stats {
  std::string name{};
  champsim::chrono::clock::duration dbus_cycle_congested{};
  uint64_t dbus_count_congested = 0;

  unsigned WQ_ROW_BUFFER_HIT = 0, WQ_ROW_BUFFER_MISS = 0, RQ_ROW_BUFFER_HIT = 0, RQ_ROW_BUFFER_MISS = 0, WQ_FULL = 0;
};

dram_stats operator-(dram_stats lhs, dram_stats rhs);

#endif