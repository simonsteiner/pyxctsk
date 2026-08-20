#!/usr/bin/env bash
# Run the complete, non-mutating release verification gate.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

verify_tmp_dir="$(mktemp -d /tmp/pyxctsk-verify.XXXXXX)"
cleanup() {
  rm -rf -- "$verify_tmp_dir"
}
trap cleanup EXIT

uv lock --check
uv sync --frozen --all-extras
uv run ruff check src/ tests/ scripts/
uv run ruff format --check src/ tests/ scripts/
uv run mypy src/ tests/
uv run pytest

git ls-files -z '*.py' '*.md' '*.txt' '*.toml' '*.yml' '*.yaml' '*.json' '*.cfg' '*.ini' \
  | xargs -0 npx --yes cspell --no-progress --no-must-find-files --config cspell.json

uv build --out-dir "$verify_tmp_dir/dist"

wheel_paths=("$verify_tmp_dir/dist/"*.whl)
if [ "${#wheel_paths[@]}" -ne 1 ] || [ ! -f "${wheel_paths[0]}" ]; then
  echo "Expected exactly one wheel in $verify_tmp_dir/dist." >&2
  exit 1
fi

uv venv "$verify_tmp_dir/core-only"
uv pip install --python "$verify_tmp_dir/core-only/bin/python" "${wheel_paths[0]}"
"$verify_tmp_dir/core-only/bin/python" scripts/check_core_without_qr.py
