/**
 * echoLink() — Alpine.js component for the "Paste Link" mode on the upload page.
 * Completely independent from echoUpload(). A bug here cannot affect direct uploads.
 *
 * States: idle | validating | fetching_metadata | downloading | processing | preview | error
 */
window.echoLink = function () {
  return {
    state: 'idle',
    url: '',
    title: '',
    platformLabel: '',
    platformWarning: '',
    errorMsg: '',
    linkProgress: 0,
    _progressInterval: null,
    _pollInterval: null,

    init() {
      window.addEventListener('pageshow', (e) => {
        this.reset();
      });
      window.addEventListener('reset-link', () => {
        this.reset();
      });
    },

    pipelineSteps: [
      { label: 'Fetching info',   sub: 'Reading video metadata',        status: 'waiting' },
      { label: 'Downloading',     sub: 'Extracting audio track',        status: 'waiting' },
      { label: 'Transcribing',    sub: 'Converting speech to text',     status: 'waiting' },
      { label: 'Summarising',     sub: 'ECHO is reading your content',  status: 'waiting' },
      { label: 'Ready',           sub: 'Results prepared',              status: 'waiting' },
    ],

    // ── URL input: real-time platform detection ────────────────────────────
    onUrlInput() {
      this.platformLabel = '';
      this.platformWarning = '';
      this.errorMsg = '';
      const u = this.url.trim();
      if (!u) return;

      try {
        const parsed = new URL(u);
        const host = parsed.hostname.replace(/^www\./, '');
        const path = parsed.pathname.toLowerCase();
        const sp   = new URLSearchParams(parsed.search);

        // YouTube
        if (['youtube.com', 'youtu.be', 'm.youtube.com'].includes(host)) {
          if (sp.has('list') && !sp.has('v')) {
            this.platformWarning = '⚠ Playlists are not supported — paste a single video link.';
          } else if (path.includes('/watch') || host === 'youtu.be' || path.includes('/shorts/') || path.includes('/live/') || sp.has('v')) {
            this.platformLabel = '▶ YouTube detected ✓';
          }
          return;
        }
        // Google Drive
        if (host === 'drive.google.com') {
          if (path.includes('/file/d/') || sp.has('id')) {
            this.platformLabel = '📁 Google Drive detected ✓';
          } else {
            this.platformWarning = '⚠ Please paste a direct Google Drive file link.';
          }
          return;
        }
        // Dropbox
        if (host === 'dropbox.com') {
          if (path.startsWith('/s/') || path.includes('/scl/')) {
            this.platformLabel = '📦 Dropbox detected ✓';
          } else {
            this.platformWarning = '⚠ Please paste a Dropbox shared file link.';
          }
          return;
        }
        // Vimeo
        if (host === 'vimeo.com' || host === 'player.vimeo.com') {
          this.platformLabel = '🎬 Vimeo detected ✓';
          return;
        }
        // Twitter/X
        if (['twitter.com', 'x.com'].includes(host)) {
          this.platformLabel = '🐦 Twitter/X detected ✓';
          return;
        }
        // Facebook
        if (['facebook.com', 'fb.com', 'fb.watch'].includes(host)) {
          this.platformLabel = '📘 Facebook detected ✓';
          return;
        }
        // Instagram
        if (host === 'instagram.com') {
          this.platformLabel = '📸 Instagram detected ✓';
          return;
        }
        // TikTok
        if (['tiktok.com', 'vm.tiktok.com'].includes(host)) {
          this.platformLabel = '🎵 TikTok detected ✓';
          return;
        }
        // Direct file link
        const directExts = ['.mp3','.mp4','.m4a','.wav','.ogg','.webm','.flac','.opus','.mkv','.mov','.avi'];
        const ext = '.' + path.split('.').pop();
        if (directExts.includes(ext)) {
          this.platformLabel = '🔗 Direct media link ✓';
          return;
        }
        // Generic
        this.platformLabel = '🌐 External link — will attempt download';
      } catch (e) {
        // Not a valid URL yet — user might still be typing
      }
    },

    // ── Submit ──────────────────────────────────────────────────────────────
    async submit() {
      const u = this.url.trim();
      if (!u) return;

      if (this.platformWarning) {
        this.errorMsg = this.platformWarning.replace('⚠ ', '');
        return;
      }

      this.state = 'validating';
      this.errorMsg = '';
      this._resetPipeline();
      
      this.linkProgress = 0;
      this._polledData = null;
      this._polledSessionId = null;
      if (this._progressInterval) clearInterval(this._progressInterval);
      
      // Increment smoothly over ~4.5 seconds (to match lecture upload feel)
      const totalDuration = 4500; // ms
      const interval = 50; // ms
      const steps = totalDuration / interval;
      const inc = 100 / steps;
      this._progressInterval = setInterval(() => {
        if (this.linkProgress < 100) {
          this.linkProgress = Math.min(100, this.linkProgress + inc);
        } else {
          // Keep at 100% for a brief pause so user sees closure
          clearInterval(this._progressInterval);
          this._progressInterval = null;
          setTimeout(() => {
            if (this.state === 'validating') {
              this.state = 'fetching_metadata';
              this._setActiveStep(0);
            }
            if (this._polledData && this._polledSessionId) {
              this._applyStatus(this._polledData, this._polledSessionId);
            }
          }, 800); // 0.8s pause at 100%
        }
      }, interval);

      const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';

      let data;
      try {
        const res = await fetch('/sessions/from-url/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrf,
          },
          body: JSON.stringify({ url: u, title: this.title.trim() || undefined }),
        });
        data = await res.json();
        if (!res.ok) {
          if (this._progressInterval) clearInterval(this._progressInterval);
          this.state = 'error';
          this.errorMsg = data.error || 'Something went wrong. Please try again.';
          return;
        }
      } catch (e) {
        if (this._progressInterval) clearInterval(this._progressInterval);
        this.state = 'error';
        this.errorMsg = 'Network error. Please check your connection and try again.';
        return;
      }

      // Begin polling
      const sessionId = data.session_id;
      this._startPolling(sessionId);
    },

    // ── Polling ─────────────────────────────────────────────────────────────
    _startPolling(sessionId) {
      const poll = async () => {
        try {
          const res = await fetch(`/sessions/${sessionId}/status/`);
          const data = await res.json();
          
          if (data.status === 'failed') {
            this._clearPoll();
            if (this._progressInterval) clearInterval(this._progressInterval);
            this.state = 'error';
            this.errorMsg = data.error || 'Processing failed. Please try a different link.';
            return;
          }
          
          this._polledData = data;
          this._polledSessionId = sessionId;

          if (this.linkProgress >= 100 || this.state !== 'validating') {
            this._applyStatus(data, sessionId);
          }
        } catch (e) {
          // Network hiccup — keep polling
        }
      };

      // Run immediately first
      poll();
      this._pollInterval = setInterval(poll, 2000);
    },

    _applyStatus(data, sessionId) {
      const s = data.status;

      if (this.state === 'validating') {
        if (s === 'initiated' || s === 'fetching_metadata') {
          this.state = 'fetching_metadata';
          this._setActiveStep(0);
        } else if (s === 'downloading') {
          this.state = 'downloading';
          this._setActiveStep(1);
        } else if (s === 'transcribing' || s === 'uploading') {
          this.state = 'processing';
          this._setActiveStep(2);
        } else if (s === 'summarising') {
          this.state = 'processing';
          this._setActiveStep(3);
        }
      }

      if (s === 'initiated' || s === 'fetching_metadata') {
        this.state = 'fetching_metadata';
        this._setActiveStep(0);
      } else if (s === 'downloading') {
        this.state = 'downloading';
        this._setActiveStep(1);
      } else if (s === 'transcribing' || s === 'uploading') {
        this.state = 'processing';
        this._setActiveStep(2);
      } else if (s === 'summarising') {
        this.state = 'processing';
        this._setActiveStep(3);
      } else if (s === 'complete') {
        this._clearPoll();
        if (this._progressInterval) clearInterval(this._progressInterval);
        this.linkProgress = 100;
        
        // Ensure pipeline container is shown while cascading
        this.state = 'processing';
        
        let delay = 0;
        for (let i = 0; i < this.pipelineSteps.length; i++) {
          if (this.pipelineSteps[i].status !== 'done') {
            setTimeout(() => {
              this.pipelineSteps[i].status = 'done';
              if (i < this.pipelineSteps.length - 1) {
                  this.pipelineSteps[i+1].status = 'active';
              }
            }, delay);
            delay += 600;
          }
        }

        setTimeout(() => {
          this.state = 'preview';
          setTimeout(() => {
            window.location.href = data.result_url;
          }, 3200);
        }, delay + 400);
      } else if (s === 'failed') {
        this._clearPoll();
        if (this._progressInterval) clearInterval(this._progressInterval);
        this.state = 'error';
        this.errorMsg = data.error || 'Processing failed. Please try a different link.';
      }
    },

    _setActiveStep(idx) {
      for (let i = 0; i < this.pipelineSteps.length; i++) {
        if (i < idx)  this.pipelineSteps[i].status = 'done';
        else if (i === idx) this.pipelineSteps[i].status = 'active';
        else          this.pipelineSteps[i].status = 'waiting';
      }
    },

    _clearPoll() {
      if (this._pollInterval) {
        clearInterval(this._pollInterval);
        this._pollInterval = null;
      }
    },

    _resetPipeline() {
      this.pipelineSteps.forEach(s => s.status = 'waiting');
    },

    reset() {
      this._clearPoll();
      this.state = 'idle';
      this.url = '';
      this.title = '';
      this.platformLabel = '';
      this.platformWarning = '';
      this.errorMsg = '';
      this.linkProgress = 0;
      if (this._progressInterval) clearInterval(this._progressInterval);
      this._resetPipeline();
    },
  };
};
