#!/usr/bin/env bash
set -euo pipefail

DIST_REPO="${RADAR_PD_DIST_REPO:-https://github.com/LalitYadav07/radar-pd-pip-prototype.git}"
RAW_BASE="${RADAR_PD_RAW_BASE:-https://raw.githubusercontent.com/LalitYadav07/radar-pd-pip-prototype/main}"
APP_REPO="${RADAR_PD_APP_REPO:-https://github.com/LalitYadav07/Impurity_detection_GSAS_ver6.git}"
PYTHON_BIN="${PYTHON_BIN:-python3.12}"
VENV_DIR="${RADAR_PD_VENV:-$HOME/radar-pd-env}"
SOURCE_DIR="${RADAR_PD_SOURCE_DIR:-$HOME/.local/share/radar-pd/source/Impurity_detection_GSAS_ver6}"
RUNTIME_WHEEL="$RAW_BASE/wheelhouse/radar_pd_gsasii_runtime-0.0.1-cp312-cp312-linux_x86_64.whl"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3.12 is required. Set PYTHON_BIN=/path/to/python3.12 if needed." >&2
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "git is required to fetch the RADAR-PD source checkout." >&2
  exit 1
fi

echo "Creating/updating virtual environment: $VENV_DIR"
"$PYTHON_BIN" -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip

echo "Installing RADAR-PD prototype from GitHub..."
"$VENV_DIR/bin/python" -m pip install \
  "radar-pd-gsasii-runtime @ $RUNTIME_WHEEL" \
  "radar-pd[app] @ git+$DIST_REPO#subdirectory=radar_pd"

if [[ -d "$SOURCE_DIR/.git" ]]; then
  echo "Updating RADAR-PD source checkout: $SOURCE_DIR"
  git -C "$SOURCE_DIR" pull --ff-only
else
  echo "Cloning RADAR-PD source checkout: $SOURCE_DIR"
  mkdir -p "$(dirname "$SOURCE_DIR")"
  git clone --depth 1 "$APP_REPO" "$SOURCE_DIR"
fi

echo "Running GSAS-II smoke diagnostic..."
"$VENV_DIR/bin/radar-pd" doctor --smoke-gsas-project

echo
echo "Install complete."
echo
echo "Activate:"
echo "  source \"$VENV_DIR/bin/activate\""
echo
echo "Launch GUI:"
echo "  \"$VENV_DIR/bin/radar-pd\" ui --source-root \"$SOURCE_DIR\""
echo
echo "If catalogs are not present yet, install/copy them after activation, for example:"
echo "  radar-pd install-data --source /path/to/catalog --name standard"
