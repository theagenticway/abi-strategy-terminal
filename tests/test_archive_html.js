const fs = require('fs');
const path = require('path');
const assert = require('assert');

console.log("=== Testing archive.html Structure and Integration ===");

const archiveHtmlPath = path.join(__dirname, '../archive.html');
assert.ok(fs.existsSync(archiveHtmlPath), "archive.html must exist");

const html = fs.readFileSync(archiveHtmlPath, 'utf8');

// Check key DOM IDs
const requiredIds = [
    'header-clock',
    'header-count-badge',
    'stat-total',
    'stat-sprint',
    'stat-balanced',
    'stat-core',
    'stat-equities',
    'stat-hedges',
    'archive-search',
    'filter-asset',
    'filter-days',
    'filter-min-score',
    'archive-table-body',
    'filtered-count-badge'
];

for (const id of requiredIds) {
    assert.ok(html.includes(`id="${id}"`), `Missing required DOM element: #${id}`);
    console.log(`✔ DOM element #${id} verified`);
}

// Check cross-navigation links
assert.ok(html.includes('href="index.html?tab=recs"'), "Missing link to Options Alpha Radar");
assert.ok(html.includes('href="stocks.html"'), "Missing link to Equity Terminal");
assert.ok(html.includes('href="index.html?tab=macro"'), "Missing link to Macro Board");
console.log("✔ Navigation links to options and equity terminals verified");

// Check index.html and stocks.html navigation to archive.html
const indexHtml = fs.readFileSync(path.join(__dirname, '../index.html'), 'utf8');
const stocksHtml = fs.readFileSync(path.join(__dirname, '../stocks.html'), 'utf8');

assert.ok(indexHtml.includes('href="archive.html"'), "index.html missing link to archive.html");
assert.ok(stocksHtml.includes('href="archive.html"'), "stocks.html missing link to archive.html");
console.log("✔ index.html and stocks.html cross-navigation to archive.html verified");

// Check data/recommendations_archive.json loading
const archiveJsonPath = path.join(__dirname, '../data/recommendations_archive.json');
assert.ok(fs.existsSync(archiveJsonPath), "data/recommendations_archive.json must exist");
const data = JSON.parse(fs.readFileSync(archiveJsonPath, 'utf8'));
assert.ok(Array.isArray(data), "Archive JSON must be an array");
console.log(`✔ recommendations_archive.json verified (${data.length} records parsed successfully)`);

console.log("\n========================================================");
console.log(" ALL ARCHIVE MODULE HTML & JSON TESTS PASSED CLEANLY! ");
console.log("========================================================");
