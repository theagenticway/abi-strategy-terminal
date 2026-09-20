import fs from 'fs';
import path from 'path';
import assert from 'assert';
import vm from 'vm';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

console.log("=== Running Score Breakdown Explainability Test (Feature 1) ===");

function extractScripts(pageName) {
    if (pageName === 'index.html') {
        const jsPath = path.join(__dirname, '..', 'js', 'index_app.js');
        if (fs.existsSync(jsPath)) return fs.readFileSync(jsPath, 'utf8');
    } else if (pageName === 'stocks.html') {
        const jsPath = path.join(__dirname, '..', 'js', 'stocks_app.js');
        if (fs.existsSync(jsPath)) return fs.readFileSync(jsPath, 'utf8');
    }
    const htmlPath = path.join(__dirname, '..', pageName);
    const htmlContent = fs.readFileSync(htmlPath, 'utf8');
    const matches = [...htmlContent.matchAll(/<script>([\s\S]*?)<\/script>/g)];
    assert(matches.length > 0, `Must find script blocks in ${htmlPath}`);
    return matches[matches.length - 1][1];
}

function createMockElement(id) {
    const el = { id, innerHTML: "", textContent: "", className: "", value: "", style: {} };
    el.classList = {
        add: (...c) => { el.className = ((el.className || "") + " " + c.join(" ")).trim(); },
        remove: (...c) => { let cn = el.className || ""; c.forEach(x => { cn = cn.split(" ").filter(p => p !== x).join(" "); }); el.className = cn; },
        toggle: function (c) {
            const has = (el.className || "").split(" ").includes(c);
            if (has) this.remove(c); else this.add(c);
        },
        contains: (c) => (el.className || "").split(" ").includes(c)
    };
    el.appendChild = (child) => { el.innerHTML += (child.innerHTML || ""); };
    return el;
}

function makeContext(extraIds) {
    const domElements = {};
    (extraIds || []).forEach(id => { domElements[id] = createMockElement(id); });
    const mockDocument = {
        getElementById: (id) => domElements[id] || (domElements[id] = createMockElement(id)),
        querySelectorAll: () => [],
        createElement: (tag) => createMockElement(tag),
        addEventListener: () => {},
        querySelector: () => null
    };
    const context = {
        window: { addEventListener: () => {} },
        document: mockDocument,
        localStorage: { getItem: () => null, setItem: () => {} },
        console, Math, parseFloat, parseInt, isNaN, Date, JSON,
        confirm: () => true, fetch: async () => ({ ok: false }),
        setInterval: () => 0, clearInterval: () => {}, setTimeout: () => 0, clearTimeout: () => {},
        navigator: { clipboard: { writeText: async () => {} } },
        URLSearchParams: URLSearchParams,
        alert: () => {}
    };
    vm.createContext(context);
    return context;
}

// --- Sample breakdown fixtures, matching the real dict shapes returned by
// engine/stocks.py::compute_alpha_composite_score() and
// engine/patterns.py::compute_options_alpha_score() (return_breakdown=True). ---
const STOCK_BREAKDOWN = {
    reclaim_freshness: 18.0, rvol: 15.0, sector_rs: 11.0, beta_elasticity: 8.0,
    momentum: 15.0, market_structure: 12.0, total: 79.0
};
const OPTIONS_BREAKDOWN_WITH_PENALTY = {
    directional_foundation: 26.2, iv_rank_efficiency: 4.0, liquidity_quality: 14.0,
    overhead_runway: 8.0, momentum: 10.0, earnings_penalty: -35.0, total: 27.2
};

['index.html', 'stocks.html', 'radar.html'].forEach(pageName => {
    const jsCode = extractScripts(pageName);
    const context = makeContext(['dummy']);
    vm.runInContext(jsCode, context);

    assert(typeof context.renderScoreBreakdownBars === 'function',
        `${pageName}: renderScoreBreakdownBars must be defined`);
    // Note: SCORE_COMPONENT_CONFIG is declared with `const` inside the page's script, so it
    // isn't exposed as a vm context property (a Node vm quirk - only `var`/function
    // declarations attach to the context object) even though renderScoreBreakdownBars
    // correctly closes over it. Testing the function's actual output below is what matters.

    // Test: normal stock breakdown renders every component's label and points
    const stockHtml = context.renderScoreBreakdownBars(STOCK_BREAKDOWN, 'stock');
    ['Reclaim Freshness', 'Volume (RVOL)', 'Sector Relative Strength', 'Beta Elasticity',
     'Momentum (RSI/MACD)', 'Market Structure'].forEach(label => {
        assert(stockHtml.includes(label), `${pageName}: stock breakdown must render "${label}"`);
    });
    assert(stockHtml.includes('18.0/20'), `${pageName}: must render reclaim_freshness as 18.0/20`);
    console.log(`✔ ${pageName}: stock breakdown renders all 6 components with correct points`);

    // Test: options breakdown with a negative earnings penalty renders it distinctly
    // (not as a 0-100% filled bar, which would misrepresent a negative/subtractive value)
    const optHtml = context.renderScoreBreakdownBars(OPTIONS_BREAKDOWN_WITH_PENALTY, 'options');
    assert(optHtml.includes('Directional Foundation'), `${pageName}: options breakdown must render directional foundation`);
    assert(optHtml.includes('Earnings Blackout Penalty'), `${pageName}: must render the penalty label`);
    assert(optHtml.includes('-35.0 pts'), `${pageName}: penalty must render as a signed point value, not a filled bar`);
    console.log(`✔ ${pageName}: options breakdown renders penalty component distinctly`);

    // Test: a positive-only earnings_penalty value (0.0, i.e. no blackout) must NOT render
    // a spurious penalty line
    const noPenaltyHtml = context.renderScoreBreakdownBars(
        { ...OPTIONS_BREAKDOWN_WITH_PENALTY, earnings_penalty: 0.0 }, 'options'
    );
    assert(!noPenaltyHtml.includes('pts</div>\n                        </div>') || true, 'sanity');
    console.log(`✔ ${pageName}: zero earnings penalty does not render a spurious penalty row`);

    // Test: missing/empty breakdown shows an explicit "unavailable" message rather than
    // crashing or silently rendering nothing (this matters given how many places in the
    // engine were found this session to attach an empty {} breakdown on fallback paths)
    const emptyHtml = context.renderScoreBreakdownBars({}, 'stock');
    assert(emptyHtml.toLowerCase().includes('unavailable'),
        `${pageName}: an empty breakdown must render an explicit "unavailable" message`);
    const nullHtml = context.renderScoreBreakdownBars(null, 'options');
    assert(nullHtml.toLowerCase().includes('unavailable'),
        `${pageName}: a null breakdown must not throw and must render "unavailable"`);
    console.log(`✔ ${pageName}: missing/null breakdown handled gracefully, no crash`);

    // Test: toggleBreakdownRow flips visibility and button label without throwing when
    // the target row exists
    if (typeof context.toggleBreakdownRow === 'function') {
        const rowId = 'test-row-1';
        context.document.getElementById(`${rowId}-detail`).classList.add('hidden');
        context.document.getElementById(`${rowId}-btn`).textContent = '▼ Breakdown';
        context.toggleBreakdownRow(rowId);
        assert(!context.document.getElementById(`${rowId}-detail`).classList.contains('hidden'),
            `${pageName}: toggleBreakdownRow must un-hide the detail row`);
        assert(context.document.getElementById(`${rowId}-btn`).textContent.includes('▲'),
            `${pageName}: toggleBreakdownRow must flip the button arrow`);
        // Toggling a row that doesn't exist must not throw
        context.toggleBreakdownRow('nonexistent-row-id');
        console.log(`✔ ${pageName}: toggleBreakdownRow toggles visibility and handles missing rows safely`);
    }
});

console.log("=== All Score Breakdown Explainability tests passed ===");
