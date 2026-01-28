# Seller Opportunity Scanner — Setup Guide

**Target machine:** macOS Apple Silicon (M1 / M2 / M4 family)
**Repo location:** `~/Desktop/ANALYZER/seller-opportunity-scanner`
**Python version:** 3.11+ (guide installs 3.11 via Homebrew if needed)

---

## What will happen

1. You will install Homebrew (if missing) and Python 3.11 (if missing).
2. You will create a Python virtual environment inside the repo.
3. You will install all project dependencies (~30 packages including PyQt6).
4. You will copy the credentials template to `~/.seller-opportunity-scanner/.env`.
5. You will run the test suite (48 tests) to verify everything works.
6. You will launch the GUI in mock mode (no API keys needed).

Total time on a fresh machine: roughly 5–10 minutes, mostly waiting for `pip install`.

---

## Step-by-step setup

### Step 1 — Open Terminal

Open **Terminal.app** (press ⌘ Space, type `Terminal`, press Enter). All commands below go here.

---

### Step 2 — Check for Python 3.11+

```bash
python3 --version
```

You need `Python 3.11.x` or `3.12.x` or `3.13.x` or `3.14.x`. If you see that, skip to Step 5.

If the command is not found or shows `3.10` or older, continue to Step 3.

---

### Step 3 — Install Homebrew (skip if you already have it)

Check first:

```bash
brew --version
```

If `brew` is not found, install it:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

This takes 1–3 minutes. When it finishes, it prints instructions to add Homebrew to your PATH. Run the two lines it shows, which look like:

```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

**Success looks like:** `brew --version` prints `Homebrew 4.x.x`.

**If it fails:**

```bash
# Check: can you reach the internet?
curl -I https://raw.githubusercontent.com
# Check: is Xcode CLI installed?
xcode-select --install
# Check: is /opt/homebrew writable?
ls -la /opt/homebrew
```

---

### Step 4 — Install Python 3.11

```bash
brew install python@3.11
```

Wait 1–2 minutes. Then verify:

```bash
python3.11 --version
```

**Success looks like:** `Python 3.11.x`.

If `python3.11` is not on your PATH after install:

```bash
export PATH="/opt/homebrew/opt/python@3.11/bin:$PATH"
```

**If it fails:**

```bash
brew doctor
brew update && brew install python@3.11
which python3.11
```

---

### Step 5 — Navigate to the repo

```bash
cd ~/Desktop/ANALYZER/seller-opportunity-scanner
```

Verify you're in the right place:

```bash
ls pyproject.toml src/main.py
```

**Success looks like:** both files listed without errors.

---

### Step 6 — Remove any old virtual environment

If a `venv` folder already exists from a previous attempt, remove it to start clean:

```bash
rm -rf venv
```

---

### Step 7 — Create the virtual environment

Use whichever Python you have. Try `python3.11` first, fall back to `python3`:

```bash
python3.11 -m venv venv || python3 -m venv venv
```

**Success looks like:** no output and a `venv/` directory was created.

Verify:

```bash
ls venv/bin/python
```

**If it fails:**

```bash
# Check: does your Python have venv?
python3.11 -m ensurepip --default-pip
python3.11 -m venv venv
# Check: disk space
df -h .
# Check: Python location
which python3.11
```

---

### Step 8 — Activate the virtual environment

```bash
source venv/bin/activate
```

**Success looks like:** your prompt changes to start with `(venv)`.

Verify the right Python is active:

```bash
which python
```

Should print something like `.../seller-opportunity-scanner/venv/bin/python`.

---

### Step 9 — Upgrade pip

```bash
python -m pip install --upgrade pip
```

**Success looks like:** `Successfully installed pip-XX.X`.

---

### Step 10 — Install the project and all dependencies

```bash
python -m pip install -e ".[dev]"
```

**This is the longest step.** It downloads and installs ~30 packages including PyQt6, SQLAlchemy, pandas, boto3, pytest, and PyInstaller. On a fast connection it takes 1–3 minutes.

**Success looks like:** the last lines say `Successfully installed ... seller-opportunity-scanner-1.0.0` and there are no red `ERROR` lines.

**If it fails:**

```bash
# Re-run with verbose output to see what broke:
python -m pip install -e ".[dev]" -v 2>&1 | tail -80
# Check: is pip working at all?
python -m pip --version
# Check: are you in the venv?
which python
```

---

### Step 11 — Create the config directory and credentials file

```bash
mkdir -p ~/.seller-opportunity-scanner
```

```bash
cp .env.example ~/.seller-opportunity-scanner/.env
```

**Success looks like:** the file exists:

```bash
cat ~/.seller-opportunity-scanner/.env
```

You should see the template with `your_keepa_api_key_here` placeholders.

---

### Step 12 — Enable mock mode in the .env file

For your first launch, you do not need real API keys. Enable mock mode:

```bash
sed -i '' 's/SOS_MOCK_MODE=false/SOS_MOCK_MODE=true/' ~/.seller-opportunity-scanner/.env
```

Verify:

```bash
grep MOCK ~/.seller-opportunity-scanner/.env
```

**Success looks like:** `SOS_MOCK_MODE=true`.

---

### Step 13 — Run the test suite

```bash
python -m pytest tests/ -v
```

**Success looks like:**

```
tests/test_csv_importer.py::TestCsvValidation::test_valid_headers PASSED
tests/test_csv_importer.py::TestCsvValidation::test_missing_headers PASSED
...
tests/test_shipping.py::TestShippingCalculator::test_get_tier PASSED

============= 48 passed in 0.XXs =============
```

All 48 tests should say `PASSED`. Zero `FAILED` or `ERROR`.

**If tests fail:**

```bash
# Run a single test file to isolate:
python -m pytest tests/test_models.py -v
# Check: can Python import the project?
python -c "from src.core.models import Brand; print(Brand.values())"
# Check: is SQLAlchemy importable?
python -c "import sqlalchemy; print(sqlalchemy.__version__)"
```

---

### Step 14 — Launch the GUI in mock mode

```bash
python -m src.main
```

**Success looks like:** a desktop window titled **"Seller Opportunity Scanner"** appears with tabs (Makita, DeWalt, Timco, Mappings, Imports, Settings, Diagnostics). The terminal prints log lines like:

```
INFO src.main: Starting Seller Opportunity Scanner
INFO src.main: Mock mode: True
INFO src.main: Database initialized
INFO src.main: Application started
```

Close the window normally (⌘ Q or click the red X) to shut down.

**If the window does not appear:**

```bash
# Check: is PyQt6 installed?
python -c "from PyQt6.QtWidgets import QApplication; print('OK')"
# Check: is there an error in the terminal output?
python -m src.main 2>&1 | tail -50
# Check: are you running from the repo root?
pwd
ls src/main.py
```

---

### Step 15 — Launch the GUI in live mode (with real API keys)

Edit the `.env` file with your real credentials:

```bash
nano ~/.seller-opportunity-scanner/.env
```

Replace the placeholder values for `SOS_KEEPA_API_KEY`, `SOS_SPAPI_*` fields with your real keys. Change `SOS_MOCK_MODE=true` back to `SOS_MOCK_MODE=false`. Save (Ctrl+O, Enter, Ctrl+X).

Then launch:

```bash
python -m src.main
```

The app will now make real API calls to Keepa and Amazon SP-API when you click **Start Refresh**.

---

## If you get stuck — paste this

Run these five commands, copy the entire terminal output, and paste it back:

```bash
echo "=== 1. Python ===" && python3 --version 2>&1 && python3.11 --version 2>&1 && which python3.11 2>&1
echo "=== 2. Venv ===" && ls -la ~/Desktop/ANALYZER/seller-opportunity-scanner/venv/bin/python 2>&1
echo "=== 3. Pip ===" && ~/Desktop/ANALYZER/seller-opportunity-scanner/venv/bin/python -m pip --version 2>&1
echo "=== 4. Key packages ===" && ~/Desktop/ANALYZER/seller-opportunity-scanner/venv/bin/python -c "import PyQt6, sqlalchemy, pydantic; print('PyQt6 OK, SA', sqlalchemy.__version__, 'pydantic', pydantic.__version__)" 2>&1
echo "=== 5. App launch ===" && cd ~/Desktop/ANALYZER/seller-opportunity-scanner && source venv/bin/activate && python -m src.main 2>&1 | head -50
```

---

## Optional nice-to-haves

### A — Build a standalone macOS .app bundle

From the repo root, with the venv active:

```bash
python -m PyInstaller seller_scanner.spec --noconfirm
```

This takes 1–3 minutes. The result is at:

```
dist/Seller Opportunity Scanner.app
```

Double-click it in Finder to launch without Terminal.

---

### B — Create a Dock / Desktop shortcut

After building the `.app`:

```bash
cp -r "dist/Seller Opportunity Scanner.app" /Applications/
```

Then find it in Launchpad or drag it to the Dock.

---

### C — Run the app as a one-liner from anywhere

Add an alias to your shell profile:

```bash
echo 'alias seller-scanner="cd ~/Desktop/ANALYZER/seller-opportunity-scanner && source venv/bin/activate && python -m src.main"' >> ~/.zshrc
source ~/.zshrc
```

Then just type `seller-scanner` in any Terminal window.

---

### D — Export data

Inside the app, open any brand tab (Makita / DeWalt / Timco) and click **Export** to save the current view as `.xlsx` or `.csv`.

---

## One-shot automated setup (optional)

> **WARNING:** This single command installs Homebrew (if missing), installs Python 3.11 (if missing), creates a venv, installs all dependencies, sets up the config directory with mock mode, runs tests, and launches the GUI. It will modify your system. Read it before running.

```bash
(command -v brew >/dev/null || /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)") && eval "$(/opt/homebrew/bin/brew shellenv)" && (command -v python3.11 >/dev/null || brew install python@3.11) && cd ~/Desktop/ANALYZER/seller-opportunity-scanner && rm -rf venv && python3.11 -m venv venv && source venv/bin/activate && python -m pip install --upgrade pip && python -m pip install -e ".[dev]" && mkdir -p ~/.seller-opportunity-scanner && cp .env.example ~/.seller-opportunity-scanner/.env && sed -i '' 's/SOS_MOCK_MODE=false/SOS_MOCK_MODE=true/' ~/.seller-opportunity-scanner/.env && python -m pytest tests/ -v && python -m src.main
```
