#!/usr/bin/env bash
set -euo pipefail

DIST_REPO="${RADAR_PD_DIST_REPO:-https://github.com/LalitYadav07/radar-pd-installer.git}"
RAW_BASE="${RADAR_PD_RAW_BASE:-https://raw.githubusercontent.com/LalitYadav07/radar-pd-installer/main}"
APP_REPO="${RADAR_PD_APP_REPO:-https://github.com/LalitYadav07/Impurity_detection_GSAS_ver6.git}"
PYTHON_BIN="${PYTHON_BIN:-python3.12}"
VENV_DIR="${RADAR_PD_VENV:-$HOME/radar-pd-env}"
SOURCE_DIR="${RADAR_PD_SOURCE_DIR:-$HOME/.local/share/radar-pd/source/Impurity_detection_GSAS_ver6}"
CACHE_HOME="${RADAR_PD_CACHE_HOME:-$HOME/.cache/radar-pd}"
CATALOGS="${RADAR_PD_CATALOGS:-all}"
BOOTSTRAP_DIR="${RADAR_PD_BOOTSTRAP_DIR:-$(pwd)/.radar-pd-bootstrap}"
PYTHON_INSTALL_DIR="${RADAR_PD_PYTHON_INSTALL_DIR:-$BOOTSTRAP_DIR/python}"
UV_BIN="${UV_BIN:-}"
RUNTIME_WHEEL="$RAW_BASE/wheelhouse/radar_pd_gsasii_runtime-0.0.1-cp312-cp312-linux_x86_64.whl"
LAUNCH_SCRIPT="${RADAR_PD_LAUNCH_SCRIPT:-$(pwd)/launch-radar-pd.sh}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3.12 executable '$PYTHON_BIN' was not found."
  echo "Bootstrapping a local Python 3.12 with uv under: $PYTHON_INSTALL_DIR"

  if [[ -z "$UV_BIN" ]]; then
    if command -v uv >/dev/null 2>&1; then
      UV_BIN="$(command -v uv)"
    else
      if ! command -v curl >/dev/null 2>&1; then
        echo "curl is required to install uv when Python 3.12 is missing." >&2
        exit 1
      fi
      mkdir -p "$BOOTSTRAP_DIR/uv"
      echo "Installing uv locally under: $BOOTSTRAP_DIR/uv"
      curl -LsSf https://astral.sh/uv/install.sh | UV_UNMANAGED_INSTALL="$BOOTSTRAP_DIR/uv" sh
      UV_BIN="$BOOTSTRAP_DIR/uv/uv"
    fi
  fi

  "$UV_BIN" python install 3.12 --install-dir "$PYTHON_INSTALL_DIR"
  PYTHON_BIN=""
  for candidate in "$PYTHON_INSTALL_DIR"/*/bin/python3.12; do
    if [[ -x "$candidate" ]]; then
      PYTHON_BIN="$candidate"
      break
    fi
  done
  if [[ -z "$PYTHON_BIN" ]]; then
    echo "uv installed Python 3.12, but no python3.12 executable was found under $PYTHON_INSTALL_DIR" >&2
    exit 1
  fi
  echo "Using bootstrapped Python: $PYTHON_BIN"
fi

"$PYTHON_BIN" - <<'PYTHON_VERSION_CHECK'
import sys
if sys.version_info[:2] != (3, 12):
    raise SystemExit(
        f"RADAR-PD requires Python 3.12, got "
        f"{sys.version_info.major}.{sys.version_info.minor} at {sys.executable}"
    )
PYTHON_VERSION_CHECK

if ! command -v git >/dev/null 2>&1; then
  echo "git is required to fetch the RADAR-PD source checkout." >&2
  exit 1
fi

mkdir -p "$CACHE_HOME"
export RADAR_PD_CACHE_HOME="$CACHE_HOME"

echo "Creating/updating virtual environment: $VENV_DIR"
"$PYTHON_BIN" -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip

echo "Installing RADAR-PD from GitHub..."
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

if [[ "${RADAR_PD_SKIP_CATALOGS:-0}" == "1" ]]; then
  echo "Skipping built-in catalog download because RADAR_PD_SKIP_CATALOGS=1."
else
  catalog_args=(install-catalogs --source-root "$SOURCE_DIR" --catalog "$CATALOGS")
  if [[ "${RADAR_PD_FORCE_CATALOGS:-0}" == "1" ]]; then
    catalog_args+=(--force)
  fi
  echo "Installing built-in RADAR-PD catalogs: $CATALOGS"
  "$VENV_DIR/bin/radar-pd" "${catalog_args[@]}"
fi

mkdir -p "$(dirname "$LAUNCH_SCRIPT")"
cat > "$LAUNCH_SCRIPT" <<LAUNCH_SCRIPT_CONTENT
#!/usr/bin/env bash
set -euo pipefail

PORT="\${1:-8501}"
ADDRESS="\${RADAR_PD_ADDRESS:-127.0.0.1}"
export RADAR_PD_CACHE_HOME="$CACHE_HOME"

exec "$VENV_DIR/bin/radar-pd" ui --source-root "$SOURCE_DIR" --address "\$ADDRESS" --port "\$PORT"
LAUNCH_SCRIPT_CONTENT
chmod +x "$LAUNCH_SCRIPT"

echo
echo "Install complete."
echo
echo "Activate:"
echo "  source \"$VENV_DIR/bin/activate\""
echo
echo "Launch GUI:"
echo "  \"$LAUNCH_SCRIPT\""
echo "  \"$LAUNCH_SCRIPT\" 8502"
echo
echo "If catalogs are not present yet, install/copy them after activation, for example:"
echo "  RADAR_PD_CACHE_HOME=\"$CACHE_HOME\" radar-pd install-data --source /path/to/catalog --name standard"
