// Permanent Adversarial Guardrail Self-Test Card

export function renderGuardrailCard(container, selfTestData) {
  if (!selfTestData) return;

  container.innerHTML = `
    <div class="guardrail-card">
      <div class="gr-header">
        <div class="gr-title">
          <span>🛡️ Guardrail Engine Active Verification (Live Adversarial Test)</span>
        </div>
        <div class="gr-status">${selfTestData.status}</div>
      </div>
      <div class="gr-body">
        <div class="gr-box">
          <div class="gr-label">Injected Adversarial Draft (Over-Bound Attack)</div>
          <div class="mono" style="color: var(--red); font-weight: 500;">
            "${selfTestData.input_draft}"
          </div>
          <div class="gr-label" style="margin-top: 8px;">Authorized Policy Limit</div>
          <div class="mono" style="color: var(--ink-soft); font-weight: 600;">
            ${selfTestData.authorized_bound}
          </div>
        </div>
        <div class="gr-box" style="border-left: 3px solid var(--red);">
          <div class="gr-label">Deterministic Interception & Sanitization</div>
          <div class="mono" style="color: var(--red); font-size: 11px; margin-bottom: 6px;">
            ⚠️ ${selfTestData.rejection_reason}
          </div>
          <div class="gr-label">Substituted Safe Fallback Sent to Customer</div>
          <div class="mono" style="color: var(--money); font-weight: 600;">
            "${selfTestData.fallback_substituted}"
          </div>
        </div>
      </div>
    </div>
  `;
}
