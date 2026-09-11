const fs = require('fs');
const path = require('path');
const assert = require('assert');

console.log("=== Running Comprehensive Node.js Stock Terminal Test ===");

const htmlPath = path.join(__dirname, '..', 'stocks.html');
assert(fs.existsSync(htmlPath), "stocks.html must exist");
const htmlContent = fs.readFileSync(htmlPath, 'utf8');

// Test 1: Navigation links to index.html with tab params
assert(htmlContent.includes('href="index.html?tab=macro"'), "Must link to index.html?tab=macro");
assert(htmlContent.includes('href="index.html?tab=recs"'), "Must link to index.html?tab=recs");
assert(htmlContent.includes('href="index.html?tab=perf"'), "Must link to index.html?tab=perf");
console.log("✔ Test 1: Navigation links to index.html with tab query parameters verified.");

// Test 2: Clean Equity terminology in markup
assert(htmlContent.includes('Tactical Equity Swings (50 EMA Reclaims — 1:2.5+ R/R)'), "Must have Tactical Equity Swings section");
assert(htmlContent.includes('Strategic Core Growth Accumulation (Common Shares)'), "Must have Strategic Core Growth Accumulation section");
assert(htmlContent.includes('Automated Stock Recommendation Audit & Outcome Ledger'), "Must have Stock Audit Ledger section");
console.log("✔ Test 2: Dedicated Equity sections and clean terminology verified.");

// Test 3: Extract JS logic and simulate DOM rendering
const scriptMatches = [...htmlContent.matchAll(/<script>([\s\S]*?)<\/script>/g)];
assert(scriptMatches.length > 0, "Must find script blocks");
const jsCode = scriptMatches[scriptMatches.length - 1][1];

// Mock DOM
const domElements = {};
function createMockElement(id) {
    const el = {
        id,
        innerHTML: "",
        textContent: "",
        className: "",
        value: "",
        style: {}
    };
    el.classList = {
        add: function(...classes) {
            el.className = ((el.className || "") + " " + classes.join(" ")).trim();
        },
        remove: function(...classes) {
            let cn = el.className || "";
            classes.forEach(c => {
                cn = cn.replace(new RegExp("\b" + c + "\b", "g"), "").trim();
            });
            el.className = cn;
        },
        toggle: function() {}
    };
    el.appendChild = function(child) {
        el.innerHTML += (child.innerHTML || "");
    };
    return el;
}

const mockIds = [
    'header-clock', 'header-timestamp', 'stock-view-recs-container', 'stock-view-perf-container',
    'btn-view-recs', 'btn-view-perf', 'stock-view-explainer', 'sector-nav-pills',
    'global-search-input', 'active-filter-banner', 'active-filter-label', 'briefing-verdict-badge',
    'briefing-regime-badge', 'idx-spy-price', 'idx-spy-status', 'idx-qqq-price', 'idx-qqq-status',
    'idx-rsp-price', 'idx-rsp-status', 'idx-iwm-price', 'idx-iwm-status', 'briefing-macro-narrative',
    'briefing-sector-narrative', 'briefing-mandates-list', 'scanner-funnel-container',
    'eq-alloc-architecture', 'eq-dry-powder-mode', 'equity-custom-capital',
    'eq-disp-total-cap', 'eq-disp-committed-cap', 'eq-disp-free-cash', 'eq-disp-core-budget',
    'eq-disp-tactical-budget', 'eq-my-port-badge', 'eq-swings-count', 'stock-swings-body',
    'eq-core-count', 'stock-core-body', 'eq-perf-total', 'eq-perf-open', 'eq-perf-closed',
    'eq-perf-winrate', 'eq-perf-pf', 'eq-perf-realized', 'eq-perf-floating', 'eq-perf-hold',
    'stock-ledger-count', 'stock-perf-search', 'stock-ledger-body', 'eq-sim-equity-val',
    'equity-export-modal', 'equity-import-modal', 'equity-export-json-textarea', 'equity-import-json-textarea',
    'equity-import-status', 'btn-equity-copy-json', 'btn-export-equity-json', 'btn-import-equity-json',
    'eq-ticker-search', 'eq-filter-qualified', 'eq-universe-body', 'btn-spfilt-all',
    'btn-spfilt-open', 'btn-spfilt-won', 'btn-spfilt-lost', 'btn-spfilt-my-port'
];

mockIds.forEach(id => {
    domElements[id] = createMockElement(id);
});

let mockLocalStorage = {};
const mockWindow = {
    addEventListener: () => {}
};
const mockDocument = {
    getElementById: (id) => domElements[id] || null,
    querySelectorAll: () => [],
    createElement: (tag) => createMockElement(tag)
};

const vm = require('vm');
const context = {
    window: mockWindow,
    document: mockDocument,
    localStorage: {
        getItem: (k) => mockLocalStorage[k] || null,
        setItem: (k, v) => { mockLocalStorage[k] = v; }
    },
    console: console,
    Math: Math,
    parseFloat: parseFloat,
    parseInt: parseInt,
    isNaN: isNaN,
    Date: Date,
    confirm: () => true, fetch: async () => ({ ok: false })
};

vm.createContext(context);
vm.runInContext(jsCode, context);

// Test 4: Load and render latest.json with Dynamic Alpha Ranking & Index Filtering
const latestData = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'latest.json'), 'utf8'));
context.currentPayload = latestData;
context.renderAll(latestData);

assert.strictEqual(domElements['eq-swings-count'].textContent, '5 Swings Qualified');
// Broad index filtering: SPY and QQQ must be excluded from tactical swings
assert(!domElements['stock-swings-body'].innerHTML.includes('SPY'), "Table 1 must NOT contain SPY (routed strictly to Core Accumulation)");
assert(!domElements['stock-swings-body'].innerHTML.includes('QQQ'), "Table 1 must NOT contain QQQ (routed strictly to Core Accumulation)");
// Must contain single-stock alpha setups and dynamic Alpha Score badges
assert(domElements['stock-swings-body'].innerHTML.includes('NVDA') || domElements['stock-swings-body'].innerHTML.includes('MS'), "Table 1 must contain top single-stock alpha candidates");
assert(domElements['stock-swings-body'].innerHTML.includes('ALPHA:'), "Table 1 must display Alpha Score badge");
console.log("✔ Test 3: Tactical Stock Swings rendered with dynamic multi-factor Alpha scoring & index filtering.");

// Test 5: Verify NO options terminology in stock table output
const swingHtml = domElements['stock-swings-body'].innerHTML.toLowerCase();
assert(!swingHtml.includes('contract'), "Stock swings table must NOT contain 'contract'");
assert(!swingHtml.includes('debit'), "Stock swings table must NOT contain 'debit'");
assert(!swingHtml.includes('call spread'), "Stock swings table must NOT contain 'call spread'");
assert(!swingHtml.includes('put spread'), "Stock swings table must NOT contain 'put spread'");
assert(!swingHtml.includes('leaps'), "Stock swings table must NOT contain 'leaps'");
console.log("✔ Test 4: Verified strict absence of options terminology in stock recommendations.");

// Test 6: Strategic Core Accumulation
assert.strictEqual(domElements['eq-core-count'].textContent, '5 Core Compounders');
assert(domElements['stock-core-body'].innerHTML.includes('SPY'), "Table 2 must contain SPY");
assert(domElements['stock-core-body'].innerHTML.includes('QQQ'), "Table 2 must contain QQQ");
assert(domElements['stock-core-body'].innerHTML.includes('MACRO STOP'), "Table 2 must contain macro stop");
console.log("✔ Test 5: Strategic Core common share accumulation rendered cleanly.");

// Test 7: Stock Performance Ledger
const stockLogData = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'stock_trades_log.json'), 'utf8'));
context.renderStockPerformanceView(stockLogData);

assert(parseInt(domElements['eq-perf-total'].textContent) >= 5, 'Must have at least 5 tracked trades');
assert(parseInt(domElements['eq-perf-open'].textContent) >= 1, 'Must have active open trades');
assert(domElements['stock-ledger-body'].innerHTML.includes('STOCK_2026-09-11_SPY') || domElements['stock-ledger-body'].innerHTML.includes('SPY'), "Ledger must show SPY");
console.log("✔ Test 6: Stock Performance Ledger rendered with 5 active stock trades.");

// Test 8: Subview Switcher
context.switchStockView('perf');
assert.strictEqual(context.activeStockView, 'perf');
context.switchStockView('recs');
assert.strictEqual(context.activeStockView, 'recs');
console.log("✔ Test 7: Subview Switcher toggles between Recommendations and Performance Ledger.");


// Test 9: Portfolio JSON Export and Import Portability
assert(htmlContent.includes('id="equity-export-modal"'), "Must have export modal in DOM");
assert(htmlContent.includes('id="equity-import-modal"'), "Must have import modal in DOM");

// Simulate adding a trade to portfolio
context.toggleEquityTrade('STOCK_NVDA_SWING', 'NVDA', 100, 92.89, 85.46, 111.47, 118.89, 'TECH SEMIS');
let port = context.getMyEquityPortfolio();
assert(port['STOCK_NVDA_SWING'], "Must have NVDA in portfolio");

// Test Export Modal
context.openEquityExportModal();
const exportText = domElements['equity-export-json-textarea'].value;
assert(exportText.includes('STOCK_NVDA_SWING'), "Exported JSON must contain NVDA trade");
const exportedObj = JSON.parse(exportText);
assert.strictEqual(exportedObj['STOCK_NVDA_SWING'].ticker, 'NVDA');
context.closeEquityExportModal();
console.log("✔ Test 8: Portfolio JSON Export modal generated valid backup schema.");

// Test Import Modal
const testImportJSON = JSON.stringify({
    'STOCK_MS_SWING': {
        tradeId: 'STOCK_MS_SWING',
        ticker: 'MS',
        shares: 83,
        price: 112.24,
        stop: 103.26,
        tp1: 134.69,
        tp2: 143.67,
        sector: 'FINANCIALS',
        capitalDeployed: 9315
    }
});
domElements['equity-import-json-textarea'].value = testImportJSON;
context.importEquityPortfolioJSON(false); // Merge mode
port = context.getMyEquityPortfolio();
assert(port['STOCK_NVDA_SWING'], "NVDA should still be present after merge");
assert(port['STOCK_MS_SWING'], "MS should be imported into portfolio");

// Replace mode
domElements['equity-import-json-textarea'].value = testImportJSON;
context.importEquityPortfolioJSON(true); // Replace mode
port = context.getMyEquityPortfolio();
assert(!port['STOCK_NVDA_SWING'], "NVDA should be replaced");
assert(port['STOCK_MS_SWING'], "MS should be only trade after replace");
console.log("✔ Test 9: Portfolio JSON Import modal verified for merge and replace modes.");

console.log("\n=========================================================");
console.log(" ALL STOCK TERMINAL NODE.JS SIMULATION TESTS PASSED! ");
console.log("=========================================================");
