#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
workspace="${1:-$HOME/Jobber}"
python_bin="${PYTHON_BIN:-python3}"
venv="$project_root/.venv"

"$python_bin" -m venv "$venv"
"$venv/bin/python" -m pip install --upgrade pip
"$venv/bin/python" -m pip install -e "$project_root[browser]"
"$venv/bin/job-agent" init "$workspace"

echo "Jobber is installed in $venv"
echo "Workspace selected: $workspace"
echo "Next: edit $workspace/candidate/profile.yaml"
echo "Then run: $venv/bin/job-agent web"
