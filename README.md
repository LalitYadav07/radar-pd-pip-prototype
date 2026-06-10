# RADAR-PD internet install prototype

This repository is a temporary distribution prototype for testing a no-copy
install path on a fresh Linux workstation.

It does not replace the main RADAR-PD development repository. It only contains:

- the small `radar-pd` launcher package,
- a Linux x86_64 / Python 3.12 GSAS-II runtime wheel,
- an installer script that creates a venv, installs the package, and clones the
  current RADAR-PD app source from GitHub.

## One-command install test

On a Linux x86_64 workstation with Python 3.12:

```bash
curl -LsSf https://raw.githubusercontent.com/LalitYadav07/radar-pd-pip-prototype/main/install.sh | bash
```

Then launch:

```bash
source ~/radar-pd-env/bin/activate
radar-pd ui --source-root ~/.local/share/radar-pd/source/Impurity_detection_GSAS_ver6
```

If Python 3.12 has a different path:

```bash
curl -LsSf https://raw.githubusercontent.com/LalitYadav07/radar-pd-pip-prototype/main/install.sh \
  | PYTHON_BIN=/path/to/python3.12 bash
```

## What gets installed

The installer:

1. creates `~/radar-pd-env`,
2. installs `radar-pd-gsasii-runtime` from the wheel in this repo,
3. installs `radar-pd[app]` from this repo,
4. clones `https://github.com/LalitYadav07/Impurity_detection_GSAS_ver6.git`
   into `~/.local/share/radar-pd/source/Impurity_detection_GSAS_ver6`,
5. runs `radar-pd doctor --smoke-gsas-project`.

## Manual pip install

If you do not want the script:

```bash
python3.12 -m venv ~/radar-pd-env
source ~/radar-pd-env/bin/activate
python -m pip install --upgrade pip
python -m pip install \
  "radar-pd-gsasii-runtime @ https://raw.githubusercontent.com/LalitYadav07/radar-pd-pip-prototype/main/wheelhouse/radar_pd_gsasii_runtime-0.0.1-cp312-cp312-linux_x86_64.whl" \
  "radar-pd[app] @ git+https://github.com/LalitYadav07/radar-pd-pip-prototype.git#subdirectory=radar_pd"
git clone --depth 1 https://github.com/LalitYadav07/Impurity_detection_GSAS_ver6.git \
  ~/.local/share/radar-pd/source/Impurity_detection_GSAS_ver6
radar-pd doctor --smoke-gsas-project
radar-pd ui --source-root ~/.local/share/radar-pd/source/Impurity_detection_GSAS_ver6
```

## Catalogs and weights

Large catalogs should not be stored in this pip package. They should be
downloaded or copied into the RADAR-PD cache separately:

```bash
radar-pd install-data --source /path/to/catalog --name standard
```

The next production step is to replace this with a pinned bootstrap manifest
that downloads the existing hosted catalog automatically and verifies checksums.

## Scope

This is a fast Linux-only proof of concept. It is not yet a PyPI release.
