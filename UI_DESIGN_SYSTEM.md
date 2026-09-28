# VEYRA — UI Design System Specification

> **Status:** LOCKED DESIGN TOKENS  
> **Modes:** Normal Mode (Cyan) & Gaming Mode (Crimson)  
> **Themes:** Dark (Default), Light (First-class), System

---

## 1. Core Visual Principles

1. **Information Density & Clarity:** VEYRA is a precision tool for network and hardware monitoring. Typography and layout prioritize high legibility, clean visual hierarchies, and micro-interactions.
2. **Brand Immutability:** 
   - Normal Mode displays the **locked cyan logo** directly from `assets/branding/normal/`.
   - Gaming Mode displays the **locked crimson logo** directly from `assets/branding/gaming/`.
   - Under no circumstances is the Normal logo dynamically recolored via CSS filters or canvas to generate the Gaming logo.
   - **`LOGO INTEGRITY > UI CONVENIENCE`**
3. **Seamless Dynamic Mode Switching:** Toggling between Normal and Gaming Mode, or switching themes (Dark, Light, System) must occur immediately in memory without requiring an application restart.

---

## 2. Locked Palette Tokens

### A. Normal Mode Palette (Cyan Accent)

| Token Name | Hex Code | Purpose |
|---|---|---|
| `--color-normal-bg` | `#0B0D10` | Main application background |
| `--color-normal-secondary` | `#12161B` | Sidebars, headers, status bars |
| `--color-normal-cards` | `#181D23` | Metric cards, container panels |
| `--color-normal-borders` | `#2A3139` | Dividers, card strokes, gridlines |
| `--color-normal-text-primary` | `#F1F3F5` | Primary headings, active metrics |
| `--color-normal-text-secondary` | `#9AA3AD` | Subheadings, units, timestamps, metadata |
| `--color-normal-accent` | `#27D3E6` | Primary cyan brand accent, active tabs |
| `--color-normal-healthy` | `#35C99A` | Low latency, zero packet loss, healthy status |
| `--color-normal-warning` | `#E8B84A` | Elevating jitter, Wi-Fi signal drop |
| `--color-normal-high` | `#E8794F` | High packet loss, elevated thermal readings |
| `--color-normal-critical` | `#E05252` | Outages, disconnects, hardware throttling |

### B. Gaming Mode Palette (Crimson Accent)

| Token Name | Hex Code | Purpose |
|---|---|---|
| `--color-gaming-bg` | `#080A0C` | Deep obsidian background |
| `--color-gaming-panels` | `#101418` | Elevated telemetry panels, HUD container |
| `--color-gaming-borders` | `#32252A` | Subtle crimson-tinted borders |
| `--color-gaming-primary` | `#FF3045` | Primary brand crimson accent |
| `--color-gaming-deep-red` | `#B51227` | Secondary crimson for badges, depth strokes |
| `--color-gaming-hot-accent` | `#FF4655` | High-impact alert highlights |
| `--color-gaming-healthy` | `#32D7A0` | Low ping, zero jitter, optimal gaming network |
| `--color-gaming-text` | `#F5F5F5` | Crisp HUD typography |

---

## 3. Typography & Micro-Animations

- **Primary Font:** Inter / Roboto / Segoe UI (Clean modern sans-serif).
- **Monospace Font:** JetBrains Mono / Cascadia Code / Consolas (Used for IP addresses, MACs, latency values, timestamps, and log output).
- **Transitions:** Smooth 150ms-250ms ease-out transitions on hover states, badge changes, and theme shifts.
- **Unavailable States:** Rendered with muted typography (`#5A6470`) and clear text badges (`"NOT CONNECTED"`, `"NOT SUPPORTED"`), never blinking `0` or blank voids.
