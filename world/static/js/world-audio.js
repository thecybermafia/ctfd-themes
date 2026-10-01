/**
 * Tactical Cyber Audio Engine (World Theme)
 * Web Audio API synthesizer for zero-latency, realistic cyber terminal sound effects.
 * Fallback to HTML5 audio when needed.
 */
(function() {
  const AudioEngine = {
    ctx: null,
    muted: false,
    volume: 0.6,
    enabled: true,

    init() {
      try {
        const savedMute = localStorage.getItem("world_audio_muted");
        if (savedMute !== null) {
          this.muted = (savedMute === "true");
        }
      } catch(e) {}

      // Check global setting from api (deduped via window.getWorldSettings)
      const getSettings = window.getWorldSettings || function() {
        return fetch("/api/v1/world/settings").then(r => r.json()).then(res => res.data || {}).catch(() => ({}));
      };

      getSettings()
        .then(settings => {
          if (settings && settings.sound_effects_enabled !== undefined) {
            this.enabled = (settings.sound_effects_enabled !== false);
          }
          this.updateNavbarToggle();
        })
        .catch(() => {
          this.updateNavbarToggle();
        });

      // Unlock AudioContext on first operative gesture
      const unlockAudio = () => {
        if (!this.ctx) {
          const AudioCtx = window.AudioContext || window.webkitAudioContext;
          if (AudioCtx) this.ctx = new AudioCtx();
        }
        if (this.ctx && this.ctx.state === "suspended") {
          this.ctx.resume().catch(() => {});
        }
        document.removeEventListener("click", unlockAudio);
        document.removeEventListener("keydown", unlockAudio);
      };
      document.addEventListener("click", unlockAudio, { once: true });
      document.addEventListener("keydown", unlockAudio, { once: true });
    },

    getContext() {
      if (!this.ctx && typeof window !== "undefined") {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (AudioCtx) {
          this.ctx = new AudioCtx();
        }
      }
      if (this.ctx && this.ctx.state === "suspended") {
        this.ctx.resume().catch(() => {});
      }
      return this.ctx;
    },

    toggleMute() {
      this.muted = !this.muted;
      try {
        localStorage.setItem("world_audio_muted", this.muted ? "true" : "false");
      } catch(e) {}
      this.updateNavbarToggle();
      if (!this.muted) {
        this.playBlip();
      }
      return this.muted;
    },

    updateNavbarToggle() {
      const btn = document.getElementById("audio-toggle-btn");
      if (!btn) return;
      const icon = btn.querySelector("i");
      const label = btn.querySelector(".audio-toggle-text");
      if (this.muted || !this.enabled) {
        btn.classList.add("audio-muted");
        if (icon) {
          icon.className = icon.className.replace("fa-volume-up", "fa-volume-mute");
        }
        if (label) label.textContent = "SFX: OFF";
      } else {
        btn.classList.remove("audio-muted");
        if (icon) {
          icon.className = icon.className.replace("fa-volume-mute", "fa-volume-up");
        }
        if (label) label.textContent = "SFX: ON";
      }
    },

    // 1. Radar Blip / Target Lock (Triggered on territory click, reticle lock, camera recenter)
    playBlip() {
      if (!this.enabled || this.muted) return;
      const ctx = this.getContext();
      if (!ctx) return;
      try {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "sine";
        osc.frequency.setValueAtTime(880, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(1760, ctx.currentTime + 0.08);
        gain.gain.setValueAtTime(0.12 * this.volume, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.08);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.08);
      } catch(e) {}
    },

    // 2. Solve Fanfare / Mission Accomplished Chime (Triggered on flag breach)
    playSolve() {
      if (!this.enabled || this.muted) return;
      const ctx = this.getContext();
      if (!ctx) return;
      try {
        const notes = [523.25, 659.25, 783.99, 1046.50]; // C5, E5, G5, C6
        notes.forEach((freq, idx) => {
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          const startTime = ctx.currentTime + (idx * 0.08);
          osc.type = "triangle";
          osc.frequency.setValueAtTime(freq, startTime);
          gain.gain.setValueAtTime(0.16 * this.volume, startTime);
          gain.gain.exponentialRampToValueAtTime(0.001, startTime + 0.38);
          osc.connect(gain);
          gain.connect(ctx.destination);
          osc.start(startTime);
          osc.stop(startTime + 0.38);
        });
      } catch(e) {}
    },

    // 3. Access Denied / Error Buzzer (Triggered on incorrect flag)
    playError() {
      if (!this.enabled || this.muted) return;
      const ctx = this.getContext();
      if (!ctx) return;
      try {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "sawtooth";
        osc.frequency.setValueAtTime(140, ctx.currentTime);
        osc.frequency.setValueAtTime(110, ctx.currentTime + 0.12);
        gain.gain.setValueAtTime(0.18 * this.volume, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.3);
      } catch(e) {}
    }
  };

  window.WorldAudio = AudioEngine;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => AudioEngine.init());
  } else {
    AudioEngine.init();
  }
})();
