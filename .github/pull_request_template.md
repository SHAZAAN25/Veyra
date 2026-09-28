## Description
Brief summary of the changes proposed in this pull request.

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Architectural / Refactoring change (code improvement with identical behavior)
- [ ] Packaging / Deployment improvement
- [ ] Documentation update

## Engineering Invariants Verification
Please confirm that your changes strictly comply with VEYRA core invariants:
- [ ] **Rule 1 (Measurement Integrity):** Zero fabricated, synthetic, or interpolated measurements added.
- [ ] **Rule 9 (Simulation Isolation):** Simulation and chaos code is isolated to `simulation/` or `tests/` and tagged `is_simulation=True`.
- [ ] **Least Privilege:** No blanket Administrator privilege requirements added. Privileged actions route strictly through `PrivilegedHelper`.
- [ ] **Local-First & Offline:** Zero external cloud dependencies, third-party API keys, or off-host telemetry transmission added.
- [ ] **Branding Protection:** Locked branding assets in `assets/branding/` remain completely untouched and byte-identical.

## Testing & Quality Assurance
- [ ] Automated tests added or updated for new functionality.
- [ ] Full test suite passes: `python -m pytest tests/ -q` (all 209+ tests passing with 0 failures).

## Related Issues
Closes #[issue_number]
