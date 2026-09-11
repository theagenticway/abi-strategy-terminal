const fs = require('fs');
const path = require('path');
const assert = require('assert');

console.log("=== Running Comprehensive Node.js Allocator & LocalStorage Simulation ===");

// 1. Read index.html and extract the main Application Master Controller script block
const html = fs.readFileSync(path.join(__dirname, '../index.html'), 'utf-8');
const scriptBlocks = [...html.matchAll(/<script[\s\S]*?>([\s\S]*?)<\/script>/g)];
assert(scriptBlocks.length >= 2, "Must find script blocks in index.html");
const mainScript = scriptBlocks[scriptBlocks.length - 1][1];

// 2. Mock minimal browser environment
const storage = {};
global.localStorage = {
    getItem: (k) => storage[k] || null,
    setItem: (k, v) => { storage[k] = v.toString(); },
    removeItem: (k) => { delete storage[k]; }
};

const domElements = {};
function createMockElement(id) {
    return {
        id: id,
        textContent: '',
        value: '',
        innerHTML: '',
        className: '',
        children: [],
        style: {},
        classList: {
            _classes: new Set(),
            add: function(...c) { c.forEach(x => this._classes.add(x)); },
            remove: function(...c) { c.forEach(x => this._classes.delete(x)); },
            contains: function(x) { return this._classes.has(x); }
        },
        querySelectorAll: () => [],
        appendChild: function(child) { this.children.push(child); },
        setAttribute: () => {},
        getAttribute: () => null
    };
}

global.document = {
    getElementById: (id) => {
        if (!domElements[id]) domElements[id] = createMockElement(id);
        return domElements[id];
    },
    querySelectorAll: (selector) => {
        return [];
    },
    createElement: (tag) => {
        return createMockElement(tag);
    }
};

global.window = global;
global.window.addEventListener = () => {};
global.confirm = () => true;
global.alert = () => {};
global.tailwind = {};
global.setInterval = () => {};
global.fetch = async (url) => ({
    ok: true,
    json: async () => tradesLogData
});

// 3. Load latest.json and evaluate script
const latestData = JSON.parse(fs.readFileSync(path.join(__dirname, '../data/latest.json'), 'utf-8'));
const tradesLogData = JSON.parse(fs.readFileSync(path.join(__dirname, '../data/trades_log.json'), 'utf-8'));

const vm = require('vm');
const context = vm.createContext(global);
vm.runInContext(mainScript, context);

// -----------------------------------------------------------------
// Test 1: Empty Portfolio initialization
// -----------------------------------------------------------------
let port = context.getMyPortfolio();
assert.strictEqual(Object.keys(port).length, 0, "Initial portfolio must be empty");
console.log("✔ Test 1: Empty Portfolio initialized correctly.");

// -----------------------------------------------------------------
// Test 2: Render Recs View with $50k default, Mixed regime (25% cash buffer)
// -----------------------------------------------------------------
context.currentPayload = latestData;
context.setDeployCapital(50000);
context.renderRecsView(latestData);

assert.strictEqual(domElements['plan-total-cap'].textContent, '$50,000');
assert.strictEqual(domElements['plan-my-committed'].textContent, '$0 (0 pos)');
assert.strictEqual(domElements['plan-cash-reserve'].textContent, '$12,500 (25%)');
assert.strictEqual(domElements['plan-free-cash'].textContent, '$37,500');
assert.strictEqual(domElements['plan-today-budget'].textContent, '$16,500 (33%)');
assert.strictEqual(domElements['plan-leaps-budget'].textContent, '$9,900');
assert.strictEqual(domElements['plan-spreads-budget'].textContent, '$6,600');
console.log("✔ Test 2: Default $50k Balanced Core/Satellite & 25% cash reserve verified.");

// -----------------------------------------------------------------
// Test 3: Allocation Architecture Modes (Pillar 2)
// -----------------------------------------------------------------
// A. Tactical Mode (80% Spreads / 20% LEAPS)
domElements['alloc-architecture-mode'].value = 'tactical';
context.updateAllocationPlan();
assert.strictEqual(domElements['plan-leaps-budget'].textContent, '$3,300'); // 20% of 16500
assert.strictEqual(domElements['plan-spreads-budget'].textContent, '$13,200'); // 80% of 16500
console.log("✔ Test 3A: Tactical Mode (80% Spreads / 20% LEAPS) verified.");

// B. Secular Mode (80% LEAPS / 20% Spreads)
domElements['alloc-architecture-mode'].value = 'secular';
context.updateAllocationPlan();
assert.strictEqual(domElements['plan-leaps-budget'].textContent, '$13,200'); // 80% of 16500
assert.strictEqual(domElements['plan-spreads-budget'].textContent, '$3,300'); // 20% of 16500
console.log("✔ Test 3B: Secular Compounding Mode (80% LEAPS / 20% Spreads) verified.");

// Return to Balanced
domElements['alloc-architecture-mode'].value = 'balanced';
context.updateAllocationPlan();

// -----------------------------------------------------------------
// Test 4: Dynamic Cash Buffer Modes (Pillar 3)
// -----------------------------------------------------------------
// Fixed 20%
domElements['alloc-cash-reserve-mode'].value = 'fixed_20';
context.updateAllocationPlan();
assert.strictEqual(domElements['plan-cash-reserve'].textContent, '$10,000 (20%)');
assert.strictEqual(domElements['plan-free-cash'].textContent, '$40,000');

// Fixed 30%
domElements['alloc-cash-reserve-mode'].value = 'fixed_30';
context.updateAllocationPlan();
assert.strictEqual(domElements['plan-cash-reserve'].textContent, '$15,000 (30%)');
assert.strictEqual(domElements['plan-free-cash'].textContent, '$35,000');

// Fully Deployed 0%
domElements['alloc-cash-reserve-mode'].value = 'fully_deployed';
context.updateAllocationPlan();
assert.strictEqual(domElements['plan-cash-reserve'].textContent, '$0 (0%)');
assert.strictEqual(domElements['plan-free-cash'].textContent, '$50,000');
assert.strictEqual(domElements['plan-today-budget'].textContent, '$16,500 (33%)');

// Reset to Auto Regime
domElements['alloc-cash-reserve-mode'].value = 'auto_regime';
context.updateAllocationPlan();
assert.strictEqual(domElements['plan-cash-reserve'].textContent, '$12,500 (25%)');
console.log("✔ Test 4: Dynamic Dry Powder reserve modes verified.");

// -----------------------------------------------------------------
// Test 5: LocalStorage Portfolio Tracking & Capital Deduction (Option 1)
// -----------------------------------------------------------------
// Adding DOCU spread (1 contract @ $1,520)
context.toggleTradePortfolio('spread', 'DOCU', 'Oct 26 $65/$105 Call Spread', 1, 1520, 68.41, 54.6, 102.94, 116.75, 'TECH SOFTWARE');
port = context.getMyPortfolio();
assert(port['DOCU_SPREAD'], "DOCU_SPREAD must exist in portfolio");
assert.strictEqual(port['DOCU_SPREAD'].totalCapitalCommitted, 1520);
assert.strictEqual(domElements['plan-my-committed'].textContent, '$1,520 (1 pos)');
assert.strictEqual(domElements['plan-free-cash'].textContent, '$35,980'); // 50000 - 1520 - 12500 = 35980
console.log("✔ Test 5: Adding spread to My Portfolio updates committed & free cash.");

// Adding NVDA LEAPS (1 contract @ $6,879)
context.toggleTradePortfolio('leaps', 'NVDA', 'Jan 2028 $180 Call LEAPS', 1, 6879, 230.36, 191.87, 315.04, 365.08, 'TECH SEMIS');
port = context.getMyPortfolio();
assert(port['NVDA_LEAPS'], "NVDA_LEAPS must exist in portfolio");
// Total committed = 1520 + 6879 = 8399
assert.strictEqual(domElements['plan-my-committed'].textContent, '$8,399 (2 pos)');
assert.strictEqual(domElements['plan-free-cash'].textContent, '$29,101'); // 50000 - 8399 - 12500 = 29101
console.log("✔ Test 6: Multiple position commitments aggregate accurately.");

// -----------------------------------------------------------------
// Test 6: Capacity Reached Guardrail & Throttle
// -----------------------------------------------------------------
// Add large position of $30,000 committed
context.toggleTradePortfolio('leaps', 'MSFT', 'Jan 2028 Call LEAPS', 5, 6000, 450, 410, 550, 600, 'TECH CORE');
// Total committed = 8399 + 30000 = 38399. Cash reserve = 12500. Total required = 50899 > 50000!
assert.strictEqual(domElements['plan-free-cash'].textContent, '$0');
assert.strictEqual(domElements['plan-today-budget'].textContent, '$0 (0%)');
assert(domElements['plan-capacity-banner'].classList.contains('flex'), "Capacity banner must be visible when capacity is reached");
console.log("✔ Test 7: Capacity Reached guardrail throttles today's tranche to $0 and shows warning banner.");

// -----------------------------------------------------------------
// Test 7: Position Removal & Capital Recovery
// -----------------------------------------------------------------
context.toggleTradePortfolio('leaps', 'MSFT', '', 0, 0); // Toggle again removes it
port = context.getMyPortfolio();
assert(!port['MSFT_LEAPS'], "MSFT_LEAPS should be removed");
assert.strictEqual(domElements['plan-my-committed'].textContent, '$8,399 (2 pos)');
assert.strictEqual(domElements['plan-free-cash'].textContent, '$29,101');
assert(!domElements['plan-capacity-banner'].classList.contains('flex'), "Capacity banner must be hidden when capacity is not reached");
console.log("✔ Test 8: Removing trade safely returns committed capital to free liquid cash.");

// -----------------------------------------------------------------
// Test 8: Table 3 Trade Ledger Integration & My Portfolio Filter
// -----------------------------------------------------------------
context.allTradesLog = tradesLogData.trades;
context.setPerfFilter('MY_PORTFOLIO');
assert.strictEqual(context.activePerfFilter, 'MY_PORTFOLIO');
// Toggling ledger trade directly
context.toggleLedgerTradePortfolio('2026-08-19_SWKS', 'SWKS', 'Oct 26 Call Spread', 1500);
port = context.getMyPortfolio();
assert(port['2026-08-19_SWKS'], "Ledger trade must be stored in portfolio");
assert.strictEqual(port['2026-08-19_SWKS'].totalCapitalCommitted, 1500);
console.log("✔ Test 9: Table 3 Ledger trade tracking & MY_PORTFOLIO filter verified.");

// -----------------------------------------------------------------
// Test 9: Small Account Protection ($10,000 tier)
// -----------------------------------------------------------------
context.setDeployCapital(10000);
context.clearMyPortfolioConfirm();
assert.strictEqual(Object.keys(context.getMyPortfolio()).length, 0, "Portfolio should be empty after clear");
assert.strictEqual(domElements['plan-total-cap'].textContent, '$10,000');
assert.strictEqual(domElements['plan-cash-reserve'].textContent, '$2,500 (25%)');
assert.strictEqual(domElements['plan-free-cash'].textContent, '$7,500');
assert.strictEqual(domElements['plan-today-budget'].textContent, '$3,300 (33%)');
console.log("✔ Test 10: $10,000 account tier calculates strictly with cash buffer.");

console.log("\n========================================================");
console.log(" ALL 10 COMPREHENSIVE SIMULATION TESTS PASSED CLEANLY! ");
console.log("========================================================");

// -----------------------------------------------------------------
// Test 11: Executive Market Briefing & Action Directive Rendering
// -----------------------------------------------------------------
assert(domElements['briefing-verdict-badge'], "briefing-verdict-badge must exist");
assert(domElements['briefing-macro-narrative'], "briefing-macro-narrative must exist");
assert(domElements['briefing-sector-narrative'], "briefing-sector-narrative must exist");
assert(domElements['briefing-mandates-list'], "briefing-mandates-list must exist");
assert(domElements['idx-spy-price'].textContent.includes('$548'), "SPY benchmark chip must render price");
assert(domElements['idx-qqq-price'].textContent.includes('$472'), "QQQ benchmark chip must render price");
assert(domElements['idx-rsp-price'].textContent.includes('$174'), "RSP benchmark chip must render price");
assert(domElements['idx-iwm-price'].textContent.includes('$218'), "IWM benchmark chip must render price");
assert(domElements['idx-qqq-status'].textContent.includes('Below'), "QQQ status must display Below 50 EMA");
console.log("✔ Test 11: Executive Market Briefing & 4-Index Benchmark Confluence Ribbon verified.");

// -----------------------------------------------------------------
// Test 12: Directional Mode Switcher (Long vs. Downside Hedges)
// -----------------------------------------------------------------
context.setDirectionalMode('HEDGE');
assert.strictEqual(context.activeDirectionalMode, 'HEDGE');
assert.strictEqual(domElements['table1-header-title'].textContent, 'Downside Hedges (Options Alpha Radar — Bear Put Spreads 30–45 DTE)');
console.log("✔ Test 12: Directional Mode switched to HEDGE (Bear Put Spreads).");

// -----------------------------------------------------------------
// Test 13: Tracking a Downside Hedge in My Portfolio
// -----------------------------------------------------------------
context.toggleTradePortfolio('hedge', 'TAN', 'Oct 26 $40/$35 Put Spread', 2, 190, 38.45, 40.20, 34.50, 31.80, 'SOLAR');
port = context.getMyPortfolio();
assert(port['TAN_HEDGE'], "TAN_HEDGE must exist in portfolio");
assert.strictEqual(port['TAN_HEDGE'].totalCapitalCommitted, 380); // 2 * 190
console.log("✔ Test 13: Downside Hedge position committed & tracked in My Portfolio.");

// -----------------------------------------------------------------
// Test 14: Switch back to LONG mode
// -----------------------------------------------------------------
context.setDirectionalMode('LONG');
assert.strictEqual(context.activeDirectionalMode, 'LONG');
assert.strictEqual(domElements['table1-header-title'].textContent, 'Tactical Swings (Options Alpha Radar — Bull Call Spreads 45–60 DTE)');
console.log("✔ Test 14: Directional Mode safely returned to LONG.");

// -----------------------------------------------------------------
// Test 15: Clean Options-only rendering in Table 1 & Table 2
// -----------------------------------------------------------------
domElements['table1-header-title'] = createMockElement('table1-header-title');
domElements['table2-header-title'] = createMockElement('table2-header-title');

context.renderRecsView(latestData);
assert(domElements['table1-header-title'].textContent.includes('Options Alpha Radar'), "Table 1 must be dedicated to Options Alpha Radar");
assert(domElements['table2-header-title'].textContent.includes('Deep-ITM Call LEAPS'), "Table 2 must be dedicated to Deep-ITM Call LEAPS");
console.log("✔ Test 15: Table 1 & Table 2 strictly dedicated to Bull Call Spreads and Deep-ITM Call LEAPS.");

// -----------------------------------------------------------------
// Test 16: Top navigation bar link to dedicated Equity & Stock Terminal
// -----------------------------------------------------------------
assert(html.includes('href="stocks.html"'), "Must link cleanly to stocks.html in top navigation");
console.log("✔ Test 16: Clean top navigation link to dedicated stocks.html verified.");

// -----------------------------------------------------------------
// Test 17: Strict absence of leftover equity switchers in index.html
// -----------------------------------------------------------------
assert(!html.includes('btn-asset-stocks'), "index.html must NOT contain leftover btn-asset-stocks");
assert(!html.includes('STRATEGY ASSET CLASS:'), "index.html must NOT contain leftover asset class switcher banner");
console.log("✔ Test 17: Strict absence of leftover equity/stock switcher widgets verified.");

// -----------------------------------------------------------------
// Test 18: Performance ledger dedicated to Options
// -----------------------------------------------------------------
assert.strictEqual(context.activeAssetClass, 'OPTIONS');
console.log("✔ Test 18: Options performance ledger verified.");


// -----------------------------------------------------------------

domElements["options-export-modal"] = createMockElement("options-export-modal");
domElements["options-import-modal"] = createMockElement("options-import-modal");
domElements["options-export-json-textarea"] = createMockElement("options-export-json-textarea");
domElements["options-import-json-textarea"] = createMockElement("options-import-json-textarea");
domElements["options-import-status"] = createMockElement("options-import-status");
domElements["btn-options-copy-json"] = createMockElement("btn-options-copy-json");

// Test 19: Cross-Device Options Portfolio Export Modal
// -----------------------------------------------------------------
assert(html.includes('id="options-export-modal"'), "Must have options export modal in DOM");
assert(html.includes('id="options-import-modal"'), "Must have options import modal in DOM");

context.toggleTradePortfolio('SPREAD', 'SPY', 'SPY 590/600 C', 2, 450, 580, 565, 595, 605, 'INDEX');
let optPort = context.getMyPortfolio();
assert(optPort['SPY_SPREAD'], "Must have SPY_SPREAD in options portfolio");

context.openOptionsExportModal();
const optExportVal = domElements['options-export-json-textarea'].value;
assert(optExportVal.includes('SPY_SPREAD'), "Exported JSON must contain SPY_SPREAD trade");
const parsedOptExport = JSON.parse(optExportVal);
assert.strictEqual(parsedOptExport['SPY_SPREAD'].ticker, 'SPY');
context.closeOptionsExportModal();
console.log("✔ Test 19: Options Portfolio JSON Export modal verified.");

// -----------------------------------------------------------------
// Test 20: Cross-Device Options Portfolio Import Modal
// -----------------------------------------------------------------
const testOptImportJSON = JSON.stringify({
    'NVDA_LEAPS': {
        id: 'NVDA_LEAPS',
        ticker: 'NVDA',
        contract: 'NVDA 120 C Jan2027',
        contracts: 1,
        costPerContract: 1800,
        totalCost: 1800,
        type: 'LEAPS',
        sector: 'TECH SEMIS'
    }
});

domElements['options-import-json-textarea'].value = testOptImportJSON;
context.importOptionsPortfolioJSON(false); // Merge mode
optPort = context.getMyPortfolio();
assert(optPort['SPY_SPREAD'], "SPY_SPREAD should still exist after merge");
assert(optPort['NVDA_LEAPS'], "NVDA_LEAPS should be merged into portfolio");

// Replace mode
domElements['options-import-json-textarea'].value = testOptImportJSON;
context.importOptionsPortfolioJSON(true); // Replace mode
optPort = context.getMyPortfolio();
assert(!optPort['SPY_SPREAD'], "SPY_SPREAD should be removed in replace mode");
assert(optPort['NVDA_LEAPS'], "NVDA_LEAPS should be sole remaining position in replace mode");
console.log("✔ Test 20: Options Portfolio JSON Import modal verified for merge and replace modes.");

console.log("\n========================================================");
console.log(" ALL 20 COMPREHENSIVE SIMULATION TESTS PASSED CLEANLY! ");
console.log("========================================================");


