#!/usr/bin/env bash

set -euo pipefail

codes_dir="$HOME/eczoo_data/codes"
checklist="$HOME/eczoo_data/scripts/checked_files.txt"

if [[ ! -d "$codes_dir" ]]; then
  echo "Error: directory not found: $codes_dir" >&2
  exit 1
fi

if [[ ! -f "$checklist" ]]; then
  echo "Error: checklist not found: $checklist" >&2
  exit 1
fi

mapfile -t all_files < <(find "$codes_dir" -type f -name '*.yml' | sort)

if [[ ${#all_files[@]} -eq 0 ]]; then
  echo "No YAML files found under $codes_dir" >&2
  exit 1
fi

# Print all YAML files recursively under codes/.
printf '%s\n' "${all_files[@]}"

declare -A checked_paths
declare -A checked_names

while IFS= read -r line; do
  line="${line%%$'\r'}"
  line="${line#${line%%[![:space:]]*}}"
  line="${line%${line##*[![:space:]]}}"
  [[ -z "$line" ]] && continue

  checked_paths["$line"]=1
  checked_names["$(basename "$line")"]=1
done < "$checklist"

candidates=()
for file in "${all_files[@]}"; do
  base_name="$(basename "$file")"
  if [[ -n "${checked_paths[$file]+x}" ]]; then
    continue
  fi
  if [[ -n "${checked_paths[$base_name]+x}" ]]; then
    continue
  fi
  if [[ -n "${checked_names[$base_name]+x}" ]]; then
    continue
  fi
  candidates+=("$file")
done

if [[ ${#candidates[@]} -eq 0 ]]; then
  echo "No unchecked YAML files remain." >&2
  exit 2
fi

selected_file="$(printf '%s\n' "${candidates[@]}" | shuf -n 1)"
echo "$selected_file" >> "$checklist"
echo "Selected and appended: $selected_file"