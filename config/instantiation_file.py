#    Copyright 2023 The ChampSim Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import itertools
import functools
import operator
import os

from . import util

pmem_fmtstr = 'MEMORY_CONTROLLER {name}{{{frequency}, {io_freq}, {tRP}, {tRCD}, {tCAS}, {turn_around_time}, {{{_ulptr}}}}};'
vmem_fmtstr = 'VirtualMemory vmem{{{pte_page_size}, {num_levels}, {minor_fault_penalty}, {dram_name}}};'

queue_fmtstr = 'champsim::channel {name}{{{rq_size}, {pq_size}, {wq_size}, {_offset_bits}, {_queue_check_full_addr:b}}};'

core_builder_parts = {
    'ifetch_buffer_size': '.ifetch_buffer_size({ifetch_buffer_size})',
    'decode_buffer_size': '.decode_buffer_size({decode_buffer_size})',
    'dispatch_buffer_size': '.dispatch_buffer_size({dispatch_buffer_size})',
    'rob_size': '.rob_size({rob_size})',
    'lq_size': '.lq_size({lq_size})',
    'sq_size': '.sq_size({sq_size})',
    'fetch_width': '.fetch_width({fetch_width})',
    'decode_width': '.decode_width({decode_width})',
    'dispatch_width': '.dispatch_width({dispatch_width})',
    'scheduler_size': '.schedule_width({scheduler_size})',
    'execute_width': '.execute_width({execute_width})',
    'lq_width': '.lq_width({lq_width})',
    'sq_width': '.sq_width({sq_width})',
    'retire_width': '.retire_width({retire_width})',
    'mispredict_penalty': '.mispredict_penalty({mispredict_penalty})',
    'decode_latency': '.decode_latency({decode_latency})',
    'dispatch_latency': '.dispatch_latency({dispatch_latency})',
    'schedule_latency': '.schedule_latency({schedule_latency})',
    'execute_latency': '.execute_latency({execute_latency})',
    'dib_set': '  .dib_set({dib_set})',
    'dib_way': '  .dib_way({dib_way})',
    'dib_window': '  .dib_window({dib_window})',
    '_branch_predictor_data': '.branch_predictor<{^branch_predictor_string}>()',
    '_btb_data': '.btb<{^btb_string}>()'
}

dib_builder_parts = {
    'sets': '  .dib_set({DIB[sets]})',
    'ways': '  .dib_way({DIB[ways]})',
    'window_size': '  .dib_window({DIB[window_size]})'
}

cache_builder_parts = {
    'frequency': '.frequency({frequency})',
    'sets': '.sets({sets})',
    'ways': '.ways({ways})',
    'pq_size': '.pq_size({pq_size})',
    'mshr_size': '.mshr_size({mshr_size})',
    'latency': '.latency({latency})',
    'hit_latency': '.hit_latency({hit_latency})',
    'fill_latency': '.fill_latency({fill_latency})',
    'max_tag_check': '.tag_bandwidth({max_tag_check})',
    'max_fill': '.fill_bandwidth({max_fill})',
    '_offset_bits': '.offset_bits({_offset_bits})',
    'prefetch_activate': '.prefetch_activate({^prefetch_activate_string})',
    '_replacement_data': '.replacement<{^replacement_string}>()',
    '_prefetcher_data': '.prefetcher<{^prefetcher_string}>()',
    'lower_translate': '.lower_translate(&{name}_to_{lower_translate}_channel)'
}

def vector_string(iterable):
    ''' Produce a string that avoids a warning on clang under -Wbraced-scalar-init if there is only one member '''
    hoisted = list(iterable)
    if len(hoisted) == 1:
        return hoisted[0]
    return '{'+', '.join(hoisted)+'}'

def get_cpu_builder(cpu):
    required_parts = [
        '.index({_index})',
        '.frequency({frequency})',
        '.l1i(&{L1I})',
        '.l1i_bandwidth({L1I}.MAX_TAG)',
        '.l1d_bandwidth({L1D}.MAX_TAG)',
        '.fetch_queues(&{name}_to_{L1I}_channel)',
        '.data_queues(&{name}_to_{L1D}_channel)'
    ]

    local_params = {
        '^branch_predictor_string': ', '.join(f'{k["class"]}' for k in cpu.get('_branch_predictor_data',[])),
        '^btb_string': ', '.join(f'{k["class"]}' for k in cpu.get('_btb_data',[]))
    }

    builder_parts = itertools.chain(util.multiline(itertools.chain(
        ('O3_CPU {name}{{', 'champsim::core_builder{{ champsim::defaults::default_core }}'),
        required_parts,
        (v for k,v in core_builder_parts.items() if k in cpu),
        (v for k,v in dib_builder_parts.items() if k in cpu.get('DIB',{}))
    ), indent=1, line_end=''), ('}};', ''))
    yield from (part.format(**cpu, **local_params) for part in builder_parts)

def get_cache_builder(elem, upper_levels):
    required_parts = [
        '.name("{name}")',
        '.upper_levels({{{^upper_levels_string}}})',
        '.lower_level(&{name}_to_{lower_level}_channel)'
    ]

    local_cache_builder_parts = {
        ('prefetch_as_load', True): '.set_prefetch_as_load()',
        ('prefetch_as_load', False): '.reset_prefetch_as_load()',
        ('wq_check_full_addr', True): '.set_wq_checks_full_addr()',
        ('wq_check_full_addr', False): '.reset_wq_checks_full_addr()',
        ('virtual_prefetch', True): '.set_virtual_prefetch()',
        ('virtual_prefetch', False): '.reset_virtual_prefetch()'
    }

    local_params = {
        '^defaults': elem.get('_defaults', ''),
        '^upper_levels_string': vector_string("&"+v for v in upper_levels[elem["name"]]["upper_channels"]),
        '^prefetch_activate_string': ', '.join('access_type::'+t for t in elem.get('prefetch_activate',[])),
        '^replacement_string': ', '.join(f'{k["class"]}' for k in elem.get('_replacement_data',[])),
        '^prefetcher_string': ', '.join(f'{k["class"]}' for k in elem.get('_prefetcher_data',[]))
    }

    builder_parts = itertools.chain(util.multiline(itertools.chain(
        ('CACHE {name}{{', 'champsim::cache_builder{{ {^defaults} }}'),
        required_parts,
        (v for k,v in cache_builder_parts.items() if k in elem),
        (v for k,v in local_cache_builder_parts.items() if k[0] in elem and k[1] == elem[k[0]])
    ), indent=1, line_end=''), ('}};', ''))
    yield from (part.format(**elem, **local_params) for part in builder_parts)

def get_ptw_builder(ptw, upper_levels):
    required_parts = [
        '.name("{name}")',
        '.cpu({cpu})',
        '.upper_levels({{{^upper_levels_string}}})',
        '.lower_level(&{name}_to_{lower_level}_channel)',
        '.virtual_memory(&vmem)'
    ]

    local_ptw_builder_parts = {
        ('pscl5_set', 'pscl5_way'): '.add_pscl(5, {pscl5_set}, {pscl5_way})',
        ('pscl4_set', 'pscl4_way'): '.add_pscl(4, {pscl4_set}, {pscl4_way})',
        ('pscl3_set', 'pscl3_way'): '.add_pscl(3, {pscl3_set}, {pscl3_way})',
        ('pscl2_set', 'pscl2_way'): '.add_pscl(2, {pscl2_set}, {pscl2_way})',
        ('mshr_size',): '.mshr_size({mshr_size})',
        ('max_read',): '.tag_bandwidth({max_read})',
        ('max_write',): '.fill_bandwidth({max_write})'
    }

    local_params = {
        '^upper_levels_string': vector_string("&"+v for v in upper_levels[ptw["name"]]["upper_channels"])
    }

    builder_parts = itertools.chain(util.multiline(itertools.chain(
        ('PageTableWalker {name}{{', 'champsim::ptw_builder{{ champsim::defaults::default_ptw }}'),
        required_parts,
        (v for keys,v in local_ptw_builder_parts.items() if any(k in ptw for k in keys))
    ), indent=1, line_end=''), ('}};', ''))
    yield from (part.format(**ptw, **local_params) for part in builder_parts)

def get_ref_vector_function(rtype, func_name, elements):
    if len(elements) > 1:
        open_brace, close_brace = '{{', '}}'
    else:
        open_brace, close_brace = '{', '}'

    wrapped = itertools.chain(
        ('return', open_brace),
        util.append_except_last((f'std::reference_wrapper<{rtype}>{{{elem["name"]}}}' for elem in elements), ','),
        (f'{close_brace};',)
    )
    wrapped = util.multiline(wrapped, length=3, indent=2, line_end='')

    wrapped_rtype = f'std::vector<std::reference_wrapper<{rtype}>>'

    yield from util.cxx_function(func_name, wrapped, rtype=wrapped_rtype, qualifiers=['override'])
    yield ''

def cache_queue_defaults(cache):
    return {
        'rq_size': cache.get('rq_size', cache['_queue_factor']),
        'wq_size': cache.get('wq_size', cache['_queue_factor']),
        'pq_size': cache.get('pq_size', cache['_queue_factor']),
        '_offset_bits': cache['_offset_bits'],
        '_queue_check_full_addr': cache['_queue_check_full_addr']
    }

def ptw_queue_defaults(ptw):
    return {
        'rq_size': ptw.get('rq_size', ptw['_queue_factor']),
        'wq_size': 0,
        'pq_size': 0,
        '_offset_bits': 'champsim::lg2(PAGE_SIZE)',
        '_queue_check_full_addr': False
    }

def named_selector(elem, key):
    return elem.get(key), elem.get('name')

def upper_channel_collector(grouped_by_lower_level):
    return util.chain(*(
        {lower_name: {'upper_channels': [f'{upper_name}_to_{lower_name}_channel']}}
        for lower_name, upper_name in grouped_by_lower_level
    ))

def get_upper_levels(cores, caches, ptws):
    return list(filter(lambda x: x[0] is not None, itertools.chain(
        map(functools.partial(named_selector, key='lower_level'), ptws),
        map(functools.partial(named_selector, key='lower_level'), caches),
        map(functools.partial(named_selector, key='lower_translate'), caches),
        map(functools.partial(named_selector, key='L1I'), cores),
        map(functools.partial(named_selector, key='L1D'), cores)
    )))

def get_instantiation_lines(cores, caches, ptws, pmem, vmem):
    upper_levels = util.chain(
            *util.collect(get_upper_levels(cores, caches, ptws), operator.itemgetter(0), upper_channel_collector),
            *({c['name']: cache_queue_defaults(c)} for c in caches),
            *({p['name']: ptw_queue_defaults(p)} for p in ptws),
            {pmem['name']: {
                    'rq_size':'std::numeric_limits<std::size_t>::max()',
                    'wq_size':'std::numeric_limits<std::size_t>::max()',
                    'pq_size':'std::numeric_limits<std::size_t>::max()',
                    '_offset_bits':'champsim::lg2(BLOCK_SIZE)',
                    '_queue_check_full_addr':False
                }
            }
        )

    yield '// NOLINTBEGIN(readability-magic-numbers,cppcoreguidelines-avoid-magic-numbers): generated magic numbers'
    yield '#include "environment.h"'
    yield '#if __has_include("module_def.inc")'
    yield '#include "module_def.inc"'
    yield '#endif'

    inc_files = set()
    datas = itertools.chain(
        *(c['_branch_predictor_data'] for c in cores),
        *(c['_btb_data'] for c in cores),
        *(c['_prefetcher_data'] for c in caches),
        *(c['_replacement_data'] for c in caches)
    )
    for module_data in datas:
        for base,_,files in os.walk(module_data['path']):
            inc_files.update([os.path.join(base, f) for f in files if os.path.splitext(f)[1] == '.h'])
    yield from ('#include "../../../'+f+'"' for f in inc_files)

    yield '#include "defaults.hpp"'
    yield '#include "vmem.h"'
    yield 'namespace champsim::configured {'
    struct_body = itertools.chain(
        *((queue_fmtstr.format(name=ul_queues, **v) for ul_queues in v['upper_channels']) for v in upper_levels.values()),

        (pmem_fmtstr.format(_ulptr=vector_string('&'+v for v in upper_levels[pmem['name']]['upper_channels']), **pmem),),
        (vmem_fmtstr.format(dram_name=pmem['name'], **vmem),),

        itertools.chain(*map(functools.partial(get_ptw_builder, upper_levels=upper_levels), ptws)),
        itertools.chain(*map(functools.partial(get_cache_builder, upper_levels=upper_levels), caches)),
        itertools.chain(*map(get_cpu_builder, cores)),

        get_ref_vector_function('O3_CPU', 'cpu_view', cores),
        get_ref_vector_function('CACHE', 'cache_view', caches),
        get_ref_vector_function('PageTableWalker', 'ptw_view', ptws),
        get_ref_vector_function('champsim::operable', 'operable_view', list(itertools.chain(cores, caches, ptws, (pmem,)))),

        (f'MEMORY_CONTROLLER& dram_view() override {{ return {pmem["name"]}; }}',)
    )
    yield from util.cxx_struct('generated_environment final', struct_body, superclass='champsim::environment')

    yield '}'
    yield '// NOLINTEND(readability-magic-numbers,cppcoreguidelines-avoid-magic-numbers)'
