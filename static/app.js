/**
 * Luna AI Voice Agent - Client Application Logic
 * Integrates Web Speech API (STT & TTS), Orb visualizer, and LangGraph Backend
 */

document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const statusIndicator = document.getElementById('statusIndicator');
  const statusText = document.getElementById('statusText');
  const coreOrb = document.getElementById('coreOrb');
  const btnVoice = document.getElementById('btnVoice');
  const btnVoiceLabel = document.getElementById('btnVoiceLabel');
  const btnMuteTTS = document.getElementById('btnMuteTTS');
  const muteIcon = document.getElementById('muteIcon');
  const userTranscript = document.getElementById('userTranscript');
  const lunaTranscript = document.getElementById('lunaTranscript');
  const textInputForm = document.getElementById('textInputForm');
  const textInput = document.getElementById('textInput');
  const totalAmount = document.getElementById('totalAmount');
  const expenseCount = document.getElementById('expenseCount');
  const expensesTbody = document.getElementById('expensesTbody');
  const btnRefresh = document.getElementById('btnRefresh');
  const promptChips = document.querySelectorAll('.chip');

  // State
  let isListening = false;
  let isTTSMuted = false;
  let recognition = null;
  let synth = window.speechSynthesis || null;

  // Initialize Web Speech Recognition
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition || null;
  if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
      isListening = true;
      setOrbState('listening');
      statusText.textContent = 'Listening to your voice...';
      btnVoice.classList.add('active');
      btnVoiceLabel.textContent = 'Stop Listening';
    };

    recognition.onresult = (event) => {
      let interimTranscript = '';
      let finalTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          finalTranscript += event.results[i][0].transcript;
        } else {
          interimTranscript += event.results[i][0].transcript;
        }
      }

      if (finalTranscript) {
        userTranscript.textContent = finalTranscript;
        handleUserQuery(finalTranscript);
      } else if (interimTranscript) {
        userTranscript.textContent = interimTranscript + '...';
      }
    };

    recognition.onerror = (event) => {
      console.warn('Speech recognition event:', event.error);
      resetVoiceState();
      statusText.textContent = 'Microphone ready (click to speak)';
    };

    recognition.onend = () => {
      resetVoiceState();
    };
  } else {
    btnVoiceLabel.textContent = 'Speech Mic Unsupported';
    statusText.textContent = 'Use text input or supported browser';
  }

  function resetVoiceState() {
    isListening = false;
    btnVoice.classList.remove('active');
    btnVoiceLabel.textContent = 'Click to Speak';
    setOrbState('idle');
  }

  function setOrbState(state) {
    coreOrb.classList.remove('listening', 'speaking');
    statusIndicator.classList.remove('listening', 'speaking');

    if (state === 'listening') {
      coreOrb.classList.add('listening');
      statusIndicator.classList.add('listening');
    } else if (state === 'speaking') {
      coreOrb.classList.add('speaking');
      statusIndicator.classList.add('speaking');
    }
  }

  // Speak Response via Speech Synthesis
  function speakResponse(text) {
    if (!synth || isTTSMuted) return;

    // Stop existing speech
    synth.cancel();

    // Clean text for speech
    const cleanText = text.replace(/[*_#`]/g, '');
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1.05;
    utterance.pitch = 1.0;

    // Pick a natural voice if available
    const voices = synth.getVoices();
    const preferred = voices.find(v => (v.name.includes('Natural') || v.name.includes('Google') || v.name.includes('Samantha') || v.name.includes('Ava')) && v.lang.startsWith('en'));
    if (preferred) utterance.voice = preferred;

    utterance.onstart = () => {
      setOrbState('speaking');
      statusText.textContent = 'Luna is speaking...';
    };

    utterance.onend = () => {
      setOrbState('idle');
      statusText.textContent = 'Ready for Voice Input';
    };

    utterance.onerror = () => {
      setOrbState('idle');
      statusText.textContent = 'Ready for Voice Input';
    };

    synth.speak(utterance);
  }

  // Handle Query (Send to backend or execute client fallback)
  async function handleUserQuery(query) {
    if (!query || !query.trim()) return;
    
    setOrbState('listening');
    statusText.textContent = 'Processing request...';
    userTranscript.textContent = query;

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: query })
      });

      if (!response.ok) throw new Error('API response failed');

      const data = await response.json();
      lunaTranscript.textContent = data.reply;
      speakResponse(data.reply);

      if (data.expenses) {
        renderExpenses(data.expenses, data.total);
      } else {
        loadExpenses();
      }
    } catch (err) {
      console.warn('Backend unavailable, running in client-side Luna mode:', err);
      // Client-side fallback for static deployments (e.g. Vercel)
      processClientFallback(query);
    }
  }

  // Client-Side Fallback for Standalone Web Preview
  function processClientFallback(query) {
    let raw = query.toLowerCase();
    let localExpenses = JSON.parse(localStorage.getItem('luna_expenses') || '[]');
    let reply = "";

    if (raw.includes('total') || raw.includes('balance') || raw.includes('how much')) {
      const sum = localExpenses.reduce((acc, curr) => acc + Number(curr.amount || 0), 0);
      reply = `You have ${localExpenses.length} recorded expenses totaling $${sum.toFixed(2)}.`;
    } else if (raw.includes('add') || raw.includes('spent') || raw.includes('bought')) {
      const match = raw.match(/\$?(\d+(?:\.\d{1,2})?)/);
      const amount = match ? parseFloat(match[1]) : 20.0;
      let name = "Expense";
      let cat = "other";

      if (raw.includes('lunch') || raw.includes('food') || raw.includes('coffee')) {
        name = "Food & Coffee";
        cat = "meals";
      } else if (raw.includes('uber') || raw.includes('taxi') || raw.includes('flight')) {
        name = "Transportation";
        cat = "travel";
      } else if (raw.includes('hotel')) {
        name = "Hotel Stay";
        cat = "lodging";
      }

      const newExpense = {
        id: Date.now().toString(),
        name: name,
        amount: amount,
        category: cat,
        created_at: new Date().toLocaleDateString()
      };
      localExpenses.unshift(newExpense);
      localStorage.setItem('luna_expenses', JSON.stringify(localExpenses));
      reply = `I have logged $${amount.toFixed(2)} for ${name} under ${cat}.`;
      renderExpenses(localExpenses);
    } else {
      reply = `I heard: "${query}". You can ask me to log an expense or check your total balance anytime!`;
    }

    lunaTranscript.textContent = reply;
    speakResponse(reply);
  }

  // Load Expenses from Backend
  async function loadExpenses() {
    try {
      const res = await fetch('/api/expenses');
      if (res.ok) {
        const data = await res.json();
        renderExpenses(data.expenses, data.total);
        return;
      }
    } catch (e) {
      // Load local storage fallback
      const local = JSON.parse(localStorage.getItem('luna_expenses') || '[]');
      if (local.length === 0) {
        const defaults = [
          { id: '1', name: 'Team Lunch', amount: 42.50, category: 'meals', created_at: '2026-11-20' },
          { id: '2', name: 'Uber to Airport', amount: 34.00, category: 'travel', created_at: '2026-11-19' },
          { id: '3', name: 'Cloud Infrastructure', amount: 89.99, category: 'office_supplies', created_at: '2026-11-18' }
        ];
        localStorage.setItem('luna_expenses', JSON.stringify(defaults));
        renderExpenses(defaults);
      } else {
        renderExpenses(local);
      }
    }
  }

  // Render Table
  function renderExpenses(list, totalValue) {
    if (!list) list = [];
    const total = totalValue !== undefined ? totalValue : list.reduce((a, b) => a + Number(b.amount || 0), 0);
    totalAmount.textContent = `$${total.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    expenseCount.textContent = `${list.length} transaction${list.length === 1 ? '' : 's'} recorded`;

    expensesTbody.innerHTML = '';
    if (list.length === 0) {
      expensesTbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding: 24px; color: var(--text-dim);">No expenses recorded yet. Speak to Luna to add one!</td></tr>`;
      return;
    }

    list.forEach(item => {
      const tr = document.createElement('tr');
      const catClass = `cat-${item.category || 'other'}`;
      tr.innerHTML = `
        <td><strong>${item.name || 'Expense'}</strong></td>
        <td><span class="category-tag ${catClass}">${item.category || 'other'}</span></td>
        <td class="expense-amount">$${Number(item.amount).toFixed(2)}</td>
        <td style="color: var(--text-dim); font-size: 0.8rem;">${item.created_at || 'Today'}</td>
        <td>
          <button class="btn-del" data-id="${item.id}" title="Delete expense">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
          </button>
        </td>
      `;
      expensesTbody.appendChild(tr);
    });

    // Attach delete listeners
    document.querySelectorAll('.btn-del').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const id = btn.getAttribute('data-id');
        deleteExpense(id);
      });
    });
  }

  async function deleteExpense(id) {
    try {
      await fetch(`/api/expenses/${id}`, { method: 'DELETE' });
    } catch (e) {
      let local = JSON.parse(localStorage.getItem('luna_expenses') || '[]');
      local = local.filter(x => x.id !== id);
      localStorage.setItem('luna_expenses', JSON.stringify(local));
    }
    loadExpenses();
  }

  // Event Listeners
  btnVoice.addEventListener('click', () => {
    if (!recognition) return;
    if (isListening) {
      recognition.stop();
    } else {
      try {
        recognition.start();
      } catch (err) {
        console.error(err);
      }
    }
  });

  coreOrb.addEventListener('click', () => {
    btnVoice.click();
  });

  btnMuteTTS.addEventListener('click', () => {
    isTTSMuted = !isTTSMuted;
    muteIcon.textContent = isTTSMuted ? '🔇' : '🔊';
    btnMuteTTS.title = isTTSMuted ? 'Unmute Luna Voice' : 'Mute Luna Voice';
    if (isTTSMuted && synth) synth.cancel();
  });

  textInputForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const query = textInput.value.trim();
    if (query) {
      handleUserQuery(query);
      textInput.value = '';
    }
  });

  btnRefresh.addEventListener('click', () => {
    loadExpenses();
  });

  promptChips.forEach(chip => {
    chip.addEventListener('click', () => {
      const q = chip.getAttribute('data-query');
      handleUserQuery(q);
    });
  });

  // Initial Data Load
  loadExpenses();
});
