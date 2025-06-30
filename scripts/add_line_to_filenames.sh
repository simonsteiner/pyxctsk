#!/bin/bash

# Script to rename files by adding "_line" before file extension
# Usage: ./add_line_to_filenames.sh

# Task names to process
TASK_NAMES=(
    "task_fobe"
    "task_motu"
    "task_piga"
    "task_qoga"
    "task_quno"
)

# Base directory where searches start
BASE_DIR="/home/simon/DEV/git/pyxctsk/scripts/downloaded_tasks"

# Subdirectories to check
SUBDIRS=(
    "html"
    "geojson"
    "html_cleaned"
    "json"
    "xctsk"
)

# Counter for renamed files
renamed_count=0

# Process each task name
for task in "${TASK_NAMES[@]}"; do
    echo "Processing files for $task..."
    
    # Check each subdirectory
    for subdir in "${SUBDIRS[@]}"; do
        dir_path="$BASE_DIR/$subdir"
        
        # Check if directory exists
        if [[ -d "$dir_path" ]]; then
            # Find files with this task name in the current subdirectory
            find "$dir_path" -name "${task}.*" | while read file; do
                if [[ -f "$file" ]]; then
                    # Get directory and filename
                    dir=$(dirname "$file")
                    filename=$(basename "$file")
                    
                    # Get extension
                    extension="${filename##*.}"
                    basename="${filename%.*}"
                    
                    # Create new filename with _line added
                    new_filename="${basename}_line.${extension}"
                    new_filepath="${dir}/${new_filename}"
                    
                    # Rename the file
                    mv "$file" "$new_filepath"
                    echo "  Renamed: $file → $new_filepath"
                    ((renamed_count++))
                fi
            done
        fi
    done
done

echo "Completed renaming $renamed_count files."
