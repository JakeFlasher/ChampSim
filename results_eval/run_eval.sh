#!/bin/bash

# Define the paths to the directories
# VANILLA_DIR="vanilla_GAP"
# DELOAD_DIR="deload_GAP"
# OUTPUT_DIR="comparison_GAP"
VANILLA_DIR=$1
DELOAD_DIR=$2
OUTPUT_DIR=$3

# Create the output directory if it doesn't exist
mkdir -p $OUTPUT_DIR

# Define the Python script to use for comparison
COMPARE_SCRIPT="eval.py"

# Loop over each trace length directory
for trace_length in 100M 200M 450M; do
    # Get the list of applications in the vanilla directory for the current trace length
    vanilla_files=$(ls $VANILLA_DIR/$trace_length/*.out)

    for vanilla_file in $vanilla_files; do
        # Extract the application name from the vanilla file path
        app_name=$(basename $vanilla_file .out)

        # Define the corresponding deload file path
        deload_file="$DELOAD_DIR/$trace_length/$app_name.syn.xz.out"

        # Check if the deload file exists
        if [ -f $deload_file ]; then
            # Define the output result file path
            result_file="$OUTPUT_DIR/${app_name}_${trace_length}.res"

            # Run the comparison script and save the result
            python $COMPARE_SCRIPT $vanilla_file $deload_file > $result_file
        else
            echo "Deload file not found for $app_name in $trace_length"
        fi
    done
done
