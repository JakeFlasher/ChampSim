import re
import sys
import pprint as pp
import numpy as np
from scipy.stats import zscore
from scipy import stats
from sklearn.preprocessing import MinMaxScaler

# Explanation of Scoring Methods:
# IPC Score Formula: Z-score normalization of differences.
# Interpretation: Higher is better, as higher IPC indicates better performance.

# Branch Prediction Score Formula: Combined score of branch prediction accuracy and MPKI.
# Interpretation: Higher accuracy and lower MPKI are better.

# Branch Type Score Formula: Weighted score based on the original counts of branch types.
# Interpretation: Lower MPKI for each branch type is better, weighted by their original occurrence.

# Cache Miss Rate Score Formula: Min-Max normalization of differences.
# Interpretation: Lower miss rates are better.

# TLB Miss Rate Score Formula: Min-Max normalization of differences.
# Interpretation: Lower miss rates are better.

# Cache Miss Latency Score Formula: Min-Max normalization of differences.
# Interpretation: Lower latencies are better.

# Simulation Time and Instructions Score Formula: Combined score of simulation time and instructions.
# Interpretation: Lower simulation time and higher instructions are better.

def parse_champsim_output(filename):
    with open(filename, 'r') as file:
        data = file.read()

    metrics = {}

    # Extract cumulative IPC
    cumulative_ipc_match = re.search(r'CPU 0 cumulative IPC: ([\d.]+)', data)
    # pp.pprint(cumulative_ipc_match)
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

    # Extract Cache and TLB metrics
    cache_levels = ['L1I', 'L1D', 'L2C', 'LLC']
    for level in cache_levels:
        total_access_match = re.search(r'cpu0_' + level + r' TOTAL\s+ACCESS:\s+(\d+)', data)
        miss_match = re.search(r'cpu0_' + level + r' TOTAL\s+.*MISS:\s+(\d+)', data)
        if total_access_match and miss_match:
            total_access = int(total_access_match.group(1))
            miss = int(miss_match.group(1))
            metrics[level.lower() + '_miss_rate'] = (miss / total_access) * 100 if total_access > 0 else 0

    # Extract TLB metrics
    tlb_levels = ['ITLB', 'DTLB', 'STLB']
    for level in tlb_levels:
        total_access_match = re.search(r'cpu0_' + level + r' TOTAL\s+ACCESS:\s+(\d+)', data)
        miss_match = re.search(r'cpu0_' + level + r' TOTAL\s+.*MISS:\s+(\d+)', data)
        if total_access_match and miss_match:
            total_access = int(total_access_match.group(1))
            miss = int(miss_match.group(1))
            metrics[level.lower() + '_miss_rate'] = (miss / total_access) * 100 if total_access > 0 else 0

    # Extract Cache Miss Latencies
    cache_latency_match = re.findall(r'cpu0_([A-Z,1-9]+) AVERAGE MISS LATENCY: ([\d.]+) cycles', data)
    for match in cache_latency_match:
        if match[1] != '-':
            metrics[match[0].lower() + '_miss_latency'] = float(match[1])

    cache_latency_match = re.findall(r'([A-Z]+) AVERAGE MISS LATENCY: ([\d.]+) cycles', data)
    for match in cache_latency_match:
        if match[1] != '-':
            metrics[match[0].lower() + '_miss_latency'] = float(match[1])

    # Extract simulation time and instructions
    simulation_time_match = re.findall(r'Simulation time: (\d+) hr (\d+) min (\d+) sec', data)
    # pp.pprint(simulation_time_match[-1])
    # simulation_time_match = simulation_time_match[-1]
    if simulation_time_match:
        total_seconds = sum(int(x) * 60 ** i for i, x in enumerate(reversed(simulation_time_match[-1])))
        print(total_seconds)
        metrics['simulation_time'] = total_seconds

    instructions_match = re.search(r'Simulation finished CPU 0 instructions: (\d+)', data)
    if instructions_match:
        metrics['instructions'] = int(instructions_match.group(1))

    return metrics

def calculate_percentage_difference(baseline, synthesized):
    differences = {}
    for key in baseline:
        if key in synthesized:
            baseline_value = baseline[key]
            synthesized_value = synthesized[key]
            if isinstance(baseline_value, dict) and isinstance(synthesized_value, dict):
                differences[key] = calculate_percentage_difference(baseline_value, synthesized_value)
            else:
                if baseline_value != 0:
                    diff = ((synthesized_value - baseline_value) / baseline_value) * 100
                    differences[key] = diff
                else:
                    differences[key] = float('inf') if synthesized_value != 0 else 0
    return differences

def flatten_dict(d, parent_key='', sep='_'):
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def calculate_score_ZSCORE(differences, weights):
    # Use z-score normalization to handle differences
    scores = np.array(list(differences.values()))
    normalized_scores = zscore(scores)

    # Calculate weighted sum of normalized scores
    score = 0
    for key, weight in weights.items():
        if key in differences:
            idx = list(differences.keys()).index(key)
            score += weight * normalized_scores[idx]

    # Interpret the score: closer to 0 is better, as it indicates less deviation from the baseline
    return score

def calculate_score_MINMAX(differences, weights):
    # Cache Miss Latency: Lower is better
    scores = -np.array([differences[k] for k in weights.keys() if k in differences])  # Negative because lower is better
    normalized_scores = MinMaxScaler().fit_transform(scores.reshape(-1, 1)).flatten()
    score = np.sum(normalized_scores * np.array([weights[k] for k in weights.keys() if k in differences]))
    return score

# def calculate_score_ipc(differences, weights):
#     # IPC: Higher is better
#     scores = np.array([differences[k] for k in weights.keys() if k in differences])
#     normalized_scores = zscore(scores)  # Z-score normalization
#     score = np.sum(normalized_scores * np.array([weights[k] for k in weights.keys() if k in differences]))
#     return score

# def calculate_score_branch(differences, weights):
#     # Branch Prediction: Higher accuracy is better, lower MPKI is better
#     accuracy_score = differences.get('branch_pred_accuracy', 0)
#     mpki_score = -differences.get('branch_mpki', 0)  # Negative because lower is better
#     combined_score = accuracy_score + mpki_score
#     return combined_score

# def calculate_score_branch_type(differences, weights, baseline_counts):
#     # Branch Type MPKI: Weight by original counts
#     scores = []
#     for key, baseline_count in baseline_counts.items():
#         diff_key = f'branch_type_mpki_{key}'
#         if diff_key in differences:
#             weight = baseline_count / sum(baseline_counts.values())
#             scores.append(differences[diff_key] * weight)
#     total_score = np.sum(scores)
#     return total_score

# def calculate_score_time(differences, weights):
#     # Simulation Time and Instructions: Lower time and higher instructions are better
#     time_score = -differences.get('simulation_time', 0)  # Negative because lower is better
#     instructions_score = differences.get('instructions', 0)
#     combined_score = time_score + instructions_score
#     return combined_score

def main(baseline_file, synthesized_file):
    baseline_metrics = parse_champsim_output(baseline_file)
    synthesized_metrics = parse_champsim_output(synthesized_file)

    differences = calculate_percentage_difference(baseline_metrics, synthesized_metrics)
    flat_differences = flatten_dict(differences)

    print("Differences in metrics (in percentage):")
    for key, value in flat_differences.items():
        print(f"{key}: {value:.2f}%")

    # Define weights for different components
    # ipc_weights = {
    #     'cumulative_ipc': 1.0
    # }
    branch_weights = {
        'branch_pred_accuracy': 0.5,
        'branch_mpki': 0.2
    }


    # Calculate baseline branch type counts for weights
    baseline_branch_counts = baseline_metrics.get('branch_type_mpki', {})

    branch_type_weights = {f'branch_type_mpki_{k}': baseline_branch_counts[k] for k in baseline_branch_counts}
    pp.pprint(branch_type_weights)
    cache_weights = {
        'l1i_miss_rate': 0.1,
        'l1d_miss_rate': 0.1,
        'l2c_miss_rate': 0.1,
        'llc_miss_rate': 0.1
    }
    tlb_weights = {
        'itlb_miss_rate': 0.05,
        'dtlb_miss_rate': 0.05,
        'stlb_miss_rate': 0.05
    }
    latency_weights = {
        'l1i_miss_latency': 0.05,
        'l1d_miss_latency': 0.05,
        'l2c_miss_latency': 0.05,
        'llc_miss_latency': 0.05
    }
    # time_weights = {
    #     'simulation_time': 1.0,
    #     'instructions': 0.5
    # } 

    # Calculate scores for each component
    # ipc_score = calculate_score_ZSCORE(flat_differences, ipc_weights)
    ipc_score = np.abs(flat_differences['cumulative_ipc']/100.0)
    branch_score = np.abs(calculate_score_ZSCORE(flat_differences, branch_weights))
    branch_type_score = np.abs(calculate_score_ZSCORE(flat_differences, branch_type_weights))
    cache_score = np.abs(calculate_score_ZSCORE(flat_differences, cache_weights))
    tlb_score = np.abs(calculate_score_ZSCORE(flat_differences, tlb_weights))
    latency_score = np.abs(calculate_score_ZSCORE(flat_differences, latency_weights))
    # time_score = np.abs(calculate_score_ZSCORE(flat_differences, time_weights))
    speedup = 1/(1-np.abs((flat_differences['simulation_time']/100)))

    print("\nScores:")
    print(f"IPC Score: {ipc_score:.2f}")
    print(f"Branch Prediction Score: {branch_score:.2f}")
    print(f"Branch Type Score: {branch_type_score:.2f}")
    print(f"Cache Miss Rate Score: {cache_score:.2f}")
    print(f"TLB Miss Rate Score: {tlb_score:.2f}")
    print(f"Cache Miss Latency Score: {latency_score:.2f}")
    # print(f"Simulation Time | Instructions Improvments: {time_score:.2f}")
    print(f"Simulation Speedup: {speedup:.2f}")

    # Calculate overall score
    overall_score_g = stats.gmean(np.abs([ipc_score, branch_score, branch_type_score, cache_score, tlb_score, latency_score]))
    overall_score_h = stats.hmean(np.abs([ipc_score, branch_score, branch_type_score, cache_score, tlb_score, latency_score]))
    print(f"\nOverall Score (geo-mean): {overall_score_g:.2f}")
    print(f"Overall Score (h-mean): {overall_score_h:.2f}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python script.py <baseline_file> <synthesized_file>")
        sys.exit(1)

    baseline_file = sys.argv[1]
    synthesized_file = sys.argv[2]

    main(baseline_file, synthesized_file)
