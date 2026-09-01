// Horizontal Pipeline Rail showing events flowing across all 5 stages

export function renderPipelineRail(container, batchData) {
  if (!batchData || !batchData.actions) return;

  const actions = batchData.actions;
  const total = actions.length;

  const rulesDiag = actions.filter(a => a.diagnosis_source === 'rules').length;
  const aiDiag = actions.filter(a => a.diagnosis_source.includes('llm')).length;

  const stoppedCount = actions.filter(a => a.stopping_rule_triggered).length;
  const escalatedCount = actions.filter(a => a.chosen_intervention === 'escalate_review').length;
  const actionableCount = total - stoppedCount - escalatedCount;

  const guardedCount = actions.filter(a => a.drafted_message).length;
  const recoveredCount = actions.filter(a => a.outcome === 'recovered').length;

  container.innerHTML = `
    <div class="rail-header">
      <div class="rail-title">
        <span>⚡ 5-Stage Closed-Loop Pipeline Rail</span>
      </div>
      <div class="mono" style="font-size: 11px; color: var(--ink-soft);">
        Deterministic Rules Everywhere · Constrained AI in 2 Slots Only
      </div>
    </div>
    <div class="rail-steps">
      <!-- Stage 1 -->
      <div class="rail-step">
        <div class="step-num">Stage 01</div>
        <div class="step-name">Detector</div>
        <span class="step-tag rules">Rules</span>
        <div class="step-count">${total} <span style="font-size: 11px; font-weight: normal; color: var(--ink-soft);">At-Risk</span></div>
      </div>

      <!-- Stage 2 -->
      <div class="rail-step">
        <div class="step-num">Stage 02</div>
        <div class="step-name">Diagnoser</div>
        <div style="display: flex; gap: 4px; margin-bottom: 2px;">
          <span class="step-tag rules">${rulesDiag} Rules</span>
          <span class="step-tag ai">${aiDiag} AI</span>
        </div>
        <div class="step-count">${total} <span style="font-size: 11px; font-weight: normal; color: var(--ink-soft);">Diagnosed</span></div>
      </div>

      <!-- Stage 3 -->
      <div class="rail-step">
        <div class="step-num">Stage 03</div>
        <div class="step-name">Decision Engine</div>
        <span class="step-tag rules">Pure Policy Table</span>
        <div class="step-count">${actionableCount} <span style="font-size: 11px; font-weight: normal; color: var(--ink-soft);">Actionable</span></div>
      </div>

      <!-- Stage 4 -->
      <div class="rail-step">
        <div class="step-num">Stage 04</div>
        <div class="step-name">Executor & Guard</div>
        <div style="display: flex; gap: 4px; margin-bottom: 2px;">
          <span class="step-tag ai">AI Draft</span>
          <span class="step-tag rules">Regex Guard</span>
        </div>
        <div class="step-count">${guardedCount} <span style="font-size: 11px; font-weight: normal; color: var(--ink-soft);">Validated</span></div>
      </div>

      <!-- Stage 5 -->
      <div class="rail-step active">
        <div class="step-num">Stage 05</div>
        <div class="step-name">Outcomes</div>
        <span class="step-tag rules">Probabilistic</span>
        <div class="step-count" style="color: var(--money);">${recoveredCount} <span style="font-size: 11px; font-weight: normal; color: var(--money);">Recovered</span></div>
      </div>
    </div>
  `;
}
