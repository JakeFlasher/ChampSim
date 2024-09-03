import re
import sys
import pprint as pp
import numpy as np
from scipy import stats

def parse_champsim_output(filename):
    with open(filename, 'r') as file:
        data = file.read()

    metrics = {}

    # Extract cumulative IPC
    cumulative_ipc_match = re.search(r'CPU 0 cumulative IPC: ([\d.]+)', data)
    if cumulative_ipc_match:
        metrics['cumulative_ipc'] = float(cumulative_ipc_match.group(1))

    # Extract Branch Prediction Accuracy and MPKI
    branch_pred_match = re.search(r'CPU 0 Branch Prediction Accuracy: ([\d.]+)% MPKI: ([\d.]+)', data)
    if branch_pred_match:
        metrics['branch_pred_accuracy'] = float(branch_pred_match.group(1))
        metrics['branch_mpki'] = float(branch_pred_match.group(2))

    # Extract Branch Type MPKI
    branch_type_mpki = {}
    branch_type_match = re.findall(r'BRANCH_([A-Z_]+): ([\d.e-]+)', data)
    for match in branch_type_match:
        branch_type_mpki[match[0]] = float(match[1])
    metrics['branch_type_mpki'] = branch_type_mpki

    # Group Cache Miss Rates
    cache_miss_rate = {}
    cache_miss_latency = {}
    cache_levels = ['L1I', 'L1D', 'L2C', 'LLC']
    cache_latency_match = {}
    for level in cache_levels:
        if level == 'LLC':
            total_access_match = re.search(r'LLC TOTAL\s+ACCESS:\s+(\d+)', data)
            miss_match = re.search(r'LLC TOTAL\s+.*MISS:\s+(\d+)', data)
            cache_latency_match = re.search(r'LLC AVERAGE MISS LATENCY: ([\d.]+) cycles', data)
            # print("laten", cache_latency_match)
        else:
            total_access_match = re.search(r'cpu0_' + level + r' TOTAL\s+ACCESS:\s+(\d+)', data)
            miss_match = re.search(r'cpu0_' + level + r' TOTAL\s+.*MISS:\s+(\d+)', data)
            cache_latency_match = re.search(r'cpu0_' + level + r' AVERAGE MISS LATENCY: ([\d.]+) cycles', data)
            # print("laten", cache_latency_match)

        if total_access_match and miss_match:
            total_access = int(total_access_match.group(1))
            miss = int(miss_match.group(1))
            cache_miss_rate[level.lower()] = (miss / total_access) * 100 if total_access > 0 else 0

        # cache_latency_match += re.findall(r'LLC AVERAGE MISS LATENCY: ([\d.]+) cycles', data)
        if cache_latency_match:
            cache_miss_latency[level.lower()] = float(cache_latency_match.group(1))

    metrics['cache_miss_latency'] = cache_miss_latency
    metrics['cache_miss_rate'] = cache_miss_rate


    # Group TLB Miss Rates
    tlb_miss_rate = {}
    # Group TLB Miss Latencies
    tlb_miss_latency = {}
    tlb_levels = ['ITLB', 'DTLB', 'STLB']
    for level in tlb_levels:
        total_access_match = re.search(r'cpu0_' + level + r' TOTAL\s+ACCESS:\s+(\d+)', data)
        tlb_latency_match = re.search(r'cpu0_' + level + r' AVERAGE MISS LATENCY: ([\d.]+) cycles', data) 
        miss_match = re.search(r'cpu0_' + level + r' TOTAL\s+.*MISS:\s+(\d+)', data)
        if total_access_match and miss_match:
            total_access = int(total_access_match.group(1))
            miss = int(miss_match.group(1))
            tlb_miss_rate[level.lower()] = (miss / total_access) * 100 if total_access > 0 else 0
        if tlb_latency_match:
            tlb_miss_latency[level.lower()] = float(tlb_latency_match.group(1))
    metrics['tlb_miss_rate'] = tlb_miss_rate
    metrics['tlb_miss_latency'] = tlb_miss_latency

    # Extract simulation time and instructions
    simulation_time_match = re.findall(r'Simulation time: (\d+) hr (\d+) min (\d+) sec', data)
    if simulation_time_match:
        total_seconds = sum(int(x) * 60 ** i for i, x in enumerate(reversed(simulation_time_match[-1])))
        metrics['simulation_time'] = total_seconds

    instructions_match = re.search(r'Simulation finished CPU 0 instructions: (\d+)', data)
    if instructions_match:
        metrics['instructions'] = int(instructions_match.group(1))

    return metrics

def calculate_weighted_score(baseline, synthesized, baseline_counts):
    weighted_diffs = {}
    total_baseline = sum(baseline_counts.values())
    cnt = 0
    for key, baseline_value in baseline.items():
        if key in synthesized:
            synthesized_value = synthesized[key]
            weight = baseline_counts.get(key, 0) / total_baseline if total_baseline > 0 else 0
            weighted_diffs[key] = weight * abs(synthesized_value - baseline_value)
            cnt += abs(synthesized_value - baseline_value)
    return cnt / total_baseline 

def flatten_dict(d, parent_key='', sep='_'):
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

def calculate_absolute_difference(baseline, synthesized):
    differences = {}
    for key in baseline:
        if key in synthesized:
            baseline_value = baseline[key]
            synthesized_value = synthesized[key]
            if isinstance(baseline_value, dict) and isinstance(synthesized_value, dict):
                differences[key] = calculate_absolute_difference(baseline_value, synthesized_value)
            else:
                # if baseline_value != 0:
                diff = (synthesized_value - baseline_value)
                # diff = np.abs(synthesized_value - baseline_value)
                differences[key] = diff
                # else:
                    # differences[key] = float('inf') if synthesized_value != 0 else 0
    return differences

# def calculate_weighted_score(differences):
#     return sum(differences.values())
def weighted_score(groupname, baseline_metrics, synthesized_metrics):
    # Calculate baseline branch type counts for weights
    baseline_counts = baseline_metrics.get(groupname, {})

    # Calculate weighted differences for branch type MPKI
    w_diffs = calculate_weighted_score(
        baseline_metrics.get(groupname, {}),
        synthesized_metrics.get(groupname, {}),
        baseline_counts
    )    

    return w_diffs

def single_val_score(key, baseline, flat_diff):
    return (flat_diff[key]/baseline[key])


def main(baseline_file, synthesized_file):
    baseline_metrics = parse_champsim_output(baseline_file)
    synthesized_metrics = parse_champsim_output(synthesized_file)

    pp.pprint(baseline_metrics)
    pp.pprint(synthesized_metrics)
    abs_differences = calculate_absolute_difference(baseline_metrics, synthesized_metrics)
    flat_differences = flatten_dict(abs_differences)

    print("Differences in metrics (in raw):")
    for key, value in flat_differences.items():
        print(f"{key}: {value:.4f}#")

    # Calculate weighted differences for branch type MPKI
    branch_type_diffs = weighted_score('branch_type_mpki', baseline_metrics, synthesized_metrics)
    cache_miss_diffs = weighted_score('cache_miss_rate', baseline_metrics, synthesized_metrics)
    cache_lat_diffs = weighted_score('cache_miss_latency', baseline_metrics, synthesized_metrics)
    tlb_miss_diffs = weighted_score('tlb_miss_rate', baseline_metrics, synthesized_metrics)
    tlb_lat_diffs = weighted_score('tlb_miss_latency', baseline_metrics, synthesized_metrics)
    # Flatten differences for easier processing
    # flat_branch_type_diffs = flatten_dict(branch_type_diffs)
    ipc_score = single_val_score('cumulative_ipc', baseline_metrics, flat_differences)
    speedup =  baseline_metrics['simulation_time']/synthesized_metrics['simulation_time'] 
    bp_acc =  single_val_score('branch_pred_accuracy', baseline_metrics, flat_differences) 
    time_score = single_val_score('instructions', baseline_metrics, flat_differences)
    # Calculate the weighted score for branches
    # branch_type_score = calculate_weighted_score(flat_branch_type_diffs)
 
    print(f"Weighted Scores of Total Changes for each Component: ")
    print(f"IPC_Var: {ipc_score:.2%}")
    print(f"BP_Accuracy: {bp_acc:.2%}")
    print(f"Sim_Speedup: {speedup:.2%}")
    print(f"Instr_Reduced: {time_score:.2%}")
    print(f"Branch_Type: {branch_type_diffs:.2%}")
    print(f"Cache_Miss: {cache_miss_diffs:.2%}")
    print(f"Cache_Latency: {cache_lat_diffs:.2%}")
    print(f"TLB_Miss: {tlb_miss_diffs:.2%}")
    print(f"TLB_Latency: {tlb_lat_diffs:.2%}")

    arr = np.array(np.abs([ipc_score, bp_acc, branch_type_diffs, cache_miss_diffs, tlb_miss_diffs, cache_lat_diffs, tlb_lat_diffs]))
    arr = arr[arr != 0]
    # Calculate overall score
    overall_score_g = stats.gmean(np.abs(arr))
    overall_score_h = stats.hmean(np.abs(arr))
    # overall_score_h = stats.hmean(np.abs([ipc_score, branch_score, branch_type_score, cache_score, tlb_score, latency_score]))
    print(f"zOverall_geomean: {overall_score_g:.2%}")
    print(f"zOverall_hmean: {overall_score_h:.2%}")
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python script.py <baseline_file> <synthesized_file>")
        sys.exit(1)

    baseline_file = sys.argv[1]
    synthesized_file = sys.argv[2]

    main(baseline_file, synthesized_file)