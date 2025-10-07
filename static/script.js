document.addEventListener('DOMContentLoaded', () => {
  const chatBox = document.getElementById('chatContainer');
  const form = document.getElementById('sendForm');
  const input = document.getElementById('userInput');
  const fileInput = document.getElementById('fileInput');
  const uploadBtn = document.getElementById('uploadBtn');
  const micBtn = document.getElementById('micBtn');
  const speakBtn = document.getElementById('speakBtn');
  const settingsBtn = document.getElementById('settingsBtn');
  const chatSearch = document.getElementById('chatSearch');
  const searchInput = document.getElementById('searchInput');
  const exportBtn = document.getElementById('exportBtn');
  const settingsModal = document.getElementById('settingsModal');
  const closeModal = document.getElementById('closeModal');
  const voiceSelect = document.getElementById('voiceSelect');
  const themeToggle = document.getElementById('themeToggle');
  const chatId = window.location.href.split('chat_id=')[1] || '';

  // Dark mode
  if (localStorage.getItem('darkMode') === 'true') {
    document.body.classList.add('dark-mode');
    themeToggle.textContent = '🌚';
  }
  themeToggle.onclick = () => {
    document.body.classList.toggle('dark-mode');
    const dark = document.body.classList.contains('dark-mode');
    localStorage.setItem('darkMode', dark);
    themeToggle.textContent = dark ? '🌚' : '🌞';
  };

  // Submit form
  form.addEventListener('submit', async e => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message && !fileInput.files.length) return;

    const msgDiv = document.createElement('div');
    msgDiv.className = 'message user';
    msgDiv.innerHTML = `<strong>🧑 You:</strong> <span>${message}</span>`;
    chatBox.appendChild(msgDiv);
    input.value = '';
    chatBox.scrollTop = chatBox.scrollHeight;

    const formData = new FormData();
    formData.append('message', message);
    if (fileInput.files.length) {
      formData.append('file', fileInput.files[0]);
    }

    try {
      const res = await fetch(`/send_message/${chatId}`, {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      const botDiv = document.createElement('div');
      botDiv.className = 'message bot typing';
      botDiv.innerHTML = `<strong>🤖 Mirai:</strong> <span></span>`;
      chatBox.appendChild(botDiv);
      const span = botDiv.querySelector('span');
      let i = 0;
      const interval = setInterval(() => {
        if (i < data.reply.length) {
          span.textContent += data.reply.charAt(i++);
          chatBox.scrollTop = chatBox.scrollHeight;
        } else clearInterval(interval);
      }, 20);
    } catch {
      alert("⚠️ Error sending message.");
    }

    fileInput.value = '';
  });

  // Upload file
  uploadBtn.onclick = () => fileInput.click();

  // Mic
  let recognition;
  micBtn.onclick = () => {
    if (!recognition) {
      recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
      recognition.lang = 'en-US';
      recognition.start();
      micBtn.textContent = '🛑';
      recognition.onresult = e => {
        input.value = Array.from(e.results).map(r => r[0].transcript).join('');
      };
      recognition.onerror = () => alert('🎙️ Speech error');
      recognition.onend = () => {
        micBtn.textContent = '🎤';
        recognition = null;
      };
    } else {
      recognition.stop();
      recognition = null;
      micBtn.textContent = '🎤';
    }
  };

  // TTS
  let selectedVoice = null;
  const loadVoices = () => {
    const voices = speechSynthesis.getVoices();
    voiceSelect.innerHTML = '';
    voices.forEach(v => {
      const opt = document.createElement('option');
      opt.value = v.name;
      opt.textContent = `${v.name} (${v.lang})`;
      voiceSelect.appendChild(opt);
    });
    const saved = localStorage.getItem('miraiVoice');
    if (saved) {
      voiceSelect.value = saved;
      selectedVoice = voices.find(v => v.name === saved);
    }
  };
  speechSynthesis.onvoiceschanged = loadVoices;
  loadVoices();

  voiceSelect.onchange = () => {
    localStorage.setItem('miraiVoice', voiceSelect.value);
    selectedVoice = speechSynthesis.getVoices().find(v => v.name === voiceSelect.value);
  };

  settingsBtn.onclick = () => settingsModal.style.display = 'block';
  closeModal.onclick = () => settingsModal.style.display = 'none';
  window.onclick = e => { if (e.target === settingsModal) settingsModal.style.display = 'none'; };

  speakBtn.onclick = () => {
    const bots = document.querySelectorAll('.message.bot span');
    if (bots.length) {
      const msg = bots[bots.length - 1].textContent;
      const utterance = new SpeechSynthesisUtterance(msg);
      if (selectedVoice) utterance.voice = selectedVoice;
      speechSynthesis.cancel();
      speechSynthesis.speak(utterance);
    }
  };

  searchInput.oninput = () => {
    const q = searchInput.value.toLowerCase();
    document.querySelectorAll('.message').forEach(m => {
      m.style.display = m.innerText.toLowerCase().includes(q) ? '' : 'none';
    });
  };

  chatSearch.oninput = () => {
    const q = chatSearch.value.toLowerCase();
    document.querySelectorAll('.chat-form').forEach(f => {
      const name = f.querySelector('.chat-name').textContent.toLowerCase();
      f.style.display = name.includes(q) ? '' : 'none';
    });
  };

  exportBtn.onclick = () => {
    const messages = [...document.querySelectorAll('.message')].map(m => m.innerText.trim());
    const format = prompt("Export as: txt / json / md")?.toLowerCase();
    if (!format) return;
    let content = "", type = "text/plain", ext = "txt";
    if (format === "json") {
      content = JSON.stringify(messages, null, 2);
      type = "application/json";
      ext = "json";
    } else if (format === "md") {
      content = messages.map(m => `- ${m}`).join("\n");
      ext = "md";
    } else {
      content = messages.join("\n");
    }
    const blob = new Blob([content], { type });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `mirai_chat.${ext}`;
    a.click();
  };
});
