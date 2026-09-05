# ⚡ NEXUS TERMINAL
### Quantitative Market Watchlist & Temporal Intelligence Platform

> An institutional-grade market intelligence terminal designed to answer the investor's core question:  
> **"What has meaningfully changed since I was last here, and what deserves my attention right now?"**

---

## 1. Product Philosophy & Problem Interpretation

### Why Traditional Watchlists Fail
Traditional market watchlists (Yahoo Finance, Apple Stocks, Google Finance) present an unprioritized **"wall of green and red"**:
1. **Context Blindness**: Percentage changes are arbitrarily anchored to market open (9:30 AM) or previous close. An investor checking their screen at 2:15 PM doesn't care about a flat 0.2% day move; they need to know **what happened in the 35 minutes since they last checked**.
2. **Noise Overload**: A +2.5% move in a low-beta utility stock (like Southern Company) is an extraordinary 3.5-sigma statistical tail event, whereas the same +2.5% move in Bitcoin or Tesla is routine intra-day noise. Traditional watchlists treat all percentages equally.
3. **Absence of Significance & Attention Ranking**: Investors are forced to scan dozens of rows manually rather than having critical regime shifts, volume shocks, or idiosyncratic decoupling bubble to the top.

### The NEXUS Platform Architecture
- **Temporal Delta Engine**: Dynamic session checkpoints record the exact state of all instruments whenever you leave or re-anchor, calculating real-time deltas against that exact baseline across multiple time horizons (`Since Last Visit`, `Market Open`, `15m Momentum`, `1-Hour Flash`, `24h Close`).
- **Dual Perspective Engine**:
  - **📊 Quant Mode**: Statistical Z-scores ($\sigma$), Relative Volume (RVOL) surges, beta-adjusted divergence vs SPY, and 52-week support/breakout bounds.
  - **💬 Plain English Mode**: Translates all quantitative anomalies into intuitive, human-understandable explanations with market sentiment moods.
- **Market Sonification Engine (Web Audio API)**:
  - **🎵 Acoustic Market Sweep (`Space`)**: Synthesizes sequential harmonic chords across your portfolio—higher shimmering major notes for advancing assets, deeper resonant tones for declining assets, and attention chimes for anomalies.
  - **🎙️ Spoken Voice Briefing (`B`)**: Synthesizes speech to narrate the executive market briefing aloud.
- **Live Marquee Ticker Tape & Portfolio Breadth**: Real-time ticker tape displaying continuous market updates paired with advancing/declining breadth metrics.
- **Interactive Scenario Simulator (`S`)**: Real-time stress tester allowing you to trigger earnings breakout jumps, flash crashes, regulatory exchange halts, time jumps, and degraded stale feed states.

---

## 2. System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        NEXUS Cockpit Interface                         │
│  (Marquee Tape, Web Audio Sonification, Speech Synthesis, Dark Theme)  │
└──────────────────▲──────────────────────────────▲──────────────────────┘
                   │ REST API                     │ WebSocket (/ws)
┌──────────────────▼──────────────────────────────▼──────────────────────┐
│                            FastAPI Backend                             │
│                                                                        │
│  ┌───────────────────────┐             ┌────────────────────────────┐  │
│  │   API Endpoints       │             │   WebSocket Broadcaster    │  │
│  │ (/watchlists, /since, │             │ (Pub/Sub by Session/Ticker,│  │
│  │  /checkpoint, /shock) │             │  Heartbeats, Differential) │  │
│  └───────────┬───────────┘             └─────────────▲──────────────┘  │
│              │                                       │                 │
│  ┌───────────▼───────────┐             ┌─────────────┴──────────────┐  │
│  │  SQLite Persistence   │             │  Meaningful Change Engine  │  │
│  │ (WAL Mode, Sessions,  │             │  (Z-Scores, RVOL, Attention│  │
│  │  Snapshots, Alerts)   │             │   Score, Dual Perspective) │  │
│  └───────────▲───────────┘             └─────────────▲──────────────┘  │
│              │                                       │                 │
│              └───────────────────┬───────────────────┘                 │
│                                  │                                     │
│                     ┌────────────┴─────────────┐                       │
│                     │ Market Ingestion Engine  │                       │
│                     │ (Stochastic Drift, ADV,  │                       │
│                     │  Poisson Jumps, Stale)   │                       │
│                     └──────────────────────────┘                       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Keyboard Shortcuts

| Key | Action | Description |
|---|---|---|
| <kbd>Space</kbd> | **Acoustic Market Sweep** | Synthesizes a harmonic chord sweep of your entire watchlist |
| <kbd>B</kbd> | **Voice Briefing** | Speaks the executive market briefing aloud using speech synthesis |
| <kbd>M</kbd> | **Mute / Unmute** | Toggles all sonification audio |
| <kbd>C</kbd> | **Checkpoint Baseline** | Re-anchors your baseline comparison to this exact moment |
| <kbd>S</kbd> | **Scenario Simulator** | Opens stress tester (earnings shocks, flash crash, halts) |

---

## 4. Getting Started

### 1. Launch the Server
```powershell
python run_server.py
```
Open your browser to: **`http://127.0.0.1:8000`**

### 2. Run Automated Tests
```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

---

## 5. Verification & Demonstration Flow
1. **Explore Perspectives**: Click between **`📊 Quant Mode`** and **`💬 Plain English`** in the top navigation bar to see the table and executive briefing adapt between quantitative analytics and plain-language accessibility.
2. **Experience Market Sonification**:
   - Press <kbd>Space</kbd> to listen to the 4-second acoustic market sweep.
   - Press <kbd>B</kbd> to hear the narrator read the executive briefing aloud.
3. **Open Scenario Simulator (<kbd>S</kbd>)**:
   - Trigger **`Simulate 45m Away`** to fast-forward your temporal baseline.
   - Trigger **`NVDA Earnings Breakout`** (+11.8%, 4.5x RVOL) to test statistical anomaly detection.
   - Trigger **`Regulatory Exchange Halt`** to test circuit-breaker overrides.
   - Trigger **`Stale Feed Simulator`** to verify feed health warnings.
4. **Deep-Dive Factor Drawer**: Click any ticker to inspect its volatility Z-score, RVOL surge ratio, and S&P 500 alpha divergence.
