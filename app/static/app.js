/**
 * NEXUS - Quantitative Watchlist & Temporal Intelligence
 * Complete client-side controller featuring:
 * - Real-Time WebSocket differential updates
 * - Temporal Delta Engine across multiple baselines
 * - Dual Perspective Mode: Quant Mode vs Plain English
 * - Market Sonification (Web Audio API acoustic chord sweep)
 * - Spoken Voice Audio Briefing (SpeechSynthesis)
 * - Live Marquee Ticker Tape & Market Breadth Bar
 * - Keyboard shortcuts (Space, B, M, C, S)
 * - Scenario Simulator & Stress Tester
 */

class NexusTerminalApp {
  constructor() {
    this.sessionId = localStorage.getItem("nexus_session_id") || "nexus-" + Math.random().toString(36).substring(2, 9);
    localStorage.setItem("nexus_session_id", this.sessionId);

    this.activeWatchlistId = null;
    this.watchlists = [];
    this.tickers = [];
    this.baselineType = "last_visit";
    this.appMode = "quant"; // 'quant' or 'plain'
    this.currentFilter = "all";
    this.currentSort = "attention";
    this.isMuted = false;
    this.isSpeaking = false;
    this.audioCtx = null;
    this.ws = null;
    this.reconnectTimer = null;
    this.lastPrices = new Map();

    this.initElements();
    this.bindEvents();
    this.bindKeyboardShortcuts();
    this.initSession();
  }

  initElements() {
    this.feedStatusText = document.getElementById("feedStatusText");
    this.statusDot = document.getElementById("statusDot");
    this.briefingBadge = document.getElementById("briefingBadge");
    this.briefingMood = document.getElementById("briefingMood");
    this.briefingTime = document.getElementById("briefingTime");
    this.briefingStats = document.getElementById("briefingStats");
    this.briefingHeadline = document.getElementById("briefingHeadline");
    this.briefingTakeaways = document.getElementById("briefingTakeaways");
    this.tickerTapeContent = document.getElementById("tickerTapeContent");
    this.breadthUp = document.getElementById("breadthUp");
    this.breadthDown = document.getElementById("breadthDown");
    this.breadthRatio = document.getElementById("breadthRatio");
    this.sectorChips = document.getElementById("sectorChips");
    this.watchlistTabs = document.getElementById("watchlistTabs");
    this.tableHead = document.getElementById("watchlistTableHead");
    this.tableBody = document.getElementById("watchlistTableBody");
    this.searchUniverseInput = document.getElementById("searchUniverseInput");
    this.autocompleteDropdown = document.getElementById("autocompleteDropdown");
    this.sortSelect = document.getElementById("sortSelect");

    // Audio Elements
    this.btnAudioSweep = document.getElementById("btnAudioSweep");
    this.btnAudioBriefing = document.getElementById("btnAudioBriefing");
    this.btnAudioMute = document.getElementById("btnAudioMute");

    // Perspective Buttons
    this.btnModeQuant = document.getElementById("btnModeQuant");
    this.btnModePlain = document.getElementById("btnModePlain");

    // Modals & Drawer
    this.drawerOverlay = document.getElementById("drawerOverlay");
    this.drawerPanel = document.getElementById("drawerPanel");
    this.labModal = document.getElementById("labModal");
    this.createWlModal = document.getElementById("createWlModal");
    this.toastContainer = document.getElementById("toastContainer");
  }

  bindEvents() {
    // Mode Switcher (Quant vs Plain English)
    this.btnModeQuant.addEventListener("click", () => this.setMode("quant"));
    this.btnModePlain.addEventListener("click", () => this.setMode("plain"));

    // Audio Sonification triggers
    this.btnAudioSweep.addEventListener("click", () => this.playAcousticSweep());
    this.btnAudioBriefing.addEventListener("click", () => this.toggleVoiceBriefing());
    this.btnAudioMute.addEventListener("click", () => this.toggleMute());

    // Baseline switcher
    document.querySelectorAll(".baseline-btn").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        document.querySelectorAll(".baseline-btn").forEach((b) => b.classList.remove("active"));
        e.currentTarget.classList.add("active");
        this.baselineType = e.currentTarget.dataset.baseline;
        this.fetchBriefing();
        this.sendWsBaseline();
      });
    });

    // Filter pills
    document.querySelectorAll(".filter-pill").forEach((pill) => {
      pill.addEventListener("click", (e) => {
        document.querySelectorAll(".filter-pill").forEach((p) => p.classList.remove("active"));
        e.currentTarget.classList.add("active");
        this.currentFilter = e.currentTarget.dataset.filter;
        this.renderTable();
      });
    });

    // Sort select
    this.sortSelect.addEventListener("change", (e) => {
      this.currentSort = e.target.value;
      this.renderTable();
    });

    // Checkpoint button
    document.getElementById("btnCheckpoint").addEventListener("click", () => this.checkpointSession());

    // Lab Modal toggles
    document.getElementById("btnOpenLab").addEventListener("click", () => this.openModal(this.labModal));
    document.getElementById("btnCloseLab").addEventListener("click", () => this.closeModal(this.labModal));

    // Create Watchlist toggles
    document.getElementById("btnNewWatchlist").addEventListener("click", () => this.openModal(this.createWlModal));
    document.getElementById("btnCloseCreateWl").addEventListener("click", () => this.closeModal(this.createWlModal));
    document.getElementById("btnCancelCreateWl").addEventListener("click", () => this.closeModal(this.createWlModal));
    document.getElementById("btnConfirmCreateWl").addEventListener("click", () => this.createWatchlist());

    // Drawer close
    document.getElementById("btnCloseDrawer").addEventListener("click", () => this.closeDrawer());
    this.drawerOverlay.addEventListener("click", (e) => {
      if (e.target === this.drawerOverlay) this.closeDrawer();
    });

    // Search autocomplete
    let debounceTimer;
    this.searchUniverseInput.addEventListener("input", (e) => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => this.searchUniverse(e.target.value), 200);
    });

    document.addEventListener("click", (e) => {
      if (!this.searchUniverseInput.contains(e.target) && !this.autocompleteDropdown.contains(e.target)) {
        this.autocompleteDropdown.style.display = "none";
      }
    });

    // Scenario simulator buttons
    document.getElementById("btnSimTimeJump").addEventListener("click", () => this.triggerShock("time_jump", 45));
    document.getElementById("btnSimEarnings").addEventListener("click", () => this.triggerShock("earnings_beat", 11.8, "NVDA"));
    document.getElementById("btnSimCrash").addEventListener("click", () => this.triggerShock("flash_crash", 7.8, "TSLA"));
    document.getElementById("btnSimHalt").addEventListener("click", () => this.triggerShock("halt", 0.0, "NVDA"));
    document.getElementById("btnSimStale").addEventListener("click", () => this.triggerShock("stale_toggle"));
  }

  bindKeyboardShortcuts() {
    window.addEventListener("keydown", (e) => {
      // Ignore if typing inside input
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT") {
        return;
      }

      if (e.code === "Space") {
        e.preventDefault();
        this.playAcousticSweep();
      } else if (e.key === "b" || e.key === "B") {
        e.preventDefault();
        this.toggleVoiceBriefing();
      } else if (e.key === "m" || e.key === "M") {
        e.preventDefault();
        this.toggleMute();
      } else if (e.key === "c" || e.key === "C") {
        e.preventDefault();
        this.checkpointSession();
      } else if (e.key === "s" || e.key === "S") {
        e.preventDefault();
        if (this.labModal.classList.contains("active")) {
          this.closeModal(this.labModal);
        } else {
          this.openModal(this.labModal);
        }
      }
    });
  }

  setMode(mode) {
    this.appMode = mode;
    if (mode === "quant") {
      this.btnModeQuant.classList.add("active");
      this.btnModePlain.classList.remove("active");
      this.briefingBadge.textContent = "QUANTITATIVE BRIEFING";
    } else {
      this.btnModePlain.classList.add("active");
      this.btnModeQuant.classList.remove("active");
      this.briefingBadge.textContent = "PLAIN-ENGLISH DIGEST";
    }
    this.renderTableHead();
    this.fetchBriefing();
  }

  // --- Audio Sonification Engine (Web Audio API) ---
  getAudioContext() {
    if (!this.audioCtx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      this.audioCtx = new AudioCtx();
    }
    if (this.audioCtx.state === "suspended") {
      this.audioCtx.resume();
    }
    return this.audioCtx;
  }

  playAcousticSweep() {
    if (this.isMuted) {
      this.showToast("Audio is muted. Press M or click 🔊 to unmute.", "warning");
      return;
    }
    const ctx = this.getAudioContext();
    const sorted = [...this.tickers].sort((a, b) => b.delta_since_baseline_pct - a.delta_since_baseline_pct);
    if (sorted.length === 0) return;

    this.btnAudioSweep.classList.add("playing");
    this.showToast("🎵 Playing 4-second Acoustic Market Sweep...", "info");

    const duration = 0.35;
    const interval = 0.18;
    const now = ctx.currentTime;

    sorted.forEach((item, index) => {
      const startTime = now + index * interval;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      // Pitch calculation based on delta:
      // Bullish stocks: Pentatonic major scale frequencies (523Hz C5 up to 1046Hz C6)
      // Bearish stocks: Warm resonant lower frequencies (196Hz G3 down to 130Hz C3)
      const delta = item.delta_since_baseline_pct;
      let freq;
      if (item.is_halted) {
        freq = 300; // Flat buzzing tone
        osc.type = "sawtooth";
      } else if (delta >= 4.0) {
        freq = 880 + Math.min(250, delta * 20); // A5 high bell
        osc.type = "sine";
      } else if (delta >= 0) {
        freq = 523 + (delta * 60); // C5 upwards
        osc.type = "sine";
      } else if (delta <= -4.0) {
        freq = Math.max(110, 220 + (delta * 12)); // Low bass
        osc.type = "triangle";
      } else {
        freq = 330 + (delta * 30); // E4 downwards
        osc.type = "sine";
      }

      osc.frequency.setValueAtTime(freq, startTime);

      // Envelope
      gain.gain.setValueAtTime(0, startTime);
      gain.gain.linearRampToValueAtTime(0.2, startTime + 0.04);
      gain.gain.exponentialRampToValueAtTime(0.0001, startTime + duration);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(startTime);
      osc.stop(startTime + duration);
    });

    setTimeout(() => {
      this.btnAudioSweep.classList.remove("playing");
    }, (sorted.length * interval + duration) * 1000);
  }

  toggleVoiceBriefing() {
    if (!("speechSynthesis" in window)) {
      this.showToast("Speech synthesis not supported in this browser.", "warning");
      return;
    }

    if (this.isSpeaking) {
      window.speechSynthesis.cancel();
      this.isSpeaking = false;
      this.btnAudioBriefing.classList.remove("playing");
      this.btnAudioBriefing.innerHTML = '🎙️ Briefing <span style="font-size: 0.65rem; opacity: 0.7;">[B]</span>';
      this.showToast("Voice briefing stopped.", "info");
      return;
    }

    if (this.isMuted) {
      this.showToast("Audio is muted. Press M to unmute.", "warning");
      return;
    }

    // Build speech text
    const headline = this.appMode === "plain" 
      ? document.getElementById("briefingHeadline").textContent 
      : document.getElementById("briefingHeadline").textContent;
    
    const takeaways = Array.from(document.querySelectorAll("#briefingTakeaways li"))
      .map((li) => li.textContent.replace(/[▪*]/g, ""))
      .join(". ");

    const speechText = `Market delta summary. ${headline}. Key highlights: ${takeaways}.`;

    const utterance = new SpeechSynthesisUtterance(speechText);
    utterance.rate = 1.05;
    utterance.pitch = 1.0;

    utterance.onstart = () => {
      this.isSpeaking = true;
      this.btnAudioBriefing.classList.add("playing");
      this.btnAudioBriefing.innerHTML = '⏹️ Stop <span style="font-size: 0.65rem; opacity: 0.7;">[B]</span>';
      this.showToast("🎙️ Reading market briefing aloud...", "info");
    };

    utterance.onend = utterance.onerror = () => {
      this.isSpeaking = false;
      this.btnAudioBriefing.classList.remove("playing");
      this.btnAudioBriefing.innerHTML = '🎙️ Briefing <span style="font-size: 0.65rem; opacity: 0.7;">[B]</span>';
    };

    window.speechSynthesis.speak(utterance);
  }

  toggleMute() {
    this.isMuted = !this.isMuted;
    if (this.isMuted) {
      if (this.isSpeaking) {
        window.speechSynthesis.cancel();
        this.isSpeaking = false;
        this.btnAudioBriefing.classList.remove("playing");
      }
      this.btnAudioMute.textContent = "🔇";
      this.btnAudioMute.style.color = "var(--loss-red)";
      this.showToast("Audio muted.", "info");
    } else {
      this.btnAudioMute.textContent = "🔊";
      this.btnAudioMute.style.color = "var(--text-muted)";
      this.showToast("Audio unmuted.", "success");
    }
  }

  // --- Session & Data Loading ---
  async initSession() {
    try {
      this.renderTableHead();
      const res = await fetch(`/api/session?session_id=${this.sessionId}&user_name=Quant+Trader`);
      const sessionData = await res.json();
      this.sessionId = sessionData.session_id;

      await this.loadWatchlists();
      await this.fetchBriefing();
      this.initWebSocket();
    } catch (err) {
      console.error("Session init failed:", err);
      this.showToast("Connecting to real-time stream...", "warning");
    }
  }

  async loadWatchlists() {
    try {
      const res = await fetch(`/api/watchlists?session_id=${this.sessionId}`);
      this.watchlists = await res.json();
      if (this.watchlists.length > 0 && !this.activeWatchlistId) {
        this.activeWatchlistId = this.watchlists[0].id;
      }
      this.renderWatchlistTabs();
    } catch (err) {
      console.error("Failed to load watchlists:", err);
    }
  }

  renderWatchlistTabs() {
    this.watchlistTabs.innerHTML = "";
    this.watchlists.forEach((wl) => {
      const btn = document.createElement("button");
      btn.className = `tab-btn ${wl.id === this.activeWatchlistId ? "active" : ""}`;
      btn.innerHTML = `
        <span>${this.escapeHtml(wl.name)}</span>
        <span class="tab-count">${wl.items ? wl.items.length : 0}</span>
      `;
      btn.addEventListener("click", () => {
        this.activeWatchlistId = wl.id;
        this.renderWatchlistTabs();
        this.fetchBriefing();
        this.sendWsWatchlistSubscription();
      });
      this.watchlistTabs.appendChild(btn);
    });
  }

  async createWatchlist() {
    const input = document.getElementById("newWlNameInput");
    const name = input.value.trim();
    if (!name) return;

    try {
      const res = await fetch(`/api/watchlists?session_id=${this.sessionId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name, symbols: [] }),
      });
      const created = await res.json();
      input.value = "";
      this.closeModal(this.createWlModal);
      await this.loadWatchlists();
      this.activeWatchlistId = created.id;
      this.renderWatchlistTabs();
      this.fetchBriefing();
      this.showToast(`Watchlist "${name}" created.`, "success");
    } catch (err) {
      console.error("Create watchlist failed:", err);
      this.showToast("Error creating watchlist.", "warning");
    }
  }

  async checkpointSession() {
    try {
      const res = await fetch(`/api/session/checkpoint?session_id=${this.sessionId}`, { method: "POST" });
      const data = await res.json();
      this.showToast("📸 Baseline checkpoint anchored to this moment!", "success");
      await this.fetchBriefing();
    } catch (err) {
      this.showToast("Failed to record checkpoint.", "warning");
    }
  }

  async fetchBriefing() {
    try {
      let url = `/api/market/since-last-seen?session_id=${this.sessionId}&baseline_type=${this.baselineType}`;
      if (this.activeWatchlistId) {
        url += `&watchlist_id=${this.activeWatchlistId}`;
      }
      const res = await fetch(url);
      const briefing = await res.json();

      this.tickers = briefing.tickers || [];
      this.updateBriefingUI(briefing);
      this.updateBreadthBar();
      this.updateTickerTape();
      this.renderTable();
    } catch (err) {
      console.error("Error fetching briefing:", err);
    }
  }

  updateBriefingUI(briefing) {
    const elapsed = briefing.elapsed_minutes;
    let timeText = "just now";
    if (elapsed >= 1 && elapsed < 60) timeText = `${Math.round(elapsed)}m ago`;
    else if (elapsed >= 60) timeText = `${(elapsed / 60).toFixed(1)}h ago`;

    const labelMap = {
      last_visit: `Last Visit (${timeText})`,
      open: "Market Open (9:30 AM)",
      "15m": "Past 15 Minutes",
      "1h": "Past 1 Hour",
      prev_close: "Previous Close (24h)",
    };

    this.briefingTime.textContent = `Baseline: ${labelMap[this.baselineType] || timeText}`;
    this.briefingStats.textContent = `Tracking: ${briefing.total_tracked} assets | Anomalies: ${briefing.anomalies_detected}`;

    // Mood Badge
    this.briefingMood.textContent = briefing.market_mood || "Neutral";
    if ((briefing.market_mood || "").includes("Bullish")) {
      this.briefingMood.style.color = "var(--profit-green)";
      this.briefingMood.style.background = "rgba(16, 185, 129, 0.15)";
    } else if ((briefing.market_mood || "").includes("Bearish") || (briefing.market_mood || "").includes("Alert")) {
      this.briefingMood.style.color = "var(--loss-red)";
      this.briefingMood.style.background = "rgba(244, 63, 94, 0.15)";
    } else {
      this.briefingMood.style.color = "var(--text-secondary)";
      this.briefingMood.style.background = "rgba(255, 255, 255, 0.08)";
    }

    // Headline and Takeaways based on Perspective Mode
    if (this.appMode === "plain") {
      this.briefingHeadline.textContent = briefing.plain_headline || briefing.summary_headline;
      this.briefingTakeaways.innerHTML = "";
      const items = briefing.plain_takeaways && briefing.plain_takeaways.length > 0 
        ? briefing.plain_takeaways 
        : briefing.key_takeaways;
      (items || []).forEach((t) => {
        const li = document.createElement("li");
        li.innerHTML = t.replace(/\*\*(.*?)\*\*/g, '<strong style="color: var(--text-primary); font-weight: 700;">$1</strong>');
        this.briefingTakeaways.appendChild(li);
      });
    } else {
      this.briefingHeadline.textContent = briefing.summary_headline;
      this.briefingTakeaways.innerHTML = "";
      (briefing.key_takeaways || []).forEach((t) => {
        const li = document.createElement("li");
        li.innerHTML = t.replace(/\*\*(.*?)\*\*/g, '<strong style="color: var(--text-primary); font-weight: 700;">$1</strong>');
        this.briefingTakeaways.appendChild(li);
      });
    }

    // Update filter counts
    document.getElementById("countAll").textContent = this.tickers.length;
    document.getElementById("countUrgent").textContent = this.tickers.filter((t) => t.attention_score >= 45).length;
    document.getElementById("countAnomalies").textContent = this.tickers.filter((t) =>
      t.flags.some((f) => f.severity === "critical" || f.type.includes("ANOMALY") || t.is_halted)
    ).length;
  }

  updateBreadthBar() {
    const upCount = this.tickers.filter((t) => t.delta_since_baseline_pct > 0).length;
    const downCount = this.tickers.filter((t) => t.delta_since_baseline_pct < 0).length;
    const ratio = downCount > 0 ? (upCount / downCount).toFixed(2) : upCount.toString();

    this.breadthUp.textContent = `🟢 Advancing: ${upCount}`;
    this.breadthDown.textContent = `🔴 Declining: ${downCount}`;
    this.breadthRatio.textContent = `A/D Ratio: ${ratio}`;

    // Compute sector momentum
    const sectorMap = {};
    this.tickers.forEach((t) => {
      const sec = t.sector.split(" ")[0]; // e.g. "Semiconductors", "Enterprise"
      if (!sectorMap[sec]) sectorMap[sec] = [];
      sectorMap[sec].push(t.delta_since_baseline_pct);
    });

    this.sectorChips.innerHTML = "";
    Object.entries(sectorMap).slice(0, 5).forEach(([sec, deltas]) => {
      const avg = deltas.reduce((a, b) => a + b, 0) / deltas.length;
      const chip = document.createElement("div");
      chip.className = "sector-chip";
      const color = avg >= 0 ? "var(--profit-green)" : "var(--loss-red)";
      chip.innerHTML = `${sec}: <span style="color: ${color};">${avg >= 0 ? "+" : ""}${avg.toFixed(1)}%</span>`;
      this.sectorChips.appendChild(chip);
    });
  }

  updateTickerTape() {
    if (!this.tickers || this.tickers.length === 0) return;
    const items = [...this.tickers, ...this.tickers]; // Duplicate for seamless infinite loop
    this.tickerTapeContent.innerHTML = items
      .slice(0, 18)
      .map((t) => {
        const deltaSign = t.day_change_pct >= 0 ? "+" : "";
        const deltaClass = t.day_change_pct >= 0 ? "tape-delta-pos" : "tape-delta-neg";
        return `
          <span class="tape-item">
            <span class="tape-sym">${this.escapeHtml(t.symbol)}</span>
            $${t.current_price.toFixed(2)}
            <span class="${deltaClass}">${deltaSign}${t.day_change_pct.toFixed(2)}%</span>
          </span>
        `;
      })
      .join("");
  }

  renderTableHead() {
    if (this.appMode === "plain") {
      this.tableHead.innerHTML = `
        <tr>
          <th style="width: 170px;">Asset / Company</th>
          <th style="width: 120px;">Market Mood</th>
          <th style="width: 120px;">Current Price</th>
          <th style="width: 150px;">Change Since You Checked</th>
          <th style="width: 110px;">Activity Level</th>
          <th>What Is Happening (Plain Explanation)</th>
          <th style="width: 100px;">Trend</th>
          <th style="width: 70px; text-align: right;">Actions</th>
        </tr>
      `;
    } else {
      this.tableHead.innerHTML = `
        <tr>
          <th style="width: 170px;">Asset / Sector</th>
          <th style="width: 110px;">Attention Index</th>
          <th style="width: 120px;">Live Price</th>
          <th style="width: 160px;">⚡ Since Baseline</th>
          <th style="width: 110px;">RVOL (Surge)</th>
          <th>Significant Signals / Anomalies</th>
          <th style="width: 100px;">Trend</th>
          <th style="width: 70px; text-align: right;">Actions</th>
        </tr>
      `;
    }
  }

  // --- Real-time WebSocket connection ---
  initWebSocket() {
    if (this.ws) {
      this.ws.close();
    }

    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${proto}//${window.location.host}/ws?session_id=${this.sessionId}&watchlist_id=${this.activeWatchlistId || ""}`;
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      this.updateFeedStatus(false, 14);
      this.sendWsWatchlistSubscription();
    };

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "market_tick") {
          this.handleTickUpdate(msg);
        }
      } catch (e) {
        console.error("WS Parse error:", e);
      }
    };

    this.ws.onclose = () => {
      this.updateFeedStatus(true, 9999);
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = setTimeout(() => this.initWebSocket(), 3000);
    };

    this.ws.onerror = () => {
      this.updateFeedStatus(true, 9999);
    };
  }

  sendWsWatchlistSubscription() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const activeWl = this.watchlists.find((w) => w.id === this.activeWatchlistId);
      const symbols = activeWl && activeWl.items ? activeWl.items.map((i) => i.symbol) : [];
      this.ws.send(
        JSON.stringify({
          action: "subscribe_watchlist",
          watchlist_id: this.activeWatchlistId,
          symbols: symbols,
        })
      );
    }
  }

  sendWsBaseline() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(
        JSON.stringify({
          action: "change_baseline",
          baseline_type: this.baselineType,
        })
      );
    }
  }

  handleTickUpdate(msg) {
    if (msg.health) {
      this.updateFeedStatus(msg.health.is_stale, msg.health.latency_ms);
    }

    if (msg.tickers && msg.tickers.length > 0) {
      const newMap = new Map(this.tickers.map((t) => [t.symbol, t]));
      msg.tickers.forEach((t) => {
        newMap.set(t.symbol, t);
      });
      this.tickers = Array.from(newMap.values());
      this.renderTable(true);
      this.updateBreadthBar();
    }
  }

  updateFeedStatus(isStale, latencyMs) {
    if (isStale) {
      this.statusDot.className = "status-dot stale";
      this.feedStatusText.textContent = `STALE FEED (${latencyMs}ms delay)`;
      this.feedStatusText.style.color = "var(--warning-amber)";
    } else {
      this.statusDot.className = "status-dot";
      this.feedStatusText.textContent = `Real-Time (${latencyMs}ms)`;
      this.feedStatusText.style.color = "var(--text-secondary)";
    }
  }

  getFilteredAndSortedTickers() {
    let list = [...this.tickers];

    // 1. Filtering
    if (this.currentFilter === "urgent") {
      list = list.filter((t) => t.attention_score >= 45 || t.is_halted);
    } else if (this.currentFilter === "anomalies") {
      list = list.filter((t) => t.flags.some((f) => f.severity === "critical" || f.type.includes("ANOMALY")) || t.is_halted);
    } else if (this.currentFilter === "gainers") {
      list = list.filter((t) => t.delta_since_baseline_pct > 0);
    } else if (this.currentFilter === "losers") {
      list = list.filter((t) => t.delta_since_baseline_pct < 0);
    }

    // 2. Sorting
    list.sort((a, b) => {
      if (a.is_halted && !b.is_halted) return -1;
      if (!a.is_halted && b.is_halted) return 1;
      if (this.currentSort === "attention") return b.attention_score - a.attention_score;
      if (this.currentSort === "delta_since") return Math.abs(b.delta_since_baseline_pct) - Math.abs(a.delta_since_baseline_pct);
      if (this.currentSort === "day_change") return b.day_change_pct - a.day_change_pct;
      if (this.currentSort === "rvol") return b.relative_volume - a.relative_volume;
      if (this.currentSort === "z_score") return Math.abs(b.volatility_z_score) - Math.abs(a.volatility_z_score);
      if (this.currentSort === "symbol") return a.symbol.localeCompare(b.symbol);
      return 0;
    });

    return list;
  }

  renderTable(isTickUpdate = false) {
    const list = this.getFilteredAndSortedTickers();
    if (list.length === 0) {
      this.tableBody.innerHTML = `
        <tr>
          <td colspan="8" style="text-align: center; color: var(--text-muted); padding: 3rem;">
            No instruments match the current filter.
          </td>
        </tr>
      `;
      return;
    }

    this.tableBody.innerHTML = "";
    list.forEach((t) => {
      const prevPrice = this.lastPrices.get(t.symbol) || t.current_price;
      const flashClass = t.current_price > prevPrice ? "flash-green" : t.current_price < prevPrice ? "flash-red" : "";
      this.lastPrices.set(t.symbol, t.current_price);

      const tr = document.createElement("tr");
      tr.className = `table-row ${flashClass}`;

      // Score color
      let scoreColor = "var(--profit-green)";
      if (t.is_halted) scoreColor = "#c084fc";
      else if (t.attention_score >= 70) scoreColor = "var(--loss-red)";
      else if (t.attention_score >= 40) scoreColor = "var(--warning-amber)";

      // Delta color
      const deltaClass = t.delta_since_baseline_pct > 0 ? "delta-up" : t.delta_since_baseline_pct < 0 ? "delta-down" : "delta-neutral";
      const deltaSign = t.delta_since_baseline_pct > 0 ? "+" : "";

      // Stale badge
      const staleBadge = t.is_stale ? '<span class="badge-flag warning">STALE</span>' : "";
      const haltBadge = t.is_halted ? '<span class="badge-flag halt">HALTED</span>' : "";

      if (this.appMode === "plain") {
        // Plain English Mode rendering
        let moodClass = "plain-mood-neutral";
        if (t.is_halted) moodClass = "plain-mood-bear";
        else if (t.delta_since_baseline_pct >= 2.0) moodClass = "plain-mood-bull";
        else if (t.delta_since_baseline_pct <= -2.0) moodClass = "plain-mood-bear";

        let activityText = "Normal";
        if (t.relative_volume >= 3.0) activityText = "🔥 Very Heavy";
        else if (t.relative_volume >= 2.0) activityText = "⚡ Elevated";

        tr.innerHTML = `
          <td>
            <div class="symbol-meta">
              <span class="sym-code">${this.escapeHtml(t.symbol)} ${staleBadge} ${haltBadge}</span>
              <span class="sym-name" title="${this.escapeHtml(t.name)}">${this.escapeHtml(t.name)}</span>
            </div>
          </td>
          <td>
            <span class="plain-mood-pill ${moodClass}">${this.escapeHtml(t.plain_mood || "Neutral")}</span>
          </td>
          <td>
            <div style="font-family: var(--font-mono); font-weight: 700; font-size: 0.95rem;">
              $${t.current_price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div style="font-size: 0.72rem; color: ${t.day_change_pct >= 0 ? "var(--profit-green)" : "var(--loss-red)"}; font-family: var(--font-mono);">
              ${t.day_change_pct >= 0 ? "+" : ""}${t.day_change_pct}% today
            </div>
          </td>
          <td>
            <div class="since-visit-box">
              <div class="since-visit-delta ${deltaClass}">
                ${deltaSign}${t.delta_since_baseline_pct.toFixed(2)}%
              </div>
              <div class="since-visit-sub">
                Was $${t.baseline_price.toFixed(2)}
              </div>
            </div>
          </td>
          <td>
            <div style="font-family: var(--font-mono); font-size: 0.85rem; font-weight: 700;">
              ${activityText}
            </div>
            <div style="font-size: 0.7rem; color: var(--text-muted);">${t.relative_volume.toFixed(1)}x normal</div>
          </td>
          <td>
            <div style="font-size: 0.82rem; color: #cbd5e1; line-height: 1.35;">
              ${this.escapeHtml(t.plain_explanation || "Price is moving within expected bounds.")}
            </div>
          </td>
          <td>
            <canvas class="sparkline-canvas" id="spark-${t.symbol}"></canvas>
          </td>
          <td style="text-align: right;">
            <div class="row-actions" style="justify-content: flex-end;">
              <button class="action-icon-btn delete" title="Remove from watchlist" data-symbol="${t.symbol}">🗑️</button>
            </div>
          </td>
        `;
      } else {
        // Quant Mode rendering
        const flagsHtml = t.flags
          .map((f) => `<span class="badge-flag ${f.severity}" title="${this.escapeHtml(f.description)}">${this.escapeHtml(f.label)}</span>`)
          .join(" ");

        tr.innerHTML = `
          <td>
            <div class="symbol-meta">
              <span class="sym-code">${this.escapeHtml(t.symbol)} ${staleBadge} ${haltBadge}</span>
              <span class="sym-name" title="${this.escapeHtml(t.name)}">${this.escapeHtml(t.name)}</span>
            </div>
          </td>
          <td>
            <div class="attention-gauge-wrap">
              <span class="attention-score-val" style="color: ${scoreColor};">${Math.round(t.attention_score)}</span>
              <div class="attention-bar-outer">
                <div class="attention-bar-inner" style="width: ${t.attention_score}%; background-color: ${scoreColor};"></div>
              </div>
            </div>
          </td>
          <td>
            <div style="font-family: var(--font-mono); font-weight: 700; font-size: 0.95rem;">
              $${t.current_price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div style="font-size: 0.72rem; color: ${t.day_change_pct >= 0 ? "var(--profit-green)" : "var(--loss-red)"}; font-family: var(--font-mono);">
              ${t.day_change_pct >= 0 ? "+" : ""}${t.day_change_pct}% today
            </div>
          </td>
          <td>
            <div class="since-visit-box">
              <div class="since-visit-delta ${deltaClass}">
                ${deltaSign}${t.delta_since_baseline_pct.toFixed(2)}%
                <span style="font-size: 0.72rem; opacity: 0.85;">(${deltaSign}$${Math.abs(t.delta_since_baseline_abs).toFixed(2)})</span>
              </div>
              <div class="since-visit-sub">
                Was $${t.baseline_price.toFixed(2)} | Z: ${t.volatility_z_score > 0 ? "+" : ""}${t.volatility_z_score}σ
              </div>
            </div>
          </td>
          <td>
            <div style="font-family: var(--font-mono); font-size: 0.88rem; font-weight: 700; color: ${t.relative_volume >= 2.5 ? "var(--warning-amber)" : "var(--text-primary)"};">
              ${t.relative_volume.toFixed(1)}x
            </div>
            <div style="font-size: 0.7rem; color: var(--text-muted);">vs 30D ADV</div>
          </td>
          <td>
            <div class="tags-list">
              ${flagsHtml || '<span style="font-size: 0.75rem; color: var(--text-muted);">Normal bounds</span>'}
            </div>
          </td>
          <td>
            <canvas class="sparkline-canvas" id="spark-${t.symbol}"></canvas>
          </td>
          <td style="text-align: right;">
            <div class="row-actions" style="justify-content: flex-end;">
              <button class="action-icon-btn delete" title="Remove from watchlist" data-symbol="${t.symbol}">🗑️</button>
            </div>
          </td>
        `;
      }

      // Row click opens deep-dive drawer
      tr.addEventListener("click", (e) => {
        if (e.target.closest(".delete")) {
          e.stopPropagation();
          this.removeTicker(t.symbol);
          return;
        }
        this.openDrawer(t);
      });

      this.tableBody.appendChild(tr);

      // Render sparkline
      this.drawSparkline(`spark-${t.symbol}`, t.sparkline, t.delta_since_baseline_pct >= 0);
    });
  }

  drawSparkline(canvasId, points, isPositive) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !points || points.length < 2) return;

    const ctx = canvas.getContext("2d");
    const width = canvas.width = 180;
    const height = canvas.height = 56;

    ctx.clearRect(0, 0, width, height);

    const min = Math.min(...points);
    const max = Math.max(...points);
    const range = max - min === 0 ? 1 : max - min;

    const strokeColor = isPositive ? "#10b981" : "#f43f5e";
    const fillColor = isPositive ? "rgba(16, 185, 129, 0.15)" : "rgba(244, 63, 94, 0.15)";

    ctx.beginPath();
    points.forEach((p, i) => {
      const x = (i / (points.length - 1)) * (width - 8) + 4;
      const y = height - ((p - min) / range) * (height - 12) - 6;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });

    ctx.strokeStyle = strokeColor;
    ctx.lineWidth = 2.5;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.stroke();

    ctx.lineTo(width - 4, height);
    ctx.lineTo(4, height);
    ctx.closePath();
    ctx.fillStyle = fillColor;
    ctx.fill();
  }

  // Deep-dive Side Drawer
  openDrawer(ticker) {
    document.getElementById("drawerTitle").textContent = `${ticker.symbol} - ${ticker.name}`;
    document.getElementById("drawerSubtitle").textContent = `${ticker.sector} | Real-Time Factor Decomposition`;

    const body = document.getElementById("drawerBody");
    const deltaSign = ticker.delta_since_baseline_pct >= 0 ? "+" : "";

    body.innerHTML = `
      <div class="factor-card" style="border-left: 4px solid ${ticker.delta_since_baseline_pct >= 0 ? "var(--profit-green)" : "var(--loss-red)"};">
        <div class="factor-header">
          <span class="factor-title">Delta Since Baseline (${this.baselineType})</span>
          <span class="factor-value" style="color: ${ticker.delta_since_baseline_pct >= 0 ? "var(--profit-green)" : "var(--loss-red)"};">
            ${deltaSign}${ticker.delta_since_baseline_pct.toFixed(2)}%
          </span>
        </div>
        <div class="factor-expl">
          Moved from baseline anchor of <strong>$${ticker.baseline_price.toFixed(2)}</strong> to current price of <strong>$${ticker.current_price.toFixed(2)}</strong>.
        </div>
      </div>

      <div class="factor-card">
        <div class="factor-header">
          <span class="factor-title">Statistical Volatility Anomaly (Z-Score)</span>
          <span class="factor-value">${ticker.volatility_z_score > 0 ? "+" : ""}${ticker.volatility_z_score}σ</span>
        </div>
        <div class="factor-expl">
          Normalized price move relative to historical daily volatility. Values above <strong>|2.0σ|</strong> represent statistically rare tail events warranting immediate review.
        </div>
      </div>

      <div class="factor-card">
        <div class="factor-header">
          <span class="factor-title">Relative Volume (RVOL)</span>
          <span class="factor-value" style="color: ${ticker.relative_volume >= 2.5 ? "var(--warning-amber)" : "var(--text-primary)"};">
            ${ticker.relative_volume.toFixed(2)}x
          </span>
        </div>
        <div class="factor-expl">
          Current volume relative to 30-day baseline average daily volume. RVOL > 2.0x signifies heavy institutional buying or distribution pressure.
        </div>
      </div>

      <div class="factor-card">
        <div class="factor-header">
          <span class="factor-title">Benchmark Divergence vs S&P 500 (SPY)</span>
          <span class="factor-value">${ticker.benchmark_divergence_pct > 0 ? "+" : ""}${ticker.benchmark_divergence_pct.toFixed(2)}%</span>
        </div>
        <div class="factor-expl">
          Alpha outperformance or underperformance relative to broad market beta. High divergence isolates idiosyncratic catalysts from macro drift.
        </div>
      </div>

      <div class="factor-card">
        <div class="factor-header">
          <span class="factor-title">Plain English Context</span>
          <span class="factor-value" style="color: var(--accent-cyan); font-size: 0.9rem;">${this.escapeHtml(ticker.plain_mood || "Neutral")}</span>
        </div>
        <div class="factor-expl">
          ${this.escapeHtml(ticker.plain_explanation || "Price is fluctuating within standard statistical boundaries.")}
        </div>
      </div>

      <div style="margin-top: 1.25rem;">
        <button class="btn btn-secondary" style="width: 100%; justify-content: center;" id="btnDrawerCheckpoint">
          📸 Re-Anchor Baseline for ${ticker.symbol}
        </button>
      </div>
    `;

    document.getElementById("btnDrawerCheckpoint").addEventListener("click", () => {
      this.checkpointSession();
      this.closeDrawer();
    });

    this.drawerOverlay.classList.add("active");
  }

  closeDrawer() {
    this.drawerOverlay.classList.remove("active");
  }

  // Autocomplete Universe Search
  async searchUniverse(query) {
    const q = query.trim();
    if (!q) {
      this.autocompleteDropdown.style.display = "none";
      return;
    }

    try {
      const res = await fetch(`/api/universe?q=${encodeURIComponent(q)}`);
      const results = await res.json();

      if (results.length === 0) {
        this.autocompleteDropdown.innerHTML = `<div style="padding: 0.75rem; font-size: 0.8rem; color: var(--text-muted); text-align: center;">No instruments found</div>`;
        this.autocompleteDropdown.style.display = "block";
        return;
      }

      this.autocompleteDropdown.innerHTML = "";
      results.slice(0, 6).forEach((item) => {
        const div = document.createElement("div");
        div.className = "autocomplete-item";
        div.innerHTML = `
          <div>
            <span style="font-family: var(--font-mono); font-weight: 700; color: var(--text-primary);">${this.escapeHtml(item.symbol)}</span>
            <span style="font-size: 0.74rem; color: var(--text-muted); margin-left: 0.5rem;">${this.escapeHtml(item.name)}</span>
          </div>
          <span style="font-family: var(--font-mono); font-size: 0.85rem; color: var(--accent-cyan);">$${item.price.toFixed(2)}</span>
        `;
        div.addEventListener("click", () => {
          this.addTicker(item.symbol);
          this.searchUniverseInput.value = "";
          this.autocompleteDropdown.style.display = "none";
        });
        this.autocompleteDropdown.appendChild(div);
      });
      this.autocompleteDropdown.style.display = "block";
    } catch (e) {
      console.error("Search error:", e);
    }
  }

  async addTicker(symbol) {
    if (!this.activeWatchlistId) {
      this.showToast("Please select or create a watchlist first.", "warning");
      return;
    }
    try {
      const res = await fetch(`/api/watchlists/${this.activeWatchlistId}/items`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: symbol }),
      });
      if (res.ok) {
        this.showToast(`Added ${symbol} to watchlist.`, "success");
        await this.loadWatchlists();
        await this.fetchBriefing();
        this.sendWsWatchlistSubscription();
      } else {
        const err = await res.json();
        this.showToast(err.detail || "Could not add symbol.", "warning");
      }
    } catch (e) {
      this.showToast("Failed to add symbol.", "warning");
    }
  }

  async removeTicker(symbol) {
    if (!this.activeWatchlistId) return;
    try {
      const res = await fetch(`/api/watchlists/${this.activeWatchlistId}/items/${symbol}`, {
        method: "DELETE",
      });
      if (res.ok) {
        this.showToast(`Removed ${symbol}.`, "success");
        await this.loadWatchlists();
        await this.fetchBriefing();
        this.sendWsWatchlistSubscription();
      }
    } catch (e) {
      this.showToast("Failed to remove symbol.", "warning");
    }
  }

  // Market Scenario Simulator Shocks
  async triggerShock(shockType, magnitude = 5.0, symbol = "NVDA") {
    try {
      const payload = {
        symbol: symbol,
        shock_type: shockType,
        magnitude_pct: magnitude,
        time_jump_minutes: magnitude,
      };
      const res = await fetch(`/api/simulate/shock?session_id=${this.sessionId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      this.showToast(data.message, "success");
      await this.fetchBriefing();
      this.closeModal(this.labModal);
    } catch (e) {
      this.showToast("Failed to trigger simulation scenario.", "warning");
    }
  }

  openModal(modal) {
    modal.classList.add("active");
  }

  closeModal(modal) {
    modal.classList.remove("active");
  }

  showToast(msg, type = "info") {
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.innerHTML = `<span>${type === "warning" ? "⚠️" : type === "success" ? "✅" : "ℹ️"}</span> <span>${this.escapeHtml(msg)}</span>`;
    this.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(10px)";
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
}

// Initialize on DOM load
document.addEventListener("DOMContentLoaded", () => {
  window.app = new NexusTerminalApp();
});
