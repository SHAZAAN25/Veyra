# VEYRA — Non-Negotiable Project Engineering Rules

> **Status:** ACTIVE & MANDATORY  
> **Applicability:** All contributors, maintainers, and developers.

---

### Rule 1: Never Fabricate Measurements
NEVER FABRICATE A MEASUREMENT. This is the permanent core engineering rule of VEYRA.
- Never introduce fake telemetry, placeholder telemetry presented as real, hardcoded production measurements, or random numbers.
- Never introduce guessed Wi-Fi values, guessed packet loss, guessed latency, guessed jitter, guessed GPU temperature, guessed CPU usage, guessed FPS, or fake historical charts.
- If a measurement cannot be obtained, represent the state explicitly (`Unavailable`, `Not supported`, `Stale`, `Permission required`, `Collector unavailable`, `Measurement failed`).

### Rule 2: Preserve Working Functionality
Never break or regress existing, working functionality. Refactoring must be non-destructive and verified against existing regression tests.

### Rule 3: Read Architecture & Contributing Guidelines Before Modifying Code
Every contributor must read [ARCHITECTURE.md](ARCHITECTURE.md) and [CONTRIBUTING.md](CONTRIBUTING.md) before making modifications to any part of the repository. Context and architectural invariants must be respected.

### Rule 4: Never Blindly Rewrite the Repository
Do not blow away directories, reinstall frameworks, or replace foundational code simply to impose personal styling or alternative paradigms.

### Rule 5: Never Silently Change Frozen Architecture
The system architecture (collectors -> analyzer -> storage -> API -> UI) is FROZEN. If an architectural change is believed to be necessary, you must STOP, document the proposal, risks, and rationale, and request explicit approval.

### Rule 6: Acceptance Criteria & Contract Verification
No feature or subsystem may be committed until every single acceptance criterion is satisfied and verified against automated contracts.

### Rule 7: Every Stage Must Have Appropriate Tests
Code without automated test coverage is incomplete. Every contract, parser, collector, and security boundary must have corresponding automated tests.

### Rule 8: UI Must Not Contain Monitoring Logic
The UI is strictly a presentation and interaction layer. The UI must never run ping commands, invoke shell commands, poll system WMI directly, or act as the monitoring engine.

### Rule 9: Simulation Data Must Remain Separate from Production Data
Development test mocks or simulation scenarios must be strictly isolated. Simulation telemetry must never contaminate production storage or masquerade as real hardware measurements.

### Rule 10: Missing Measurements Must Be Explicitly Represented
When a metric cannot be collected (e.g. Wi-Fi metric on an Ethernet connection, or GPU metrics on headless hardware), it must be explicitly tagged with its actual state rather than falling back to `0` or null masquerading as zero.

### Rule 11: Security and Privacy are Mandatory
All network and system commands must execute through hardened, safe subprocess boundaries (`shell=False`, strict timeouts, argument arrays). Path traversal defense is mandatory on all file access.

### Rule 12: Logs Must Not Expose Secrets
Structured logging must sanitize and redact authentication tokens, passwords, API keys, private keys, and sensitive headers.

### Rule 13: VEYRA is Local-First
By default, all APIs, telemetry storage, and UI bindings bind strictly to `127.0.0.1`. Never default to `0.0.0.0`. VEYRA operates without mandatory cloud dependencies or unauthorized telemetry exfiltration.

### Rule 14: Verified Subsystems Must Be Preserved
Core subsystems are stable foundations. Subsequent enhancements must build upon them, not overwrite them.

### Rule 15: Documentation Must Reflect Actual Implementation
Do not document speculative or unimplemented features as existing. Documentation must accurately describe current reality and frozen design contracts.

### Rule 16: Locked Branding Assets Must Remain Immutable
The official VEYRA branding artwork in [assets/branding](assets/branding) is locked and verified by SHA-256 integrity checks. Artwork must never be redrawn, vectorized into alternative designs, recolored, resized with distortion, or replaced. Normal Mode uses the locked cyan artwork; Gaming Mode uses the locked crimson artwork.
