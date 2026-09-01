// AI vs Rules Architectural Disclosure Table

export function renderDisclosureTable(container) {
  container.innerHTML = `
    <div class="disclosure-container">
      <button class="disclosure-trigger" id="toggle-disclosure-btn">
        <span>📖 AI-vs-Rules Architectural Disclosure (Hackathon AI-Judgment Rubric)</span>
        <span id="disclosure-arrow">▼</span>
      </button>
      <div class="disclosure-content" id="disclosure-content">
        <table class="disclosure-table">
          <thead>
            <tr>
              <th style="width: 22%;">Pipeline Component</th>
              <th style="width: 14%;">Engine Type</th>
              <th style="width: 64%;">Architectural Justification</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td class="mono"><strong>01. Event Detector</strong></td>
              <td><span class="step-tag rules">Rules</span></td>
              <td>Deterministic filtering of raw payment declines and checkout abandonment funnels without LLM overhead.</td>
            </tr>
            <tr>
              <td class="mono"><strong>02. Explicit Decline Mapping</strong></td>
              <td><span class="step-tag rules">Rules</span></td>
              <td>Bank decline codes (INSUFFICIENT_FUNDS, RISK_BLOCK, CARD_EXPIRED, GATEWAY_TIMEOUT) map directly with 100% precision.</td>
            </tr>
            <tr>
              <td class="mono"><strong>03. Ambiguous Drop-off Diagnoser</strong></td>
              <td><span class="step-tag ai">AI (Claude 3.5)</span></td>
              <td>Multi-variable behavioral inference across dwell times, funnel stages, and cart values using strict JSON tool schemas.</td>
            </tr>
            <tr>
              <td class="mono"><strong>04. Stopping Rules & Contact Limits</strong></td>
              <td><span class="step-tag rules">Rules</span></td>
              <td>Hard customer opt-out (DNC) and max 2 contact attempts per batch enforced strictly in code before any action.</td>
            </tr>
            <tr>
              <td class="mono"><strong>05. Intervention & Bounds Selection</strong></td>
              <td><span class="step-tag rules">Rules</span></td>
              <td>Pure policy table binds actions to hard limits (e.g. max discount <= 5%, 48h windows); LLM never touches financial bounds.</td>
            </tr>
            <tr>
              <td class="mono"><strong>06. Recovery Message Copywriting</strong></td>
              <td><span class="step-tag ai">AI (Claude 3.5)</span></td>
              <td>Empathetic, brand-safe SMS/WhatsApp copy generation in English & Hinglish, strictly bounded by upstream policy.</td>
            </tr>
            <tr>
              <td class="mono"><strong>07. Deterministic Guardrail Validator</strong></td>
              <td><span class="step-tag rules">Rules</span></td>
              <td>Regex scanner (\d+%) catches and rejects out-of-bounds promises (e.g. unauthorized discounts) with automatic fallback substitution.</td>
            </tr>
            <tr>
              <td class="mono"><strong>08. Outcome & Net Revenue Simulation</strong></td>
              <td><span class="step-tag rules">Rules</span></td>
              <td>Seeded probabilistic conversion model deducting per-channel messaging costs (SMS, WhatsApp, Email) from gross recovery.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  `;

  const btn = container.querySelector('#toggle-disclosure-btn');
  const content = container.querySelector('#disclosure-content');
  const arrow = container.querySelector('#disclosure-arrow');

  btn.addEventListener('click', () => {
    content.classList.toggle('open');
    arrow.textContent = content.classList.contains('open') ? '▲' : '▼';
  });
}
