
document.addEventListener('DOMContentLoaded', () => {
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

  let isListening = false;
  let isTTSMuted = false;
  let recognition = null;
  let synth = window.speechSynthesis || null;

  const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition || null;
  if (SpeechRec) {
    recognition = new SpeechRec();
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
      let interim = '';
      let final = '';
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) final += event.results[i][0].transcript;
        else interim += event.results[i][0].transcript;
      }
      if (final) {
        userTranscript.textContent = final;
        handleUserQuery(final);
      } else if (interim) {
        userTranscript.textContent = interim + '...';
      }
    };

    recognition.onerror = () => {
      resetVoiceState();
      statusText.textContent = 'Microphone ready (click to speak)';
    };

    recognition.onend = () => {
      resetVoiceState();
    };
  } else {
    btnVoiceLabel.textContent = 'Click to Speak';
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

  function speakResponse(text) {
    if (!synth || isTTSMuted) return;
    synth.cancel();
    const cleanText = text.replace(/[*_#`$]/g, '');
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1.05;
    const voices = synth.getVoices();
    const preferred = voices.find(v => (v.name.includes('Natural') || v.name.includes('Google') || v.name.includes('Samantha') || v.name.includes('Ava') || v.name.includes('Zira')) && v.lang.startsWith('en'));
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
      if (response.ok) {
        const data = await response.json();
        lunaTranscript.textContent = data.reply;
        speakResponse(data.reply);
        if (data.expenses) {
          renderExpenses(data.expenses, data.total);
        } else {
          loadExpenses();
        }
        return;
      }
    } catch (err) {}

    processClientLunaTurn(query);
  }

  function processClientLunaTurn(query) {
    const raw = query.toLowerCase().trim();
    let expenses = getStoredExpenses();
    let reply = '';

    // Total / Balance query
    if (/(total|balance|how much|sum|spending)/i.test(raw)) {
      const sum = expenses.reduce((a, b) => a + Number(b.amount || 0), 0);
      reply = `You have recorded ${expenses.length} expense${expenses.length === 1 ? '' : 's'} totaling $${sum.toFixed(2)}.`;
    }
    // Clear / Reset query
    else if (/(clear all|delete all|reset|remove all)/i.test(raw)) {
      expenses = [];
      saveStoredExpenses(expenses);
      reply = 'All recorded expenses have been cleared.';
      renderExpenses(expenses);
    }
    // List expenses query
    else if (/(list|show|what are my expenses|all expenses|transactions|history)/i.test(raw)) {
      if (expenses.length === 0) {
        reply = 'You have no recorded expenses.';
      } else {
        const top = expenses.slice(0, 3).map(e => `${e.name} ($${Number(e.amount).toFixed(2)})`).join(', ');
        const sum = expenses.reduce((a, b) => a + Number(b.amount || 0), 0);
        reply = `Here are your recent expenses: ${top}. Your overall total is $${sum.toFixed(2)}.`;
      }
    }
    // Record / Log Expense (matches: "log and expense of $20", "log an expense of $20", "add $45 for lunch", "$20 for coffee", "spent 30 dollars on gas", etc.)
    else if (
      /(log|add|spent|spend|bought|buy|record|charge|charged|paid|pay|purchase|new expense)/i.test(raw) ||
      /expense\s+of/i.test(raw) ||
      /expense/i.test(raw) ||
      /\$\s*\d+/.test(raw) ||
      /\d+\s*(\$|dollars?|bucks?)/i.test(raw)
    ) {
      let amount = 20.0;
      const mDollar = raw.match(/\$\s*(\d+(?:\.\d{1,2})?)/);
      const mAfter = raw.match(/(\d+(?:\.\d{1,2})?)\s*(?:\$|dollars?|bucks?)/i);
      const mAnyNum = raw.match(/(\d+(?:\.\d{1,2})?)/);

      if (mDollar && mDollar[1]) amount = parseFloat(mDollar[1]);
      else if (mAfter && mAfter[1]) amount = parseFloat(mAfter[1]);
      else if (mAnyNum && mAnyNum[1]) amount = parseFloat(mAnyNum[1]);

      let category = 'other';
      let name = 'Expense';

      if (/(lunch|dinner|breakfast|food|coffee|starbucks|cafe|drinks?|beer|wine|burger|pizza|groceries|snack|restaurant|meal|meals)/i.test(raw)) {
        category = 'meals';
        if (/coffee|starbucks|cafe/i.test(raw)) name = 'Coffee & Cafe';
        else if (/lunch/i.test(raw)) name = 'Lunch';
        else if (/dinner/i.test(raw)) name = 'Dinner';
        else if (/breakfast/i.test(raw)) name = 'Breakfast';
        else name = 'Meals & Food';
      } else if (/(uber|taxi|cab|flight|tickets?|train|subway|metro|gas|fuel|parking|commute|transit|travel)/i.test(raw)) {
        category = 'travel';
        if (/uber/i.test(raw)) name = 'Uber';
        else if (/flight|airline/i.test(raw)) name = 'Flight Ticket';
        else if (/taxi|cab/i.test(raw)) name = 'Taxi Fare';
        else if (/gas|fuel/i.test(raw)) name = 'Fuel';
        else name = 'Travel & Transit';
      } else if (/(hotel|airbnb|stay|room|motel|lodging|resort)/i.test(raw)) {
        category = 'lodging';
        name = 'Hotel Stay';
      } else if (/(movie|cinema|concert|game|gaming|spotify|netflix|entertainment)/i.test(raw)) {
        category = 'entertainment';
        name = 'Entertainment';
      } else if (/(course|training|workshop|seminar|bootcamp|certification)/i.test(raw)) {
        category = 'training';
        name = 'Professional Training';
      } else if (/(book|books|tuition|study|education|class)/i.test(raw)) {
        category = 'education';
        name = 'Books & Study';
      } else if (/(office|supplies|server|cloud|aws|hosting|monitor|laptop|computer|software|subscription|desk|paper)/i.test(raw)) {
        category = 'office_supplies';
        name = 'Office & Cloud';
      } else if (/(gift|present|flowers)/i.test(raw)) {
        category = 'gifts';
        name = 'Gift';
      } else {
        const forMatch = raw.match(/(?:for|on)\s+([a-zA-Z\s]{2,20})/i);
        if (forMatch && forMatch[1] && !/(an|and|the|a)/i.test(forMatch[1].trim())) {
          name = forMatch[1].trim().replace(/\w/g, l => l.toUpperCase());
        } else {
          name = 'Expense';
        }
      }

      const newExpense = {
        id: Date.now().toString(),
        name: name,
        amount: amount,
        category: category,
        created_at: new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
      };

      expenses.unshift(newExpense);
      saveStoredExpenses(expenses);
      reply = `I've recorded that for you: ${name} for $${amount.toFixed(2)} under ${category}.`;
      renderExpenses(expenses);
    } else {
      reply = `Hello! I'm Luna. I heard "${query}". You can ask me to log purchases (e.g. "Add $20 for lunch"), check your budget, or list your expenses!`;
    }

    lunaTranscript.textContent = reply;
    speakResponse(reply);
  }

  function getStoredExpenses() {
    const data = localStorage.getItem('luna_expenses');
    if (!data) {
      const defaults = [
        { id: '1', name: 'Team Lunch', amount: 42.50, category: 'meals', created_at: 'Nov 20, 2026' },
        { id: '2', name: 'Uber to Airport', amount: 34.00, category: 'travel', created_at: 'Nov 19, 2026' },
        { id: '3', name: 'Cloud Infrastructure', amount: 89.99, category: 'office_supplies', created_at: 'Nov 18, 2026' }
      ];
      localStorage.setItem('luna_expenses', JSON.stringify(defaults));
      return defaults;
    }
    try {
      const parsed = JSON.parse(data);
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      const defaults = [
        { id: '1', name: 'Team Lunch', amount: 42.50, category: 'meals', created_at: 'Nov 20, 2026' },
        { id: '2', name: 'Uber to Airport', amount: 34.00, category: 'travel', created_at: 'Nov 19, 2026' },
        { id: '3', name: 'Cloud Infrastructure', amount: 89.99, category: 'office_supplies', created_at: 'Nov 18, 2026' }
      ];
      localStorage.setItem('luna_expenses', JSON.stringify(defaults));
      return defaults;
    } catch { return []; }
  }

  function saveStoredExpenses(list) {
    localStorage.setItem('luna_expenses', JSON.stringify(list));
  }

  function renderExpenses(list, totalValue) {
    if (!list) list = [];
    const total = totalValue !== undefined ? totalValue : list.reduce((a, b) => a + Number(b.amount || 0), 0);
    totalAmount.textContent = `$${total.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    expenseCount.textContent = `${list.length} transaction${list.length === 1 ? '' : 's'} recorded`;

    expensesTbody.innerHTML = '';
    if (list.length === 0) {
      expensesTbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 24px; color: var(--text-dim);">No recorded expenses. Speak to Luna or type above to add one!</td></tr>';
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

    document.querySelectorAll('.btn-del').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.getAttribute('data-id');
        deleteExpense(id);
      });
    });
  }

  function deleteExpense(id) {
    let list = getStoredExpenses();
    list = list.filter(x => x.id !== id);
    saveStoredExpenses(list);
    renderExpenses(list);
  }

  async function loadExpenses() {
    try {
      const res = await fetch('/api/expenses');
      if (res.ok) {
        const data = await res.json();
        renderExpenses(data.expenses, data.total);
        return;
      }
    } catch {}
    renderExpenses(getStoredExpenses());
  }

  btnVoice.addEventListener('click', () => {
    if (!recognition) return;
    if (isListening) {
      recognition.stop();
    } else {
      try { recognition.start(); } catch {}
    }
  });

  coreOrb.addEventListener('click', () => {
    btnVoice.click();
  });

  btnMuteTTS.addEventListener('click', () => {
    isTTSMuted = !isTTSMuted;
    if (isTTSMuted) {
      muteIcon.innerHTML = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><line x1="23" y1="9" x2="17" y2="15"></line><line x1="17" y1="9" x2="23" y2="15"></line></svg>';
      btnMuteTTS.title = 'Unmute Luna Voice';
      if (synth) synth.cancel();
    } else {
      muteIcon.innerHTML = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>';
      btnMuteTTS.title = 'Mute Luna Voice';
    }
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

  loadExpenses();
});
