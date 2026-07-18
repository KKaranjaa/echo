window.echoMediaPlayer = function (audioUrl, transcriptWords = []) {
  return {
    audioUrl: audioUrl,
    playing: false,
    currentTime: 0,
    duration: 0,
    speed: 1.0,
    speeds: [0.5, 0.75, 1.0, 1.25, 1.5, 2.0],
    mediaMode: 'audio',
    volume: 1.0,
    progressPct: 0,
    
    // Subtitles
    showSubtitles: true,
    subtitles: [],
    currentSubtitle: '',

    // PiP
    isPip: false,
    pipMinimized: false,
    forceHidePip: false,
    forceMobileMinimize: false, // New manual toggle for mobile
    // Drag state for full PiP card
    pipDragX: null,
    pipDragY: null,
    _isDragging: false,
    _dragOffsetX: 0,
    _dragOffsetY: 0,
    _observer: null,

    // Store bound handlers so we can remove them on mode switch
    _handlers: null,
    _boundEl: null,

    init() {
      this._attachMedia();
      this._buildSubtitles(transcriptWords);

      // Setup PiP observer to trigger when the placeholder scrolls out of view
      this.$nextTick(() => {
        const container = this.$refs.playerContainer;
        if (container && 'IntersectionObserver' in window) {
          this._observer = new IntersectionObserver((entries) => {
            const wasPip = this.isPip;
            this.isPip = !entries[0].isIntersecting;
            if (!this.isPip) {
               this.pipMinimized = false;
               this.forceHidePip = false;
               this.pipDragX = null;
               this.pipDragY = null;
            } else if (!wasPip) {
               // Just scrolled down to enter PiP
               // Only show the full floating player if video is currently playing
               if (!this.playing) {
                 this.forceHidePip = true;
                 this.pipMinimized = true;
               }
            }
          }, { threshold: 0 });
          this._observer.observe(container);
        }
      });

      // Listen for external seek requests (from transcript word clicks etc.)
      window.addEventListener('seekaudio', (e) => {
        this.seekTo(e.detail.time);
      });
    },

    _buildSubtitles(words) {
      if (!words || !words.length) return;
      const chunkSize = 7;
      let chunks = [];
      for (let i = 0; i < words.length; i += chunkSize) {
        const chunkWords = words.slice(i, i + chunkSize);
        if (!chunkWords.length) continue;
        chunks.push({
          text: chunkWords.map(w => w.word).join(' '),
          start: chunkWords[0].start,
          end: chunkWords[chunkWords.length - 1].end
        });
      }
      this.subtitles = chunks;
      console.log('Subtitles generated:', this.subtitles.length, 'chunks from', words.length, 'words');
    },

    _attachMedia() {
      // Detach from previous element first
      this._detachMedia();

      // Retry until the ref is available (Alpine rendering may be async)
      const tryBind = () => {
        const el = this._el();
        if (!el) {
          requestAnimationFrame(tryBind);
          return;
        }

        const updateSubtitles = () => {
          if (!this.showSubtitles || !this.subtitles.length) {
            this.currentSubtitle = '';
            return;
          }
          const active = this.subtitles.find((s, i, arr) => {
            const nextStart = arr[i + 1] ? arr[i + 1].start : s.end + 2;
            return this.currentTime >= s.start && this.currentTime < nextStart;
          });
          
          // Clear if we are far past the end of the active subtitle
          if (active && this.currentTime > active.end + 2) {
             this.currentSubtitle = '';
          } else {
             this.currentSubtitle = active ? active.text : '';
          }
        };

        this._syncTime = () => {
          if (!this.playing) return;
          this.currentTime = el.currentTime;
          this.progressPct = this.duration > 0
            ? (this.currentTime / this.duration) * 100
            : 0;
          updateSubtitles();
          window.dispatchEvent(
            new CustomEvent('audiotimeupdate', { detail: { time: this.currentTime, speed: this.speed } })
          );
          this._rafId = requestAnimationFrame(this._syncTime);
        };

        const handlers = {
          loadedmetadata: () => {
            this.duration = el.duration || 0;
          },
          timeupdate: () => {
            // Keep timeupdate for when paused (e.g., seeking/scrubbing)
            if (this.playing) return;
            this.currentTime = el.currentTime;
            this.progressPct = this.duration > 0
              ? (this.currentTime / this.duration) * 100
              : 0;
            updateSubtitles();
            window.dispatchEvent(
              new CustomEvent('audiotimeupdate', { detail: { time: this.currentTime, speed: this.speed } })
            );
          },
          play:  () => { 
            this.playing = true; 
            this._rafId = requestAnimationFrame(this._syncTime);
          },
          pause: () => { 
            this.playing = false; 
            cancelAnimationFrame(this._rafId);
          },
          ended: () => { 
            this.playing = false; 
            this.currentTime = 0; 
            this.progressPct = 0; 
            cancelAnimationFrame(this._rafId);
          },
        };

        for (const [evt, fn] of Object.entries(handlers)) {
          el.addEventListener(evt, fn);
        }

        el.volume = this.volume;
        el.playbackRate = this.speed;

        // If metadata is already loaded (cached), grab duration immediately
        if (el.readyState >= 1 && el.duration) {
          this.duration = el.duration;
        }

        this._handlers = handlers;
        this._boundEl = el;
      };

      this.$nextTick(tryBind);
    },

    _detachMedia() {
      if (this._boundEl && this._handlers) {
        for (const [evt, fn] of Object.entries(this._handlers)) {
          this._boundEl.removeEventListener(evt, fn);
        }
      }
      this._handlers = null;
      this._boundEl = null;
    },

    _el() {
      return this.mediaMode === 'audio' ? this.$refs.audio : this.$refs.video;
    },

    switchMode(mode) {
      if (mode === this.mediaMode) return;
      const wasPlaying = this.playing;
      const time = this.currentTime;

      // Pause and detach the current element
      const oldEl = this._el();
      if (oldEl) oldEl.pause();
      this.playing = false;

      this.mediaMode = mode;

      // Re-attach to the new element
      this._attachMedia();

      this.$nextTick(() => {
        const newEl = this._el();
        if (!newEl) return;
        const resume = () => {
          newEl.currentTime = time;
          if (wasPlaying) newEl.play();
        };
        if (newEl.readyState >= 1) {
          resume();
        } else {
          newEl.addEventListener('loadedmetadata', resume, { once: true });
        }
      });
    },

    togglePlay() {
      const el = this._el();
      if (!el) return;
      if (this.playing) {
        el.pause();
      } else {
        el.play();
      }
    },

    seek(time) {
      const el = this._el();
      if (!el) return;
      const clamped = Math.max(0, Math.min(this.duration || Infinity, time));
      el.currentTime = clamped;
      this.currentTime = clamped;
      this.progressPct = this.duration > 0 ? (clamped / this.duration) * 100 : 0;
    },

    seekTo(time) {
      this.seek(time);
    },

    scrub(event) {
      const bar = this.$refs.seekBar;
      if (!bar) return;
      const rect = bar.getBoundingClientRect();
      const pct = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
      this.seek(pct * this.duration);
    },

    skipForward()  { this.seek(this.currentTime + 10); },
    skipBackward() { this.seek(this.currentTime - 10); },

    changeSpeed(e) {
      const s = parseFloat(e.target.value);
      this.speed = s;
      const el = this._el();
      if (el) el.playbackRate = s;
    },

    changeVolume(e) {
      this.volume = parseFloat(e.target.value);
      const el = this._el();
      if (el) el.volume = this.volume;
    },

    formatTime(seconds) {
      if (!seconds || isNaN(seconds)) return '00:00';
      const h = Math.floor(seconds / 3600);
      const m = Math.floor((seconds % 3600) / 60);
      const s = Math.floor(seconds % 60);
      if (h > 0) return `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
      return `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
    },

    _startDrag(event) {
      if (!this.isPip || this.pipMinimized) return;
      // Support both mouse and touch
      const clientX = event.touches ? event.touches[0].clientX : event.clientX;
      const clientY = event.touches ? event.touches[0].clientY : event.clientY;
      const card = document.getElementById('media-player-card');
      if (!card) return;
      const rect = card.getBoundingClientRect();
      this._isDragging = true;
      this._dragOffsetX = clientX - rect.left;
      this._dragOffsetY = clientY - rect.top;

      this._onDragMove = (e) => {
        if (!this._isDragging) return;
        const cx = e.touches ? e.touches[0].clientX : e.clientX;
        const cy = e.touches ? e.touches[0].clientY : e.clientY;
        const newX = cx - this._dragOffsetX;
        const newY = cy - this._dragOffsetY;
        // Clamp to viewport
        const cardEl = document.getElementById('media-player-card');
        const cw = cardEl ? cardEl.offsetWidth : 340;
        const ch = cardEl ? cardEl.offsetHeight : 400;
        this.pipDragX = Math.max(0, Math.min(window.innerWidth - cw, newX));
        this.pipDragY = Math.max(0, Math.min(window.innerHeight - ch, newY));
      };
      this._onDragEnd = () => {
        this._isDragging = false;
        window.removeEventListener('mousemove', this._onDragMove);
        window.removeEventListener('mouseup',   this._onDragEnd);
        window.removeEventListener('touchmove', this._onDragMove);
        window.removeEventListener('touchend',  this._onDragEnd);
      };
      window.addEventListener('mousemove', this._onDragMove);
      window.addEventListener('mouseup',   this._onDragEnd);
      window.addEventListener('touchmove', this._onDragMove, { passive: false });
      window.addEventListener('touchend',  this._onDragEnd);
      event.preventDefault();
    }
  };
};
