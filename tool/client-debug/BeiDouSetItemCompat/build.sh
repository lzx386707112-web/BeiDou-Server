#!/bin/sh
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_dir=$(CDPATH= cd -- "$script_dir/../../.." && pwd)
python3 "$script_dir/patch_stat_labels.py" "$repo_dir/clien/BeiDouSetItemCompat.dll"
python3 "$script_dir/test_stat_labels_contract.py" "$repo_dir/clien/BeiDouSetItemCompat.dll"
python3 "$script_dir/test_nameplate_series_contract.py" "$repo_dir/clien/BeiDouSetItemCompat.dll"
