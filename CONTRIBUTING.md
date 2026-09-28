# Contributing to VEYRA

Thank you for your interest in contributing to **VEYRA**! We welcome contributions from systems engineers, UI developers, security researchers, and technical writers.

To maintain the architectural integrity, security boundaries, and measurement truthfulness of VEYRA, all contributors are required to read and adhere to these guidelines.

---

## 1. Core Engineering Invariants (Non-Negotiable)

Before writing any code, understand our foundational principles:

1. **Rule 1 — Never Fabricate a Measurement:**
   VEYRA never introduces synthetic telemetry, guessed Wi-Fi values, fake packet loss, or placeholder historical graphs. If a metric cannot be queried from hardware or OS APIs, report it explicitly as `Unavailable` or `Not Supported`.
2. **Rule 9 — Simulation Isolation:**
   Simulation contracts, chaos injectors, and test harnesses must reside strictly within `simulation/` or `tests/` and embed `is_simulation=True`. Synthetic data must never be committed to production SQLite stores or shipped in release packages.
3. **Least Privilege by Default:**
   The desktop application, collectors, and API must execute as a standard unprivileged user (`asInvoker`). Never introduce code that requires global Administrator rights for general observability.
4. **Local-First & Privacy First:**
   Zero external network calls. No telemetry services (Google Analytics, Sentry, Mixpanel). No cloud LLM dependencies. All network listeners must bind strictly to `127.0.0.1`.
5. **Locked Branding Protection:**
   The official branding assets in `assets/branding/` are locked by SHA-256 manifests. Do not alter, recolor, resize, or replace locked branding assets.

---

## 2. Development Setup

### Prerequisites
- **OS:** Windows 10 (2004+) or Windows 11 (x64).
- **Python:** Python 3.12+ (64-bit).
- **Package Manager:** `uv` (recommended) or standard `pip`.

### Initializing Environment
```powershell
# Clone the repository
git clone https://github.com/SHAZAAN25/Veyra.git
cd Veyra

# Install dependencies in editable mode
pip install -r requirements.txt
pip install pytest psutil pyinstaller pillow
```

### Running Foundation Check
```powershell
python run.py
```

### Running Test Suite
```powershell
python -m pytest tests/ -q
# Ensure all 209+ tests pass with zero failures
```

---

## 3. Development Workflow & Coding Standards

- **Static Typing:** Use Python type annotations (`typing`) across all public functions and dataclasses.
- **Error Containment:** Collector modules must catch hardware timeouts and OS exceptions gracefully without terminating the application process.
- **Monotonic Clocks:** Use `time.monotonic()` for interval tracking, sliding windows, and rate limiters. Use `datetime.now(timezone.utc)` strictly for audit timestamps.
- **Subprocess Security:** Subprocesses must specify explicit argument lists with `shell=False`. Never interpolate untrusted strings into command strings.

---

## 4. Pull Request Checklist

When submitting a pull request, ensure:
1. **Tests Included:** Every new collector, diagnostic test, or optimization module must include comprehensive unit tests under `tests/`.
2. **Full Regression Passes:** The entire test suite must pass with 0 failures, 0 errors, and 0 skips.
3. **Clean Git History:** Commits should follow conventional commit formatting:
   - `feat(...)`: New feature or capability
   - `fix(...)`: Bug fix or edge-case resolution
   - `docs(...)`: Documentation updates
   - `refactor(...)`: Code cleanup without architectural change
   - `test(...)`: Test additions or test harness improvements
4. **No Secrets / Local Caches:** Ensure `.gitignore` is respected. Never commit `.venv`, local `*.sqlite` databases, or personal configuration files.
