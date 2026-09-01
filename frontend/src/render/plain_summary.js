// Plain-English Non-Technical Summary Banner

export function renderPlainSummary(container, summaryText) {
  if (!summaryText) return;

  container.innerHTML = `
    <div class="summary-banner">
      <div class="summary-label">📋 Executive Summary (Non-Technical Audit Overview)</div>
      <div>${summaryText}</div>
    </div>
  `;
}
