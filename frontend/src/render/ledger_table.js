// Audit Ledger Table with Filters, Rubber Stamps, and Inline 5-Stage Trace Drawer

export function renderLedgerTable(container, actions, activeFilters = {}, onFilterChange = null) {
  if (!actions) return;

  // Filter items
  const filtered = actions.filter(action => {
    if (activeFilters.search) {
      const q = activeFilters.search.toLowerCase();
      const matchId = action.trigger_event_id.toLowerCase().includes(q);
      const matchCause = action.diagnosed_cause.toLowerCase().includes(q);
      const matchIntervention = action.chosen_intervention.toLowerCase().includes(q);
      const matchMsg = (action.sent_message || '').toLowerCase().includes(q);
      if (!matchId && !matchCause && !matchIntervention && !matchMsg) return false;
    }
    if (activeFilters.cause && activeFilters.cause !== 'all' && action.diagnosed_cause !== activeFilters.cause) return false;
    if (activeFilters.intervention && activeFilters.intervention !== 'all' && action.chosen_intervention !== activeFilters.intervention) return false;
    if (activeFilters.outcome && activeFilters.outcome !== 'all' && action.outcome !== activeFilters.outcome) return false;
    if (activeFilters.channel && activeFilters.channel !== 'all' && action.channel !== activeFilters.channel) return false;
    return true;
  });

  const getStampClass = (outcome) => {
    switch (outcome) {
      case 'recovered': return 'stamp-recovered';
      case 'promise_to_pay': return 'stamp-promise';
      case 'escalated': return 'stamp-escalated';
      case 'stopped': return 'stamp-stopped';
      case 'rejected': return 'stamp-rejected';
      case 'no_response': return 'stamp-no-response';
      default: return 'stamp-no-action';
    }
  };

  const formatStampLabel = (outcome) => {
    if (outcome === 'promise_to_pay') return 'PROMISE TO PAY';
    if (outcome === 'no_action') return 'NO ACTION';
    if (outcome === 'no_response') return 'NO RESPONSE';
    return outcome.toUpperCase();
  };

  const getSourceBadge = (source) => {
    if (source === 'rules') return `<span class="badge-source rules">RULES</span>`;
    if (source === 'llm') return `<span class="badge-source llm">AI</span>`;
    return `<span class="badge-source llm-fallback">FALLBACK</span>`;
  };

  container.innerHTML = `
    <!-- Filter & Search Controls -->
    <div class="filter-bar">
      <div class="filter-controls">
        <input 
          type="text" 
          id="ledger-search" 
          class="search-input" 
          placeholder="🔍 Search ID, cause, text..." 
          value="${activeFilters.search || ''}"
        />
        
        <select id="filter-cause" class="filter-select">
          <option value="all">Cause: All</option>
          <option value="insufficient_funds" ${activeFilters.cause === 'insufficient_funds' ? 'selected' : ''}>insufficient_funds</option>
          <option value="price_shock" ${activeFilters.cause === 'price_shock' ? 'selected' : ''}>price_shock</option>
          <option value="otp_friction" ${activeFilters.cause === 'otp_friction' ? 'selected' : ''}>otp_friction</option>
          <option value="risk_decline" ${activeFilters.cause === 'risk_decline' ? 'selected' : ''}>risk_decline</option>
          <option value="bank_timeout" ${activeFilters.cause === 'bank_timeout' ? 'selected' : ''}>bank_timeout</option>
          <option value="expired_card" ${activeFilters.cause === 'expired_card' ? 'selected' : ''}>expired_card</option>
          <option value="trust_hesitation" ${activeFilters.cause === 'trust_hesitation' ? 'selected' : ''}>trust_hesitation</option>
          <option value="technical_error" ${activeFilters.cause === 'technical_error' ? 'selected' : ''}>technical_error</option>
          <option value="comparison_shopping" ${activeFilters.cause === 'comparison_shopping' ? 'selected' : ''}>comparison_shopping</option>
        </select>

        <select id="filter-intervention" class="filter-select">
          <option value="all">Intervention: All</option>
          <option value="retry_48h" ${activeFilters.intervention === 'retry_48h' ? 'selected' : ''}>retry_48h</option>
          <option value="discount_offer" ${activeFilters.intervention === 'discount_offer' ? 'selected' : ''}>discount_offer</option>
          <option value="resend_otp_simplified" ${activeFilters.intervention === 'resend_otp_simplified' ? 'selected' : ''}>resend_otp_simplified</option>
          <option value="escalate_review" ${activeFilters.intervention === 'escalate_review' ? 'selected' : ''}>escalate_review</option>
          <option value="request_update" ${activeFilters.intervention === 'request_update' ? 'selected' : ''}>request_update</option>
          <option value="trust_signal_message" ${activeFilters.intervention === 'trust_signal_message' ? 'selected' : ''}>trust_signal_message</option>
          <option value="reminder_only" ${activeFilters.intervention === 'reminder_only' ? 'selected' : ''}>reminder_only</option>
          <option value="no_action" ${activeFilters.intervention === 'no_action' ? 'selected' : ''}>no_action</option>
        </select>

        <select id="filter-outcome" class="filter-select">
          <option value="all">Outcome: All</option>
          <option value="recovered" ${activeFilters.outcome === 'recovered' ? 'selected' : ''}>RECOVERED</option>
          <option value="promise_to_pay" ${activeFilters.outcome === 'promise_to_pay' ? 'selected' : ''}>PROMISE TO PAY</option>
          <option value="escalated" ${activeFilters.outcome === 'escalated' ? 'selected' : ''}>ESCALATED</option>
          <option value="stopped" ${activeFilters.outcome === 'stopped' ? 'selected' : ''}>STOPPED</option>
          <option value="no_response" ${activeFilters.outcome === 'no_response' ? 'selected' : ''}>NO RESPONSE</option>
          <option value="no_action" ${activeFilters.outcome === 'no_action' ? 'selected' : ''}>NO ACTION</option>
        </select>
      </div>

      <div class="mono" style="font-size: 11px; color: var(--ink-soft);">
        Showing <strong>${filtered.length}</strong> of ${actions.length} audit entries
      </div>
    </div>

    <!-- Ledger Table -->
    <div class="ledger-container">
      <div class="table-responsive">
        <table class="ledger-table">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Trigger Event</th>
              <th>Diagnosed Cause</th>
              <th>Chosen Policy</th>
              <th>Channel</th>
              <th>Guardrail</th>
              <th style="text-align: center;">Outcome Stamp</th>
              <th style="text-align: right;">Net Recovered</th>
            </tr>
          </thead>
          <tbody>
            ${filtered.length === 0 ? `
              <tr>
                <td colspan="8" style="text-align: center; padding: 30px; color: var(--ink-faint);" class="mono">
                  No audit records match the selected filters.
                </td>
              </tr>
            ` : filtered.map((a, idx) => {
              let boundsObj = {};
              try { boundsObj = JSON.parse(a.intervention_bounds); } catch(e) {}
              const boundsSummary = boundsObj.max_discount_pct > 0 
                ? `max ${boundsObj.max_discount_pct}%` 
                : (boundsObj.max_retries ? `max ${boundsObj.max_retries}r` : (boundsObj.window || '0% disc'));

              const dateStr = new Date(a.detected_at).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });

              return `
                <tr class="ledger-row" data-action-id="${a.id}">
                  <td class="mono" style="font-size: 11.5px; color: var(--ink-soft);">${dateStr}</td>
                  <td class="mono" style="font-weight: 600;">
                    ${a.trigger_event_id}
                    <span style="font-size: 10px; color: var(--ink-faint); display: block;">${a.trigger_type}</span>
                  </td>
                  <td>
                    <div style="display: flex; align-items: center; gap: 6px;">
                      <span class="mono" style="font-weight: 600;">${a.diagnosed_cause}</span>
                      ${getSourceBadge(a.diagnosis_source)}
                    </div>
                    <span class="mono" style="font-size: 11px; color: var(--ink-soft);">conf: ${(a.diagnosis_confidence * 100).toFixed(0)}%</span>
                  </td>
                  <td>
                    <div class="mono" style="font-weight: 600;">${a.chosen_intervention}</div>
                    <span class="mono" style="font-size: 10px; color: var(--ink-faint);">${boundsSummary}</span>
                  </td>
                  <td class="mono" style="font-size: 11.5px; text-transform: uppercase;">
                    ${a.channel !== 'none' ? `● ${a.channel}` : '<span style="color: var(--ink-faint);">none</span>'}
                  </td>
                  <td>
                    ${a.guardrail_ok ? `
                      <span class="mono" style="color: var(--money); font-size: 11px; font-weight: 600;">✓ PASS</span>
                    ` : `
                      <span class="mono" style="color: var(--red); font-size: 11px; font-weight: 700;">⚠️ SANITIZED</span>
                    `}
                  </td>
                  <td style="text-align: center;">
                    <span class="stamp ${getStampClass(a.outcome)}">${formatStampLabel(a.outcome)}</span>
                  </td>
                  <td style="text-align: right;" class="mono">
                    <div style="font-weight: 700; color: ${a.net_recovered > 0 ? 'var(--money)' : (a.net_recovered < 0 ? 'var(--red)' : 'var(--ink)')};">
                      ₹${a.net_recovered.toFixed(2)}
                    </div>
                    ${a.amount_recovered > 0 ? `
                      <span style="font-size: 10px; color: var(--ink-faint);">gross ₹${a.amount_recovered.toFixed(0)}</span>
                    ` : ''}
                  </td>
                </tr>
                <tr class="trace-row" id="trace-${a.id}" style="display: none;">
                  <td colspan="8" style="padding: 0;">
                    ${renderTraceDrawerHtml(a)}
                  </td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;

  // Attach event listeners for filtering
  if (onFilterChange) {
    const searchInput = container.querySelector('#ledger-search');
    const causeSelect = container.querySelector('#filter-cause');
    const interventionSelect = container.querySelector('#filter-intervention');
    const outcomeSelect = container.querySelector('#filter-outcome');

    const triggerUpdate = () => {
      onFilterChange({
        search: searchInput.value,
        cause: causeSelect.value,
        intervention: interventionSelect.value,
        outcome: outcomeSelect.value
      });
    };

    searchInput.addEventListener('input', triggerUpdate);
    causeSelect.addEventListener('change', triggerUpdate);
    interventionSelect.addEventListener('change', triggerUpdate);
    outcomeSelect.addEventListener('change', triggerUpdate);
  }

  // Attach row expansion listeners
  const rows = container.querySelectorAll('.ledger-row');
  rows.forEach(row => {
    row.addEventListener('click', () => {
      const actId = row.getAttribute('data-action-id');
      const traceRow = container.querySelector(`#trace-${actId}`);
      if (traceRow) {
        const isHidden = traceRow.style.display === 'none';
        traceRow.style.display = isHidden ? 'table-row' : 'none';
        row.classList.toggle('selected', isHidden);
      }
    });
  });

  // Attach Hinglish / English Voice Player listeners
  const voiceButtons = container.querySelectorAll('.audio-btn');
  voiceButtons.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const text = btn.getAttribute('data-msg');
      const lang = btn.getAttribute('data-lang');
      speakMessage(text, lang);
    });
  });
}

function renderTraceDrawerHtml(a) {
  let boundsObj = {};
  try { boundsObj = JSON.parse(a.intervention_bounds); } catch(e) {}

  return `
    <div class="trace-drawer">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
        <span class="mono" style="font-weight: 700; font-size: 12px; color: var(--ink);">
          🔍 Full 5-Stage Audit Trail & Explainability Trace for <span style="color: var(--money);">${a.trigger_event_id}</span>
        </span>
        <span class="mono" style="font-size: 11px; color: var(--ink-soft);">
          Action ID: ${a.id}
        </span>
      </div>

      <div class="trace-grid">
        <!-- Stage 1: Detection -->
        <div class="trace-stage">
          <div class="trace-stage-title">
            <span>01. Detection</span>
            <span class="step-tag rules">Rules</span>
          </div>
          <div class="trace-stage-content mono">
            <div>Type: <strong>${a.trigger_type}</strong></div>
            <div>Time: ${new Date(a.detected_at).toISOString()}</div>
          </div>
        </div>

        <!-- Stage 2: Diagnosis -->
        <div class="trace-stage">
          <div class="trace-stage-title">
            <span>02. Diagnosis</span>
            <span class="step-tag ${a.diagnosis_source === 'rules' ? 'rules' : 'ai'}">${a.diagnosis_source.toUpperCase()}</span>
          </div>
          <div class="trace-stage-content">
            <div class="mono"><strong>${a.diagnosed_cause}</strong> (Conf: ${(a.diagnosis_confidence * 100).toFixed(0)}%)</div>
            <div style="font-size: 11px; color: var(--ink-soft); margin-top: 4px;">${a.diagnosis_reasoning}</div>
          </div>
        </div>

        <!-- Stage 3: Decision Engine -->
        <div class="trace-stage">
          <div class="trace-stage-title">
            <span>03. Decision Policy</span>
            <span class="step-tag rules">Rules</span>
          </div>
          <div class="trace-stage-content">
            <div class="mono"><strong>${a.chosen_intervention}</strong></div>
            <div class="mono" style="font-size: 10.5px; color: var(--ink-soft); margin-top: 2px;">
              Bounds: ${JSON.stringify(boundsObj)}
            </div>
            ${a.stopping_rule_triggered ? `
              <div class="mono" style="color: var(--red); font-size: 11px; font-weight: 600; margin-top: 4px;">
                🛑 Stopping Rule: ${a.stopping_rule_triggered}
              </div>
            ` : ''}
            <div style="font-size: 11px; color: var(--ink-soft); margin-top: 4px;">${a.decision_reasoning}</div>
          </div>
        </div>

        <!-- Stage 4: Executor & Guardrails -->
        <div class="trace-stage" style="grid-column: span 1.5;">
          <div class="trace-stage-title">
            <span>04. Execution & Guardrail</span>
            <span class="step-tag rules">Regex Guard</span>
          </div>
          <div class="trace-stage-content">
            ${a.sent_message ? `
              <div class="message-box">
                <div class="mono" style="font-size: 10px; color: var(--ink-soft); text-transform: uppercase;">
                  Sent Copy (${a.channel.toUpperCase()}):
                </div>
                <div style="margin-top: 2px; font-family: var(--font-sans);">${a.sent_message}</div>
                <button class="audio-btn" data-msg="${escapeHtml(a.sent_message)}" data-lang="${a.drafted_message ? 'Hinglish' : 'English'}">
                  🔊 Listen (Voice Synthesis)
                </button>
              </div>
              ${!a.guardrail_ok ? `
                <div class="mono" style="color: var(--red); font-size: 11px; margin-top: 6px;">
                  ⚠️ Guardrail Sanitized: ${a.guardrail_reason}
                </div>
              ` : ''}
            ` : `
              <div class="mono" style="font-size: 11px; color: var(--ink-faint); padding: 8px 0;">
                No customer message drafted (${a.chosen_intervention === 'escalate_review' ? 'Escalated internally to fraud ops' : 'Outreach suppressed by policy'}).
              </div>
            `}
          </div>
        </div>

        <!-- Stage 5: Outcomes -->
        <div class="trace-stage">
          <div class="trace-stage-title">
            <span>05. Outcome & Net ROI</span>
            <span class="step-tag rules">Probabilistic</span>
          </div>
          <div class="trace-stage-content mono">
            <div>Outcome: <strong>${a.outcome.toUpperCase()}</strong></div>
            <div>Gross: ₹${a.amount_recovered.toFixed(2)}</div>
            <div>Cost: -₹${a.intervention_cost.toFixed(2)}</div>
            <div style="font-weight: 700; color: var(--money); margin-top: 2px;">
              Net: ₹${a.net_recovered.toFixed(2)}
            </div>
            ${a.follow_up_date ? `
              <div style="font-size: 10px; color: var(--amber); margin-top: 4px;">
                📅 Follow-up: ${a.follow_up_date}
              </div>
            ` : ''}
          </div>
        </div>
      </div>
    </div>
  `;
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/"/g, '&quot;');
}

function speakMessage(text, language = 'English') {
  if (!('speechSynthesis' in window)) {
    alert('Browser SpeechSynthesis is not supported on this device.');
    return;
  }
  
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  
  const voices = window.speechSynthesis.getVoices();
  let selectedVoice = null;
  
  if (language === 'Hinglish') {
    selectedVoice = voices.find(v => v.lang === 'hi-IN' || v.lang.startsWith('hi')) 
      || voices.find(v => v.lang === 'en-IN');
  } else {
    selectedVoice = voices.find(v => v.lang === 'en-IN') 
      || voices.find(v => v.lang.startsWith('en'));
  }
  
  if (selectedVoice) {
    utterance.voice = selectedVoice;
  }
  utterance.rate = 1.0;
  utterance.pitch = 1.0;
  window.speechSynthesis.speak(utterance);
}
