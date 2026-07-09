window.echoUpload = function() {
  return {
    state: 'idle',         // idle | hovering | selected | uploading | processing | preview
    selectedFile: {},
    uploadProgress: 0,
    uploadETA: '',
    _uploadStart: 0,

    orbitLabels: ['Drop lecture', 'Voice memo', 'Meeting recording', 'Zoom recording', 'Audio note'],
    orbitIdx: 0,

    pipelineSteps: [
      { label: 'Uploading',    sub: 'Securing your file',           status: 'waiting' },
      { label: 'Transcribing', sub: 'Converting speech to text',    status: 'waiting' },
      { label: 'Summarising',  sub: 'ECHO is reading your lecture', status: 'waiting' },
      { label: 'Ready',        sub: 'Results prepared',             status: 'waiting' },
    ],

    init() {
      // Rotate orbit labels
      setInterval(() => {
        this.orbitIdx = (this.orbitIdx + 1) % this.orbitLabels.length;
      }, 2600);

      // Trigger canvas animations when state changes
      this.$watch('state', val => {
        if (val === 'processing') this.$nextTick(() => this._animateWave());
        if (val === 'preview')    this.$nextTick(() => this._animateRawWave());
      });
    },

    // ── Drag & Drop ──────────────────────────────────────────────────
    onDragOver()  { this.state = 'hovering'; },
    onDragLeave() { if (this.state === 'hovering') this.state = 'idle'; },
    onDrop(e) {
      this.state = 'idle';
      const file = e.dataTransfer.files[0];
      if (file) this._handleFile(file);
    },
    onFileSelect(e) {
      const file = e.target.files[0];
      if (file) this._handleFile(file);
    },

    // ── File validation ───────────────────────────────────────────────
    _handleFile(file) {
      if (file.size > 1024 * 1024 * 1024) {
        this._toast('File exceeds 1 GB. Please upload a smaller file.', 'error');
        return;
      }
      const ext = file.name.match(/\.[^.]+$/)?.[0]?.toLowerCase() || '';
      const allowed = ['.mp3','.mp4','.mpeg','.mpga','.m4a','.wav','.webm','.ogg','.oga','.flac','.mov','.avi','.mkv'];
      if (!allowed.includes(ext)) {
        this._toast('Unsupported format. Try MP3, MP4, WAV, FLAC or M4A.', 'error');
        return;
      }
      const sizeStr = file.size > 1_048_576
        ? (file.size / 1_048_576).toFixed(1) + ' MB'
        : (file.size / 1024).toFixed(0) + ' KB';
      const estMins = Math.max(1, Math.round(file.size / (128 * 1024 / 8 * 60)));
      const durationStr = estMins > 60
        ? Math.floor(estMins / 60) + 'h ' + (estMins % 60) + 'min'
        : '~' + estMins + ' min';
      this.selectedFile = { name: file.name, sizeStr, durationStr, raw: file };
      this.state = 'selected';
    },

    reset() {
      this.state = 'idle';
      this.selectedFile = {};
      const fi = document.getElementById('echo-file-input');
      if (fi) fi.value = '';
    },

    // ── Upload via XHR (tracks progress, then shows pipeline) ─────────
    startUpload() {
      this.state = 'uploading';
      this.uploadProgress = 0;
      this._uploadStart = Date.now();

      // Reset pipeline
      this.pipelineSteps.forEach(s => s.status = 'waiting');

      const formData = new FormData();
      formData.append('audio_file', this.selectedFile.raw);

      const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
      const xhr  = new XMLHttpRequest();

      xhr.upload.addEventListener('progress', e => {
        if (!e.lengthComputable) return;
        this.uploadProgress = Math.round(e.loaded / e.total * 100);
        const elapsed   = (Date.now() - this._uploadStart) / 1000;
        const rate      = e.loaded / elapsed;                     // bytes/s
        const remaining = (e.total - e.loaded) / rate;           // seconds
        this.uploadETA = remaining > 60
          ? Math.round(remaining / 60) + 'm remaining'
          : Math.round(remaining) + 's remaining';

        // START PIPELINE EARLY: Don't wait for server response to show 'processing'
        if (this.uploadProgress === 100 && this.state === 'uploading') {
          this.state = 'processing';
          this.pipelineSteps[0].status = 'done';
          this.pipelineSteps[1].status = 'active';

          // Animate to 'Summarising' after a short delay
          setTimeout(() => {
            if (this.state === 'processing') {
              this.pipelineSteps[1].status = 'done';
              this.pipelineSteps[2].status = 'active';
            }
          }, 1200);
        }
      });

      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 400) {
          const redirectUrl = xhr.getResponseHeader('HX-Redirect') || xhr.responseURL;
          
          if (this.state !== 'processing') {
            this.state = 'processing';
            this.pipelineSteps[0].status = 'done';
          }

          // Complete the remaining steps now that the server has responded
          this.pipelineSteps[1].status = 'done';
          this.pipelineSteps[2].status = 'done';
          this.pipelineSteps[3].status = 'active';

          setTimeout(() => {
            this.pipelineSteps[3].status = 'done';
            setTimeout(() => {
              this.state = 'preview';
              setTimeout(() => {
                window.location.href = redirectUrl;
              }, 3200);
            }, 400);
          }, 1000);

        } else {
          this._toast('Upload failed (' + xhr.status + '). Please try again.', 'error');
          this.state = 'idle';
        }
      });

      xhr.addEventListener('error', () => {
        this._toast('Network error. Check your connection.', 'error');
        this.state = 'idle';
      });

      xhr.open('POST', '/upload/');
      xhr.setRequestHeader('X-CSRFToken', csrf);
      // Ask the server for the redirect URL, not a full page redirect
      xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
      xhr.send(formData);
    },

    // ── Canvas animations ─────────────────────────────────────────────
    _animateWave() {
      const canvas = this.$el.querySelector('.echo-wave-canvas');
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      canvas.width  = canvas.offsetWidth  || 400;
      canvas.height = canvas.offsetHeight || 200;
      let t = 0;
      const draw = () => {
        if (this.state !== 'processing') return;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.strokeStyle = '#C084FC';
        ctx.lineWidth   = 1.5;
        ctx.beginPath();
        for (let x = 0; x < canvas.width; x++) {
          const y = canvas.height / 2
            + Math.sin((x / canvas.width) * Math.PI * 8 + t) * (canvas.height * 0.28)
            + Math.sin((x / canvas.width) * Math.PI * 3 + t * 0.7) * (canvas.height * 0.12);
          x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
        ctx.stroke();
        t += 0.04;
        requestAnimationFrame(draw);
      };
      draw();
    },

    _animateRawWave() {
      const canvas = this.$el.querySelector('.echo-raw-wave');
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.strokeStyle = '#7C3AED';
      ctx.lineWidth   = 2;
      ctx.beginPath();
      for (let x = 0; x < canvas.width; x++) {
        const y = canvas.height / 2 + (Math.random() - 0.5) * canvas.height * 0.65;
        x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      }
      ctx.stroke();
    },

    // ── Toast helper ──────────────────────────────────────────────────
    _toast(msg, type = 'info') {
      const el = document.createElement('div');
      el.textContent = msg;
      Object.assign(el.style, {
        position: 'fixed', bottom: '2rem', left: '50%',
        transform: 'translateX(-50%) translateY(1rem)',
        background: type === 'error' ? '#EF4444' : '#C084FC',
        color: 'white', padding: '10px 22px', borderRadius: '999px',
        fontSize: '0.82rem', fontWeight: '600', zIndex: '9999',
        opacity: '0', transition: 'all 0.3s ease',
        boxShadow: '0 4px 20px rgba(0,0,0,0.25)',
      });
      document.body.appendChild(el);
      requestAnimationFrame(() => {
        el.style.opacity = '1';
        el.style.transform = 'translateX(-50%) translateY(0)';
      });
      setTimeout(() => {
        el.style.opacity = '0';
        setTimeout(() => el.remove(), 350);
      }, 3500);
    },
  };
};
