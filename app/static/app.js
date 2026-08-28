// NoteFlow Web Client

document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const micButton = document.getElementById('mic-button');
  const micGlowWrapper = document.getElementById('mic-glow-wrapper');
  const micIconInner = document.getElementById('mic-icon-inner');
  const stopIconInner = document.getElementById('stop-icon-inner');
  const statusChip = document.getElementById('status-chip');
  const statusLabel = document.getElementById('status-label');
  const recordHint = document.getElementById('record-hint');
  const recordingMeta = document.getElementById('recording-meta');
  const recordingTimer = document.getElementById('recording-timer');
  
  const resultsArea = document.getElementById('results-area');
  const transcriptText = document.getElementById('transcript-text');
  const confirmationText = document.getElementById('confirmation-text');
  const audioPlayerWrapper = document.getElementById('audio-player-wrapper');
  const replayButton = document.getElementById('replay-button');
  const confirmationAudio = document.getElementById('confirmation-audio');

  const toggleTextBtn = document.getElementById('toggle-text-btn');
  const textInputForm = document.getElementById('text-input-form');
  const typedNoteInput = document.getElementById('typed-note-input');
  const sendTextBtn = document.getElementById('send-text-btn');

  // State
  let mediaRecorder = null;
  let audioChunks = [];
  let recordingStartTime = 0;
  let timerInterval = null;
  let isRecording = false;
  let isProcessing = false;

  // Toggle Typed Note Form
  toggleTextBtn.addEventListener('click', () => {
    const isHidden = textInputForm.classList.contains('hidden');
    if (isHidden) {
      textInputForm.classList.remove('hidden');
      toggleTextBtn.classList.add('open');
      typedNoteInput.focus();
    } else {
      textInputForm.classList.add('hidden');
      toggleTextBtn.classList.remove('open');
    }
  });

  // Handle Typed Note Submit
  textInputForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = typedNoteInput.value.trim();
    if (!text || isProcessing) return;

    typedNoteInput.value = '';
    const formData = new FormData();
    formData.append('text', text);

    await submitNote(formData, text);
  });

  // Handle Mic Click
  micButton.addEventListener('click', async () => {
    if (isProcessing) return;

    if (!isRecording) {
      await startRecording();
    } else {
      stopRecording();
    }
  });

  // Replay Audio
  replayButton.addEventListener('click', () => {
    if (confirmationAudio.src) {
      confirmationAudio.currentTime = 0;
      confirmationAudio.play().catch(err => console.warn('Audio play prevented:', err));
    }
  });

  async function startRecording() {
    try {
      audioChunks = [];
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      const options = { mimeType: 'audio/webm;codecs=opus' };
      if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
        mediaRecorder = new MediaRecorder(stream, options);
      } else if (MediaRecorder.isTypeSupported('audio/webm')) {
        mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
        mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/mp4' });
      } else {
        mediaRecorder = new MediaRecorder(stream);
      }

      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunks.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        // Stop all audio tracks to release microphone
        stream.getTracks().forEach(track => track.stop());
        
        if (audioChunks.length === 0) return;
        const mimeType = mediaRecorder.mimeType || 'audio/webm';
        const audioBlob = new Blob(audioChunks, { type: mimeType });
        
        const formData = new FormData();
        const extension = mimeType.includes('mp4') ? 'mp4' : 'webm';
        formData.append('audio', audioBlob, `note.${extension}`);

        await submitNote(formData);
      };

      mediaRecorder.start();
      isRecording = true;
      updateUIState('recording');

      // Start timer
      recordingStartTime = Date.now();
      updateTimerDisplay();
      timerInterval = setInterval(updateTimerDisplay, 1000);

    } catch (err) {
      console.error('Microphone access error:', err);
      updateUIState('error', 'Microphone access denied or not available.');
    }
  }

  function stopRecording() {
    if (mediaRecorder && isRecording) {
      clearInterval(timerInterval);
      mediaRecorder.stop();
      isRecording = false;
      updateUIState('processing');
    }
  }

  function updateTimerDisplay() {
    const elapsedSeconds = Math.floor((Date.now() - recordingStartTime) / 1000);
    const mins = String(Math.floor(elapsedSeconds / 60)).padStart(2, '0');
    const secs = String(elapsedSeconds % 60).padStart(2, '0');
    recordingTimer.textContent = `${mins}:${secs}`;
  }

  async function submitNote(formData, directText = null) {
    isProcessing = true;
    updateUIState('processing');

    try {
      const response = await fetch('/api/voice-note', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || `Server error (${response.status})`);
      }

      // Display results
      transcriptText.textContent = `"${data.transcript}"`;
      confirmationText.textContent = data.confirmation_text;
      resultsArea.classList.remove('hidden');

      // Play audio if available
      if (data.confirmation_audio_url) {
        confirmationAudio.src = `${data.confirmation_audio_url}?t=${Date.now()}`;
        audioPlayerWrapper.classList.remove('hidden');
        confirmationAudio.play().catch(err => {
          console.log('Autoplay deferred by browser policy:', err);
        });
      } else {
        audioPlayerWrapper.classList.add('hidden');
      }

      updateUIState('success');
    } catch (err) {
      console.error('Failed to process note:', err);
      updateUIState('error', err.message || 'Failed to file note in Notion.');
    } finally {
      isProcessing = false;
    }
  }

  function updateUIState(state, message = '') {
    // Reset base classes
    statusChip.className = 'status-chip';
    micGlowWrapper.className = 'mic-glow-wrapper';
    micButton.disabled = false;
    sendTextBtn.disabled = false;

    if (state === 'idle') {
      statusLabel.textContent = 'Ready to record';
      recordHint.textContent = 'Click the microphone to start speaking';
      micIconInner.classList.remove('hidden');
      stopIconInner.classList.add('hidden');
      recordingMeta.classList.add('hidden');
    } else if (state === 'recording') {
      statusChip.classList.add('recording');
      micGlowWrapper.classList.add('recording');
      statusLabel.textContent = 'Listening...';
      recordHint.textContent = 'Click again when finished speaking';
      micIconInner.classList.add('hidden');
      stopIconInner.classList.remove('hidden');
      recordingMeta.classList.remove('hidden');
    } else if (state === 'processing') {
      statusChip.classList.add('processing');
      statusLabel.textContent = 'Transcribing & filing in Notion...';
      recordHint.textContent = 'Agent is querying Notion and filing note...';
      micIconInner.classList.remove('hidden');
      stopIconInner.classList.add('hidden');
      recordingMeta.classList.add('hidden');
      micButton.disabled = true;
      sendTextBtn.disabled = true;
    } else if (state === 'success') {
      statusLabel.textContent = 'Filed in Notion';
      recordHint.textContent = 'Click mic to record another thought';
      micIconInner.classList.remove('hidden');
      stopIconInner.classList.add('hidden');
      recordingMeta.classList.add('hidden');
    } else if (state === 'error') {
      statusChip.classList.add('error');
      statusLabel.textContent = 'Error';
      recordHint.textContent = message || 'An error occurred. Please try again.';
      micIconInner.classList.remove('hidden');
      stopIconInner.classList.add('hidden');
      recordingMeta.classList.add('hidden');
    }
  }
});
