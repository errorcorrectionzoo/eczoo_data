#!/bin/bash

# Function to download paper using arxiv_id from the given json_file
download_paper() {
    local json_file="$1"
    local dir_path=$(dirname "$json_file")
    
    # Extract the arxiv_id from the JSON file
    arxiv_id=$(jq -r '.arxiv_id' "$json_file")

    # Validate if the arxiv_id was successfully extracted and is not null
    if [[ -n "$arxiv_id" && "$arxiv_id" != "null" ]]; then
        # Construct the URL for downloading the paper
        url="https://arxiv.org/pdf/${arxiv_id}.pdf"

        # Download the paper
        echo "Downloading paper from $url to $dir_path/arxiv.pdf"
        curl -L -o "$dir_path/arxiv.pdf" "$url"

        echo "Download completed: $dir_path/arxiv.pdf"
    else
        echo "Error: ArXiv ID not found or is null in $json_file"
    fi
}

export -f download_paper

# Find all arxiv_id.json files and process them
find . -name 'arxiv_id.json' -exec bash -c 'download_paper "$0"' {} \;

