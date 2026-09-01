import { runBatch, getExportUrl } from './api.js';
import { renderStatStrip } from './render/stat_strip.js';
import { renderPipelineRail } from './render/pipeline_rail.js';
import { renderDisclosureTable } from './render/disclosure_table.js';
import { renderGuardrailCard } from './render/guardrail_card.js';
import { renderPlainSummary } from './render/plain_summary.js';
import { renderLedgerTable } from './render/ledger_table.js';

// Application State
let state = {
  currentBatch: null,
  activeFilters: {
    search: '',
    cause: 'all',
    intervention: 'all',
    outcome: 'all',
    channel: 'all'
  },
  isPlayingTicker: false,
  tickerTimer: null,
  visibleActionCount: 0
};

// DOM Elements
const elements = {
  seedInput: document.getElementById('seed-input'),
  countInput: document.getElementById('count-input'),
  runBtn: document.getElementById('run-btn'),
  skipBtn: document.getElementById('skip-btn'),
  exportCsvBtn: document.getElementById('export-csv-btn'),
  exportJsonBtn: document.getElementById('export-json-btn'),
  tickerBanner: document.getElementById('ticker-banner'),
  tickerCount: document.getElementById('ticker-count'),
  statStripContainer: document.getElementById('stat-strip-container'),
  pipelineRailContainer: document.getElementById('pipeline-rail-container'),
  disclosureContainer: document.getElementById('disclosure-container'),
  guardrailContainer: document.getElementById('guardrail-container'),
  summaryContainer: document.getElementById('summary-container'),
  ledgerContainer: document.getElementById('ledger-container')
};

// Initialize Application
async function init() {
  renderDisclosureTable(elements.disclosureContainer);

  // Bind Event Listeners
  elements.runBtn.addEventListener('click', handleRunBatch);
  elements.skipBtn.addEventListener('click', handleSkipTicker);
  elements.exportCsvBtn.addEventListener('click', handleExportCsv);
  elements.exportJsonBtn.addEventListener('click', handleExportJson);

  // Run initial seeded batch on load
  await executeBatchRun(42, 70, false);
}

async function handleRunBatch() {
  const seed = parseInt(elements.seedInput.value, 10) || 42;
  const count = parseInt(elements.countInput.value, 10) || 70;
  await executeBatchRun(seed, count, true);
}

async function executeBatchRun(seed, count, animate = true) {
  try {
    elements.runBtn.disabled = true;
    elements.runBtn.textContent = '⏳ Executing 5 Stages...';
    
    // Stop any ongoing ticker
    if (state.tickerTimer) {
      clearInterval(state.tickerTimer);
      state.tickerTimer = null;
    }

    const data = await runBatch(seed, count);
    state.currentBatch = data;

    // Enable export buttons
    elements.exportCsvBtn.disabled = false;
    elements.exportJsonBtn.disabled = false;

    // Render permanent static cards
    renderGuardrailCard(elements.guardrailContainer, data.self_test);
    renderPlainSummary(elements.summaryContainer, data.summary_text);

    if (animate && data.actions.length > 5) {
      startTickerPlayback(data);
    } else {
      finishTicker(data);
    }
  } catch (err) {
    alert('Error running batch: ' + err.message);
  } finally {
    elements.runBtn.disabled = false;
    elements.runBtn.textContent = '▶ Run Engine Batch';
  }
}

function startTickerPlayback(data) {
  state.isPlayingTicker = true;
  state.visibleActionCount = 1;
  elements.tickerBanner.style.display = 'flex';
  elements.skipBtn.style.display = 'inline-flex';

  const totalActions = data.actions.length;
  const intervalMs = Math.max(120, Math.min(300, Math.floor(12000 / totalActions)));

  state.tickerTimer = setInterval(() => {
    state.visibleActionCount++;

    const currentSlice = data.actions.slice(0, state.visibleActionCount);
    const currGross = currentSlice.reduce((acc, a) => acc + (a.amount_recovered || 0), 0);
    const currNet = currentSlice.reduce((acc, a) => acc + (a.net_recovered || 0), 0);

    elements.tickerCount.textContent = `Resolving events live: ${state.visibleActionCount} / ${totalActions}`;

    const partialBatch = {
      ...data,
      actions: currentSlice
    };

    renderStatStrip(elements.statStripContainer, partialBatch, currGross, currNet);
    renderPipelineRail(elements.pipelineRailContainer, partialBatch);
    renderLedgerTable(
      elements.ledgerContainer,
      currentSlice,
      state.activeFilters,
      handleFilterChange
    );

    if (state.visibleActionCount >= totalActions) {
      finishTicker(data);
    }
  }, intervalMs);
}

function handleSkipTicker() {
  if (state.currentBatch) {
    finishTicker(state.currentBatch);
  }
}

function finishTicker(data) {
  if (state.tickerTimer) {
    clearInterval(state.tickerTimer);
    state.tickerTimer = null;
  }
  state.isPlayingTicker = false;
  state.visibleActionCount = data.actions.length;
  elements.tickerBanner.style.display = 'none';
  elements.skipBtn.style.display = 'none';

  renderStatStrip(elements.statStripContainer, data);
  renderPipelineRail(elements.pipelineRailContainer, data);
  renderLedgerTable(
    elements.ledgerContainer,
    data.actions,
    state.activeFilters,
    handleFilterChange
  );
}

function handleFilterChange(newFilters) {
  state.activeFilters = { ...state.activeFilters, ...newFilters };
  if (state.currentBatch) {
    const visibleActions = state.isPlayingTicker 
      ? state.currentBatch.actions.slice(0, state.visibleActionCount) 
      : state.currentBatch.actions;

    renderLedgerTable(
      elements.ledgerContainer,
      visibleActions,
      state.activeFilters,
      handleFilterChange
    );
  }
}

function handleExportCsv() {
  if (state.currentBatch && state.currentBatch.batch) {
    window.open(getExportUrl(state.currentBatch.batch.id, 'csv'), '_blank');
  }
}

function handleExportJson() {
  if (state.currentBatch && state.currentBatch.batch) {
    window.open(getExportUrl(state.currentBatch.batch.id, 'json'), '_blank');
  }
}

// Start on DOM Ready
window.addEventListener('DOMContentLoaded', init);
