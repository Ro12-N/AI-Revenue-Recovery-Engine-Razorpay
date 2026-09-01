// Stat Strip with High-Impact Counterfactual Comparison

export function renderStatStrip(container, batchData, animatedGross = null, animatedNet = null) {
  if (!batchData || !batchData.batch) return;

  const b = batchData.batch;
  const gross = animatedGross !== null ? animatedGross : b.total_recovered_gross;
  const net = animatedNet !== null ? animatedNet : b.total_recovered_net;
  const atRisk = b.total_at_risk || 0;
  const recoveryRate = atRisk > 0 ? ((gross / atRisk) * 100).toFixed(1) : 0;
  const agentOffLost = b.agent_off_total_lost || atRisk;

  container.innerHTML = `
    <!-- High-Impact Counterfactual Comparison -->
    <div class="stat-card counterfactual-card">
      <div>
        <div class="stat-label">Counterfactual Impact Model</div>
        <div class="stat-value money-val">+₹${net.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
        <div class="stat-sub">Net revenue saved from 100% loss</div>
      </div>
      <div class="cf-split">
        <div class="cf-column">
          <span class="cf-title agent-on">● With Agent</span>
          <span class="mono" style="font-weight: 700; color: var(--money);">₹${net.toLocaleString('en-IN', { minimumFractionDigits: 0 })} Saved</span>
          <span class="mono" style="font-size: 10px; color: var(--ink-soft);">${b.recovered_count} recovered</span>
        </div>
        <div class="cf-column" style="border-left: 1px dashed var(--hairline-strong); padding-left: 8px;">
          <span class="cf-title agent-off">○ Without Agent</span>
          <span class="mono" style="font-weight: 700; color: var(--red);">-₹${agentOffLost.toLocaleString('en-IN', { minimumFractionDigits: 0 })} Lost</span>
          <span class="mono" style="font-size: 10px; color: var(--ink-soft);">0% baseline</span>
        </div>
      </div>
    </div>

    <!-- Net Recovered -->
    <div class="stat-card">
      <div class="stat-label">Net Recovered (Headline)</div>
      <div class="stat-value money-val">₹${net.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
      <div class="stat-sub">Gross minus channel fees</div>
    </div>

    <!-- Gross Recovered -->
    <div class="stat-card">
      <div class="stat-label">Gross Recovered</div>
      <div class="stat-value">₹${gross.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
      <div class="stat-sub">Recovery rate: <strong>${recoveryRate}%</strong></div>
    </div>

    <!-- Total At-Risk Revenue -->
    <div class="stat-card">
      <div class="stat-label">Total At-Risk Revenue</div>
      <div class="stat-value">₹${atRisk.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
      <div class="stat-sub">${b.at_risk_count} drop-off & failure events</div>
    </div>

    <!-- Actions & Guardrail Interceptions -->
    <div class="stat-card">
      <div class="stat-label">System Interventions</div>
      <div class="stat-value">${batchData.actions.length}</div>
      <div class="stat-sub">${b.recovered_count} won · ${b.stopped_count} stopped · ${b.escalated_count} escalated</div>
    </div>
  `;
}
