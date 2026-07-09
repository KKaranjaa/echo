// ═══════════════════════════════════════════════════════════════
// ECHO Chat Panel — Alpine.js component
// Loaded globally in base.html so it survives HTMX hx-boost swaps.
// ═══════════════════════════════════════════════════════════════

window.chatPanel = function (sessionId, initialQuestion) {
  return {
    sessionId,
    inputText: initialQuestion || '',
    messages: [],
    isWaiting: false,
    errorMessage: '',
    thinkingText: 'Searching transcript...',
    thinkInterval: null,
    showScrollButtons: false,

    init() {
      // ── Hydrate past messages from the JSON island ──────────────
      const dataEl = document.getElementById('session-messages-data');
      if (dataEl && dataEl.textContent.trim()) {
        try {
          const msgs = JSON.parse(dataEl.textContent);
          msgs.forEach(m => { m.isStreaming = false; this.messages.push(m); });
        } catch (e) { console.error('Failed to parse session messages', e); }
      }

      // ── Scroll to the latest message ────────────────────────────
      if (this.messages.length) {
        this._scrollToBottom();
      }

      // ── Setup Resize Observer for scroll container ──────────────
      if (this.$refs.messages) {
        const observer = new ResizeObserver(() => this.checkScroll());
        observer.observe(this.$refs.messages);
      }

      // ── Auto-send starter question from ?q= URL param ───────────
      // Guard: don't re-send if this exact question is already the last user message
      if (initialQuestion) {
        const lastUserMsg = this.messages.slice().reverse().find(m => m.role === 'user');
        const alreadySent = lastUserMsg && lastUserMsg.content.trim() === initialQuestion.trim();
        if (!alreadySent) {
          // Wait for Alpine to finish its first reactive flush + browser paint before sending.
          // Using double-RAF + small buffer is more reliable than $nextTick alone,
          // especially under hx-boost where scripts re-execute in a different tick order.
          requestAnimationFrame(() => {
            requestAnimationFrame(() => {
              setTimeout(() => {
                this.inputText = initialQuestion;
                this.sendMessage();
              }, 50);
            });
          });
        }
      }
    },

    checkScroll() {
      const el = this.$refs.messages;
      if (el) {
        this.showScrollButtons = el.scrollHeight > el.clientHeight;
      }
    },

    setInput(text) {
      this.inputText = text;
      this.$refs.inputArea && this.$refs.inputArea.focus();
    },

    handleKeydown(e) {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.sendMessage(); }
    },

    resizeInput() {
      const el = this.$refs.inputArea;
      if (!el) return;
      // Temporarily set height to auto to shrink if text was deleted
      el.style.height = 'auto';
      // Set height to precisely fit the content
      el.style.height = el.scrollHeight + 'px';
    },

    _scrollToBottom(smooth = false) {
      // Use double requestAnimationFrame to guarantee the browser has
      // completed layout and paint cycles before measuring scrollHeight.
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          const el = this.$refs.messages;
          if (el) {
            el.scrollTo({
              top: el.scrollHeight,
              behavior: smooth ? 'smooth' : 'auto'
            });
            this.checkScroll();
          }
        });
      });
    },

    _scrollToTop(smooth = false) {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          const el = this.$refs.messages;
          if (el) {
            el.scrollTo({
              top: 0,
              behavior: smooth ? 'smooth' : 'auto'
            });
            this.checkScroll();
          }
        });
      });
    },

    sendMessage() {
      if (!this.inputText.trim() || this.isWaiting) return;
      this.errorMessage = '';
      const text = this.inputText.trim();
      this.inputText = '';
      // Reset the textarea height after clearing
      this.$nextTick(() => { this.resizeInput(); });

      this.messages.push({
        role: 'user',
        content: text,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        isStreaming: false,
      });

      const asstIndex = this.messages.length;
      this.messages.push({
        role: 'assistant',
        content: '',
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        isStreaming: true,
        error: false,
      });

      this._scrollToBottom();
      this.isWaiting = true;

      // Start the filler text rotation
      let phaseIndex = 0;
      // Truncate text for the 'thinking' UI if it's too long
      const shortText = text.length > 40 ? text.substring(0, 40) + '...' : text;
      const phases = [
        'Thinking',
        `Analyzing intent: "${shortText}"`,
        'Searching transcript and knowledge base',
        'Formulating response'
      ];
      this.thinkingText = phases[0];
      if (this.thinkInterval) clearInterval(this.thinkInterval);
      let ticks = 0;
      this.thinkInterval = setInterval(() => {
        ticks++;
        if (phaseIndex < phases.length - 1) {
          phaseIndex++;
          this.thinkingText = phases[phaseIndex];
        } else if (ticks === phases.length + 2) {
          this.thinkingText = "Taking a bit longer than expected";
          clearInterval(this.thinkInterval);
        }
      }, 2000);

      fetch(`/chat/${this.sessionId}/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      })
        .then(async response => {
          if (!response.ok) {
            if (this.thinkInterval) clearInterval(this.thinkInterval);
            const err = await response.json().catch(() => ({ error: 'Network error' }));
            this.messages[asstIndex].error = true;
            this.messages[asstIndex].content = err.error || 'Request failed';
            this.messages[asstIndex].isStreaming = false;
            this.isWaiting = false;
            return;
          }
          const reader = response.body.getReader();
          const decoder = new TextDecoder('utf-8');
          let done = false;
          while (!done) {
            const { value, done: readerDone } = await reader.read();
            done = readerDone;
            if (value) {
              decoder.decode(value, { stream: true }).split('\n').forEach(line => {
                if (line.startsWith('data: ')) {
                  try {
                    const data = JSON.parse(line.substring(6));
                    if (data.chunk) {
                      if (this.thinkInterval) {
                        clearInterval(this.thinkInterval);
                        this.thinkInterval = null;
                      }
                      this.messages[asstIndex].content += data.chunk;
                      this._scrollToBottom();
                    } else if (data.done) {
                      this.messages[asstIndex].isStreaming = false;
                      this.isWaiting = false;
                    } else if (data.error) {
                      this.messages[asstIndex].error = true;
                      this.messages[asstIndex].content = data.error;
                      this.messages[asstIndex].isStreaming = false;
                      this.isWaiting = false;
                    }
                  } catch (e) { /* ignore incomplete SSE frames */ }
                }
              });
            }
          }
          if (this.thinkInterval) clearInterval(this.thinkInterval);
          this.messages[asstIndex].isStreaming = false;
          this.isWaiting = false;
        })
        .catch(() => {
          if (this.thinkInterval) clearInterval(this.thinkInterval);
          this.messages[asstIndex].error = true;
          this.messages[asstIndex].content = 'Connection error. Please try again.';
          this.messages[asstIndex].isStreaming = false;
          this.isWaiting = false;
        });
    },
  };
};
