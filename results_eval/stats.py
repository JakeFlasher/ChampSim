import os
import re
import csv
from glob import glob
import argparse

def extract_application_name(filename):
    """Extract application name from the filename."""
    base_name = os.path.basename(filename)
    name_parts = base_name.split('.')

    return '.'.join(name_parts[:-2]) if len(name_parts) > 2 else name_parts[0]

def parse_results_file(filepath):
    """Parse the results file to extract differences and scores."""
    with open(filepath, 'r') as file:
        data = file.read()

    # Extract differences and scores using regular expressions
    differences = {key: float(value) for key, value in re.findall(r'(\w+): ([\d.-]+)#', data)}
    scores = {key.replace(' ', '_'): float(value) for key, value in re.findall(r'(\w+): ([\d.-]+)%', data)}
    print(scores)
    return differences, scores

def summarize_results(result_files):
    """Summarize the data from all result files."""
    differences_summary = []
    scores_summary = []

    for filepath in result_files:
        app_name = extract_application_name(filepath)
        differences, scores = parse_results_file(filepath)

        # Add application name to the dictionaries
        differences['name'] = app_name
        scores['name'] = app_name

        differences_summary.append(differences)
        scores_summary.append(scores)

    return differences_summary, scores_summary

def write_csv(filepath, data, fieldnames):
    """Write the summarized data to a CSV file."""
    with open(filepath, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

def main(target_folder):
    """Main function to execute the script."""
    # Get all .res files in the target folder
    result_files = glob(os.path.join(target_folder, "*.res"))

    # Summarize results
    differences_summary, scores_summary = summarize_results(result_files)

    # Get all unique keys for differences and scores
    all_diff_keys = ['name'] + sorted({key for d in differences_summary for key in d if key != 'name'})
    all_score_keys = ['name'] + sorted({key for s in scores_summary for key in s if key != 'name'})

    # Write CSV files in the target folder
    write_csv(os.path.join(target_folder, 'differences_summary.csv'), differences_summary, all_diff_keys)
    write_csv(os.path.join(target_folder, 'scores_summary.csv'), scores_summary, all_score_keys)

if __name__ == "__main__":
    # Argument parser to accept the target folder as an argument
    parser = argparse.ArgumentParser(description="Process .res files and summarize results.")
    parser.add_argument('target_folder', type=str, help="The folder containing .res files and where output will be saved.")
    
    args = parser.parse_args()
    main(args.target_folder)