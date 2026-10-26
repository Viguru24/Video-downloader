// OmniDownloader - Universal Video PWA Client
(function () {
  'use strict';

  // State
  let currentTask = null;
  let activeEventSource = null;
  let currentInspectedMedia = null;
  let selectedQualityId = 'best';
  let isAudioOnly = false;
  let selectedAudioFormat = 'mp3';
  let deferredInstallPrompt = null;
  let batchQueue = [];
  let isBatchRunning = false;

  // Audio synthesis for tactile UX
  const audioCtx = (typeof AudioContext !== 'undefined' || typeof webkitAudioContext !== 'undefined')
    ? new (window.AudioContext || window.webkitAudioContext)()
    : null;

  function playChime(type = 'success') {
    if (!audioCtx) return;
    try {
      if (audioCtx.state === 'suspended') {
        audioCtx.resume();
      }
      const now = audioCtx.currentTime;
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.connect(gain);
      gain.connect(audioCtx.destination);

      if (type === 'success') {
        osc.type = 'sine';
        osc.frequency.setValueAtTime(523.25, now); // C5
        osc.frequency.exponentialRampToValueAtTime(659.25, now + 0.1); // E5
        osc.frequency.exponentialRampToValueAtTime(783.99, now + 0.2); // G5
        osc.frequency.exponentialRampToValueAtTime(1046.50, now + 0.35); // C6
        gain.gain.setValueAtTime(0.08, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.5);
        osc.start(now);
        osc.stop(now + 0.5);
      } else if (type === 'click') {
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(800, now);
        osc.frequency.exponentialRampToValueAtTime(400, now + 0.04);
        gain.gain.setValueAtTime(0.04, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.04);
        osc.start(now);
        osc.stop(now + 0.04);
      }
    } catch (e) {
      // Audio autoplay policy catch
    }
  }

  // Toast UI
  function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = 'toast';
    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    if (type === 'error') icon = '⚠️';
    toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3800);
  }

  // DOM Elements
  const searchInput = document.getElementById('search-input');
  const btnAnalyze = document.getElementById('btn-analyze');
  const btnPaste = document.getElementById('btn-paste');
  const platformBadge = document.getElementById('platform-badge');
  const loadingIndicator = document.getElementById('loading-indicator');
  const mediaResultCard = document.getElementById('media-result-card');
  const progressCard = document.getElementById('progress-card');
  const btnInstall = document.getElementById('btn-install');
  const libraryGrid = document.getElementById('library-grid');
  const librarySearch = document.getElementById('library-search');

  // Platform detection helper
  function detectPlatformName(url) {
    const u = url.toLowerCase();
    if (u.includes('youtube.com') || u.includes('youtu.be')) return 'YouTube';
    if (u.includes('tiktok.com')) return 'TikTok';
    if (u.includes('twitter.com') || u.includes('x.com')) return 'X / Twitter';
    if (u.includes('instagram.com')) return 'Instagram';
    if (u.includes('reddit.com')) return 'Reddit';
    if (u.includes('facebook.com') || u.includes('fb.watch')) return 'Facebook';
    if (u.includes('vimeo.com')) return 'Vimeo';
    if (u.includes('twitch.tv')) return 'Twitch';
    if (u.includes('bilibili.com')) return 'Bilibili';
    if (u.includes('rumble.com')) return 'Rumble';
    if (u.endsWith('.mp4') || u.endsWith('.m3u8')) return 'Direct Stream';
    return 'Universal Web';
  }

  // Update platform badge dynamically
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      const val = searchInput.value.trim();
      if (val) {
        platformBadge.textContent = detectPlatformName(val);
      } else {
        platformBadge.textContent = 'Universal Web';
      }
    });

    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        analyzeUrl();
      }
    });
  }

  // Auto-paste from clipboard
  if (btnPaste) {
    btnPaste.addEventListener('click', async () => {
      playChime('click');
      try {
        const text = await navigator.clipboard.readText();
        if (text && text.startsWith('http')) {
          searchInput.value = text;
          platformBadge.textContent = detectPlatformName(text);
          showToast('URL pasted from clipboard!', 'success');
          analyzeUrl();
        } else {
          showToast('Clipboard does not contain a valid URL', 'error');
        }
      } catch (err) {
        const manual = prompt('Paste your video link here:');
        if (manual) {
          searchInput.value = manual;
          platformBadge.textContent = detectPlatformName(manual);
          analyzeUrl();
        }
      }
    });
  }

  // Tab Navigation
  document.querySelectorAll('.tab-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      playChime('click');
      const targetTab = btn.getAttribute('data-tab');
      document.querySelectorAll('.tab-btn').forEach((b) => b.classList.remove('active'));
      document.querySelectorAll('.tab-view').forEach((v) => v.classList.remove('active'));

      btn.classList.add('active');
      const view = document.getElementById(`view-${targetTab}`);
      if (view) view.classList.add('active');

      if (targetTab === 'library') {
        loadLibrary();
      }
    });
  });

  // Analyze media URL
  async function analyzeUrl(targetUrl = null) {
    const url = targetUrl || searchInput.value.trim();
    if (!url) {
      showToast('Please enter a video URL', 'error');
      return;
    }

    loadingIndicator.style.display = 'flex';
    mediaResultCard.style.display = 'none';
    progressCard.style.display = 'none';

    try {
      const resp = await fetch('/api/inspect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      });

      const data = await resp.json();
      loadingIndicator.style.display = 'none';

      if (!data.success) {
        showToast(data.error || 'Failed to inspect video', 'error');
        return;
      }

      currentInspectedMedia = data;
      renderMediaInspection(data);
    } catch (err) {
      loadingIndicator.style.display = 'none';
      showToast('Connection error: ' + err.message, 'error');
    }
  }

  if (btnAnalyze) {
    btnAnalyze.addEventListener('click', () => analyzeUrl());
  }

  // Render video preview and options
  function renderMediaInspection(data) {
    document.getElementById('meta-title').textContent = data.title || 'Extracted Video';
    document.getElementById('meta-author').textContent = data.author ? `By ${data.author}` : '';
    document.getElementById('meta-platform').textContent = data.platform || 'Web Video';
    document.getElementById('meta-duration').textContent = data.duration_str || '';

    const thumbImg = document.getElementById('thumb-img');
    if (data.thumbnail) {
      thumbImg.src = data.thumbnail;
      thumbImg.style.display = 'block';
    } else {
      thumbImg.src = '/static/icons/icon-512.png';
    }

    renderQualityGrid('video');
    mediaResultCard.style.display = 'block';
    mediaResultCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  // Switch between Video vs Audio format selectors
  window.switchFormatTab = function (type) {
    playChime('click');
    document.querySelectorAll('.format-tab-btn').forEach((b) => b.classList.remove('active'));
    if (type === 'video') {
      document.getElementById('tab-btn-video').classList.add('active');
      isAudioOnly = false;
      renderQualityGrid('video');
    } else {
      document.getElementById('tab-btn-audio').classList.add('active');
      isAudioOnly = true;
      renderQualityGrid('audio');
    }
  };

  function renderQualityGrid(type) {
    const grid = document.getElementById('quality-grid');
    grid.innerHTML = '';

    if (!currentInspectedMedia) return;

    if (type === 'video') {
      const qualities = currentInspectedMedia.qualities || [];
      qualities.forEach((q, idx) => {
        const card = document.createElement('div');
        card.className = `quality-card ${idx === 0 ? 'selected' : ''}`;
        if (idx === 0) selectedQualityId = q.id;

        card.innerHTML = `
          <div>
            <div class="quality-card-label">${q.label}</div>
            <div style="font-size:0.75rem; color:var(--text-muted);">${q.ext.toUpperCase()} ${q.filesize_str ? '• ' + q.filesize_str : ''}</div>
          </div>
          <span class="quality-card-badge">${q.badge || (q.height ? q.height + 'p' : 'HD')}</span>
        `;
        card.addEventListener('click', () => {
          playChime('click');
          document.querySelectorAll('.quality-card').forEach((c) => c.classList.remove('selected'));
          card.classList.add('selected');
          selectedQualityId = q.id;
        });
        grid.appendChild(card);
      });
    } else {
      // Audio formats
      const audios = currentInspectedMedia.audio_qualities || [];
      audios.forEach((a, idx) => {
        const card = document.createElement('div');
        card.className = `quality-card ${idx === 0 ? 'selected' : ''}`;
        if (idx === 0) selectedAudioFormat = a.ext;

        card.innerHTML = `
          <div>
            <div class="quality-card-label">${a.label}</div>
            <div style="font-size:0.75rem; color:var(--text-muted);">${a.ext.toUpperCase()} Audio</div>
          </div>
          <span class="quality-card-badge">HQ Audio</span>
        `;
        card.addEventListener('click', () => {
          playChime('click');
          document.querySelectorAll('.quality-card').forEach((c) => c.classList.remove('selected'));
          card.classList.add('selected');
          selectedAudioFormat = a.ext;
        });
        grid.appendChild(card);
      });
    }
  }

  // Start Download
  const btnStartDownload = document.getElementById('btn-start-download');
  if (btnStartDownload) {
    btnStartDownload.addEventListener('click', async () => {
      if (!currentInspectedMedia) return;
      playChime('click');

      const payload = {
        url: currentInspectedMedia.url,
        quality_id: selectedQualityId,
        audio_only: isAudioOnly,
        audio_format: selectedAudioFormat,
        embed_thumbnail: true
      };

      try {
        btnStartDownload.disabled = true;
        btnStartDownload.textContent = 'Initializing...';

        const resp = await fetch('/api/download', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        const res = await resp.json();
        btnStartDownload.disabled = false;
        btnStartDownload.textContent = '⚡ Download Now';

        if (res.success && res.task_id) {
          mediaResultCard.style.display = 'none';
          startProgressTracking(res.task_id, currentInspectedMedia.title);
        } else {
          showToast('Failed to start download: ' + (res.detail || 'Unknown error'), 'error');
        }
      } catch (err) {
        btnStartDownload.disabled = false;
        btnStartDownload.textContent = '⚡ Download Now';
        showToast('Download error: ' + err.message, 'error');
      }
    });
  }

  // Real-time SSE Progress Tracking
  function startProgressTracking(taskId, title) {
    currentTask = taskId;
    progressCard.style.display = 'block';
    progressCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    document.getElementById('progress-title').textContent = title || 'Processing Media';
    document.getElementById('completed-box').style.display = 'none';

    if (activeEventSource) {
      activeEventSource.close();
    }

    const sse = new EventSource(`/api/tasks/${taskId}/stream`);
    activeEventSource = sse;

    sse.onmessage = (event) => {
      try {
        const task = JSON.parse(event.data);
        updateProgressUI(task);

        if (task.status === 'completed') {
          sse.close();
          handleDownloadSuccess(task);
        } else if (task.status === 'error' || task.status === 'cancelled') {
          sse.close();
          showToast(task.stage || task.error || 'Download stopped', 'error');
        }
      } catch (e) {
        console.error('SSE parse error:', e);
      }
    };

    sse.onerror = () => {
      // Fallback polling if SSE disconnects
      setTimeout(() => pollTaskStatus(taskId), 1000);
    };
  }

  function updateProgressUI(task) {
    const percent = Math.min(100, Math.max(0, task.percent || 0));
    document.getElementById('progress-bar-fill').style.width = `${percent}%`;
    document.getElementById('progress-percent').textContent = `${Math.round(percent)}%`;
    document.getElementById('progress-stage').textContent = task.stage || 'Processing...';

    const speedStr = task.speed_str || '';
    const etaStr = task.eta_str || '';
    const downloadedStr = task.downloaded_bytes ? (task.downloaded_bytes / (1024 * 1024)).toFixed(1) + ' MB' : '';
    const totalStr = task.total_bytes ? (task.total_bytes / (1024 * 1024)).toFixed(1) + ' MB' : '';

    let statText = speedStr;
    if (downloadedStr && totalStr) statText += ` • ${downloadedStr} / ${totalStr}`;
    if (etaStr) statText += ` • ${etaStr}`;

    document.getElementById('progress-stats').textContent = statText;
  }

  async function pollTaskStatus(taskId) {
    try {
      const resp = await fetch(`/api/tasks/${taskId}`);
      const task = await resp.json();
      updateProgressUI(task);
      if (task.status === 'completed') {
        handleDownloadSuccess(task);
      } else if (task.status === 'downloading' || task.status === 'starting' || task.status === 'processing') {
        setTimeout(() => pollTaskStatus(taskId), 800);
      }
    } catch (e) {
      console.warn('Poll error', e);
    }
  }

  function handleDownloadSuccess(task) {
    playChime('success');
    showToast('Download completed successfully!', 'success');

    const completedBox = document.getElementById('completed-box');
    completedBox.style.display = 'flex';

    document.getElementById('completed-filename').textContent = task.filename || 'media.mp4';
    document.getElementById('completed-size').textContent = task.filesize_str || '';

    const completedPathEl = document.getElementById('completed-path');
    if (completedPathEl) {
      const fullPath = task.filepath || (task.saved_dir ? task.saved_dir + '\\' + task.filename : 'Default Directory');
      completedPathEl.textContent = 'Saved to: ' + fullPath;
      completedPathEl.title = fullPath;
    }

    const btnCompletedOpenFolder = document.getElementById('btn-completed-open-folder');
    if (btnCompletedOpenFolder) {
      btnCompletedOpenFolder.onclick = async () => {
        playChime('click');
        const folder = task.saved_dir || (task.filepath ? task.filepath.substring(0, task.filepath.lastIndexOf('\\')) : null);
        await fetch('/api/config/open-folder', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ folder_path: folder })
        });
        showToast('Opened in Windows Explorer', 'success');
      };
    }

    // Direct browser download trigger
    const saveToBrowserChecked = document.getElementById('check-browser-download')?.checked ?? true;
    if (saveToBrowserChecked) {
      triggerBrowserFileSave(`/api/file/${task.id}`, task.filename);
    }

    // Hook play button
    const btnPlayInApp = document.getElementById('btn-play-in-app');
    btnPlayInApp.onclick = () => {
      playChime('click');
      openModalPlayer(`/api/file/${task.id}`, task.title || task.filename);
    };

    // Hook save to browser button
    const btnSaveBrowser = document.getElementById('btn-save-browser');
    btnSaveBrowser.onclick = () => {
      playChime('click');
      triggerBrowserFileSave(`/api/file/${task.id}`, task.filename);
    };

    // Refresh library if active
    loadLibrary();
  }

  function triggerBrowserFileSave(url, filename) {
    const a = document.createElement('a');
    a.href = url;
    a.download = filename || 'download';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  // Cancel Task
  const btnCancel = document.getElementById('btn-cancel');
  if (btnCancel) {
    btnCancel.addEventListener('click', async () => {
      if (!currentTask) return;
      playChime('click');
      if (confirm('Cancel this download?')) {
        await fetch(`/api/tasks/${currentTask}/cancel`, { method: 'POST' });
        if (activeEventSource) activeEventSource.close();
        progressCard.style.display = 'none';
        showToast('Download cancelled', 'info');
      }
    });
  }

  // Batch Downloader
  const btnStartBatch = document.getElementById('btn-start-batch');
  const batchInput = document.getElementById('batch-urls');
  const batchQueueList = document.getElementById('batch-queue-list');

  if (btnStartBatch && batchInput) {
    btnStartBatch.addEventListener('click', async () => {
      playChime('click');
      const lines = batchInput.value.split('\n').map((l) => l.trim()).filter((l) => l.startsWith('http'));
      if (lines.length === 0) {
        showToast('Please enter at least one valid HTTP URL per line', 'error');
        return;
      }

      batchQueue = lines.map((url, i) => ({ id: i, url, status: 'pending', title: url }));
      renderBatchQueue();
      processBatchQueue();
    });
  }

  function renderBatchQueue() {
    batchQueueList.innerHTML = '';
    batchQueue.forEach((item) => {
      const div = document.createElement('div');
      div.className = 'queue-item';
      let statusColor = 'var(--text-muted)';
      if (item.status === 'downloading') statusColor = 'var(--accent-cyan)';
      if (item.status === 'completed') statusColor = 'var(--accent-emerald)';
      if (item.status === 'error') statusColor = 'var(--accent-rose)';

      div.innerHTML = `
        <div style="max-width:70%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
          <strong>${item.title || item.url}</strong>
        </div>
        <div style="font-weight:700; color:${statusColor}; text-transform:capitalize;">
          ${item.status}
        </div>
      `;
      batchQueueList.appendChild(div);
    });
  }

  async function processBatchQueue() {
    if (isBatchRunning) return;
    isBatchRunning = true;

    for (let i = 0; i < batchQueue.length; i++) {
      const item = batchQueue[i];
      if (item.status === 'completed') continue;

      item.status = 'downloading';
      renderBatchQueue();

      try {
        const resp = await fetch('/api/download', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: item.url, quality_id: 'best' })
        });
        const res = await resp.json();
        if (res.success && res.task_id) {
          await waitForTaskCompletion(res.task_id);
          item.status = 'completed';
        } else {
          item.status = 'error';
        }
      } catch (e) {
        item.status = 'error';
      }
      renderBatchQueue();
    }

    isBatchRunning = false;
    playChime('success');
    showToast('Batch download process completed!', 'success');
    loadLibrary();
  }

  function waitForTaskCompletion(taskId) {
    return new Promise((resolve) => {
      const check = async () => {
        try {
          const resp = await fetch(`/api/tasks/${taskId}`);
          const data = await resp.json();
          if (data.status === 'completed' || data.status === 'error' || data.status === 'cancelled') {
            resolve();
          } else {
            setTimeout(check, 1000);
          }
        } catch (e) {
          resolve();
        }
      };
      check();
    });
  }

  // Media Library
  async function loadLibrary() {
    if (!libraryGrid) return;
    try {
      const query = librarySearch ? librarySearch.value.trim() : '';
      const url = query ? `/api/library?search=${encodeURIComponent(query)}` : '/api/library';
      const resp = await fetch(url);
      const data = await resp.json();

      renderLibraryItems(data.downloads || []);
    } catch (err) {
      console.warn('Library load error', err);
    }
  }

  if (librarySearch) {
    librarySearch.addEventListener('input', () => {
      loadLibrary();
    });
  }

  function renderLibraryItems(items) {
    libraryGrid.innerHTML = '';
    if (items.length === 0) {
      libraryGrid.innerHTML = `
        <div style="grid-column: 1 / -1; text-align:center; padding: 48px 0; color:var(--text-muted);">
          <div style="font-size:2.5rem; margin-bottom:12px;">📁</div>
          <p>No downloaded media found yet.</p>
          <p style="font-size:0.85rem; color:var(--text-dim); margin-top:4px;">Paste any link in the Single tab to start!</p>
        </div>
      `;
      return;
    }

    items.forEach((item) => {
      const card = document.createElement('div');
      card.className = 'media-item-card';

      const thumb = item.thumbnail || '/static/icons/icon-512.png';
      const sizeMb = (item.filesize / (1024 * 1024)).toFixed(1) + ' MB';
      const dateStr = new Date(item.created_at * 1000).toLocaleDateString();

      card.innerHTML = `
        <div class="media-item-thumb">
          <img src="${thumb}" alt="${item.title}" onerror="this.src='/static/icons/icon-512.png'" />
          <div class="media-play-overlay">
            <div class="media-play-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="#fff"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            </div>
          </div>
        </div>
        <div class="media-item-body">
          <div>
            <div class="media-item-title" title="${item.title}">${item.title}</div>
            <div class="media-item-meta">
              <span>${item.platform || 'Web'} • ${item.format.toUpperCase()}</span>
              <span>${sizeMb}</span>
            </div>
          </div>
          <div class="media-item-actions">
            <button class="btn-item-action btn-play-card" title="Play Media">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg> Play
            </button>
            <button class="btn-item-action btn-open-folder" title="Open Folder in Windows Explorer">
              📂 Folder
            </button>
            <button class="btn-item-action btn-download-file" title="Save to Browser Downloads">
              ⬇ Save
            </button>
            <button class="btn-item-action btn-item-delete" title="Delete">
              🗑
            </button>
          </div>
        </div>
      `;

      // Handlers
      card.querySelector('.media-play-overlay').onclick = () => {
        playChime('click');
        openModalPlayer(`/api/stream-file/${item.id}`, item.title);
      };
      card.querySelector('.btn-play-card').onclick = () => {
        playChime('click');
        openModalPlayer(`/api/stream-file/${item.id}`, item.title);
      };
      card.querySelector('.btn-open-folder').onclick = async () => {
        playChime('click');
        const r = await fetch(`/api/library/${item.id}/open-folder`, { method: 'POST' });
        const res = await r.json();
        if (res.success) {
          showToast('Opened in Windows Explorer', 'success');
        } else {
          showToast('Could not open folder: ' + res.error, 'error');
        }
      };
      card.querySelector('.btn-download-file').onclick = () => {
        playChime('click');
        triggerBrowserFileSave(`/api/stream-file/${item.id}`, item.filename);
      };
      card.querySelector('.btn-item-delete').onclick = async () => {
        playChime('click');
        if (confirm(`Delete "${item.title}"?`)) {
          await fetch(`/api/library/${item.id}`, { method: 'DELETE' });
          showToast('Deleted', 'info');
          loadLibrary();
        }
      };

      libraryGrid.appendChild(card);
    });
  }

  // Modal Video Player
  const modalOverlay = document.getElementById('modal-player');
  const modalVideoPlayer = document.getElementById('modal-video-player');
  const modalTitle = document.getElementById('modal-title');
  const btnModalClose = document.getElementById('btn-modal-close');

  function openModalPlayer(streamUrl, title) {
    modalTitle.textContent = title || 'Media Player';
    modalVideoPlayer.src = streamUrl;
    modalOverlay.style.display = 'flex';
    modalVideoPlayer.play().catch(() => {});
  }

  function closeModalPlayer() {
    modalVideoPlayer.pause();
    modalVideoPlayer.src = '';
    modalOverlay.style.display = 'none';
  }

  if (btnModalClose) {
    btnModalClose.onclick = closeModalPlayer;
  }
  if (modalOverlay) {
    modalOverlay.onclick = (e) => {
      if (e.target === modalOverlay) closeModalPlayer();
    };
  }

  // PWA Service Worker Registration & Install Prompt
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js').then((reg) => {
        console.log('OmniDownloader Service Worker registered: ', reg.scope);
      }).catch((err) => {
        console.warn('SW registration failed: ', err);
      });
    });
  }

  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredInstallPrompt = e;
    if (btnInstall) {
      btnInstall.style.display = 'inline-flex';
    }
  });

  if (btnInstall) {
    btnInstall.addEventListener('click', async () => {
      playChime('click');
      if (deferredInstallPrompt) {
        deferredInstallPrompt.prompt();
        const choice = await deferredInstallPrompt.userChoice;
        if (choice.outcome === 'accepted') {
          showToast('App installed to your desktop!', 'success');
          btnInstall.style.display = 'none';
        }
        deferredInstallPrompt = null;
      } else {
        showToast('App is ready! You can also install via browser URL bar (➕).', 'info');
      }
    });
  }

  // Settings & Storage Location Manager
  let appConfig = null;
  let appPresets = {};

  const currentDownloadDirEl = document.getElementById('current-download-dir');
  const modalSettings = document.getElementById('modal-settings');
  const btnSettings = document.getElementById('btn-settings');
  const btnQuickChangeFolder = document.getElementById('btn-quick-change-folder');
  const btnSettingsClose = document.getElementById('btn-settings-close');
  const settingDownloadDir = document.getElementById('setting-download-dir');
  const settingTriggerBrowser = document.getElementById('setting-trigger-browser');
  const btnBrowseFolder = document.getElementById('btn-browse-folder');
  const btnSaveSettings = document.getElementById('btn-save-settings');
  const btnOpenActiveFolder = document.getElementById('btn-open-active-folder');
  const btnSettingsOpenFolder = document.getElementById('btn-settings-open-folder');

  async function loadAppConfig() {
    try {
      const resp = await fetch('/api/config');
      const data = await resp.json();
      appConfig = data.config || {};
      appPresets = data.presets || {};

      if (currentDownloadDirEl) {
        currentDownloadDirEl.textContent = appConfig.download_dir || 'Default Folder';
        currentDownloadDirEl.title = appConfig.download_dir || '';
      }
      if (settingDownloadDir) {
        settingDownloadDir.value = appConfig.download_dir || '';
      }
      if (settingTriggerBrowser) {
        settingTriggerBrowser.checked = !!appConfig.trigger_browser_download;
      }
      const checkBrowser = document.getElementById('check-browser-download');
      if (checkBrowser && appConfig.trigger_browser_download !== undefined) {
        checkBrowser.checked = !!appConfig.trigger_browser_download;
      }

      // Render drive buttons
      const drivesContainer = document.getElementById('preset-drives');
      if (drivesContainer && appPresets.drives && Array.isArray(appPresets.drives)) {
        drivesContainer.innerHTML = '';
        appPresets.drives.forEach((drv) => {
          const pill = document.createElement('button');
          pill.className = 'btn-preset-pill';
          pill.textContent = `💾 Drive ${drv}`;
          pill.onclick = () => {
            playChime('click');
            settingDownloadDir.value = drv;
            showToast(`Selected drive: ${drv}`, 'info');
          };
          drivesContainer.appendChild(pill);
        });
      }
    } catch (e) {
      console.warn('Failed to load config:', e);
    }
  }

  function openSettingsModal() {
    playChime('click');
    if (settingDownloadDir && appConfig) {
      settingDownloadDir.value = appConfig.download_dir || '';
    }
    if (settingTriggerBrowser && appConfig) {
      settingTriggerBrowser.checked = !!appConfig.trigger_browser_download;
    }
    if (modalSettings) modalSettings.style.display = 'flex';
  }

  function closeSettingsModal() {
    if (modalSettings) modalSettings.style.display = 'none';
  }

  if (btnSettings) btnSettings.onclick = openSettingsModal;
  if (btnQuickChangeFolder) btnQuickChangeFolder.onclick = openSettingsModal;
  if (btnSettingsClose) btnSettingsClose.onclick = closeSettingsModal;

  if (modalSettings) {
    modalSettings.onclick = (e) => {
      if (e.target === modalSettings) closeSettingsModal();
    };
  }

  // Open active folder in Windows Explorer
  async function triggerOpenFolder(folderPath = null) {
    playChime('click');
    try {
      await fetch('/api/config/open-folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder_path: folderPath })
      });
      showToast('Opened in Windows Explorer', 'success');
    } catch (e) {
      showToast('Failed to open folder: ' + e.message, 'error');
    }
  }

  if (btnOpenActiveFolder) btnOpenActiveFolder.onclick = () => triggerOpenFolder();
  if (btnSettingsOpenFolder) btnSettingsOpenFolder.onclick = () => triggerOpenFolder(settingDownloadDir?.value);

  // Browse PC Folder Dialog
  if (btnBrowseFolder) {
    btnBrowseFolder.onclick = async () => {
      playChime('click');
      const originalText = btnBrowseFolder.innerHTML;
      btnBrowseFolder.disabled = true;
      btnBrowseFolder.innerHTML = '⏳ Picking...';
      showToast('Opening folder browser... (Check taskbar if window appears behind)', 'info');

      try {
        const resp = await fetch('/api/config/pick-folder', { method: 'POST' });
        const res = await resp.json();
        btnBrowseFolder.disabled = false;
        btnBrowseFolder.innerHTML = originalText;

        if (res.success && res.selected_path) {
          settingDownloadDir.value = res.selected_path;
          if (currentDownloadDirEl) {
            currentDownloadDirEl.textContent = res.selected_path;
            currentDownloadDirEl.title = res.selected_path;
          }
          if (res.config) appConfig = res.config;
          showToast(`Default folder updated: ${res.selected_path}`, 'success');
        } else if (!res.cancelled) {
          showToast('Folder picker: ' + (res.error || 'Selection cancelled'), 'info');
        }
      } catch (e) {
        btnBrowseFolder.disabled = false;
        btnBrowseFolder.innerHTML = originalText;
        showToast('Error opening folder picker: ' + e.message, 'error');
      }
    };
  }

  // Preset folder pills
  document.querySelectorAll('.btn-preset-pill').forEach((btn) => {
    btn.onclick = () => {
      playChime('click');
      const key = btn.getAttribute('data-preset');
      if (appPresets[key]) {
        settingDownloadDir.value = appPresets[key];
        showToast(`Selected preset: ${btn.textContent}`, 'info');
      }
    };
  });

  // Save Settings
  if (btnSaveSettings) {
    btnSaveSettings.onclick = async () => {
      playChime('click');
      const dir = settingDownloadDir.value.trim();
      if (!dir) {
        showToast('Please provide a valid directory path', 'error');
        return;
      }

      btnSaveSettings.disabled = true;
      btnSaveSettings.textContent = 'Saving...';

      try {
        const resp = await fetch('/api/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            download_dir: dir,
            trigger_browser_download: settingTriggerBrowser ? settingTriggerBrowser.checked : true
          })
        });

        const res = await resp.json();
        btnSaveSettings.disabled = false;
        btnSaveSettings.textContent = 'Save Preferences';

        if (res.success && res.config) {
          appConfig = res.config;
          if (currentDownloadDirEl) {
            currentDownloadDirEl.textContent = appConfig.download_dir;
            currentDownloadDirEl.title = appConfig.download_dir;
          }
          const checkBrowser = document.getElementById('check-browser-download');
          if (checkBrowser) {
            checkBrowser.checked = !!appConfig.trigger_browser_download;
          }
          closeSettingsModal();
          showToast('Preferences saved successfully!', 'success');
        } else {
          showToast(res.detail || 'Failed to save preferences', 'error');
        }
      } catch (e) {
        btnSaveSettings.disabled = false;
        btnSaveSettings.textContent = 'Save Preferences';
        showToast('Save error: ' + e.message, 'error');
      }
    };
  }

  // URL Query Parameters Handling (Share Target & Bookmarklet support)
  window.addEventListener('DOMContentLoaded', () => {
    loadAppConfig();
    const params = new URLSearchParams(window.location.search);
    const sharedUrl = params.get('url') || params.get('text');
    if (sharedUrl) {
      // Find URL inside text if passed from Android share target
      const match = sharedUrl.match(/https?:\/\/[^\s]+/);
      const target = match ? match[0] : sharedUrl;
      searchInput.value = target;
      platformBadge.textContent = detectPlatformName(target);
      analyzeUrl(target);
    }
    const tabParam = params.get('tab');
    if (tabParam) {
      const tabBtn = document.querySelector(`.tab-btn[data-tab="${tabParam}"]`);
      if (tabBtn) tabBtn.click();
    }
  });

})();
