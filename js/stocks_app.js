// State variables
        var currentPayload = null;
        var stockTradesData = { summary: {}, trades: [] };
        var activeStockView = 'recs';
        var activeStockProng = 'ALL';

        function setStockProngFilter(prong) {
            activeStockProng = prong;
            document.querySelectorAll('.stk-prong-btn').forEach(b => b.classList.remove('active', 'bg-blue-600', 'text-white'));
            if (prong === 'ALL') document.getElementById('btn-stk-prong-all')?.classList.add('active', 'bg-blue-600', 'text-white');
            if (prong === 'HIGH_RISK') document.getElementById('btn-stk-prong-hr')?.classList.add('active', 'bg-blue-600', 'text-white');
            if (prong === 'BALANCED') document.getElementById('btn-stk-prong-bal')?.classList.add('active', 'bg-blue-600', 'text-white');
            renderStockSwings();
        } // 'recs' or 'perf'
        var activeGlobalSector = '';
        var activeStockPerfFilter = 'ALL';
        var equityDeployCapital = 100000;
        var eqSimCapital = 50000;

        // Portfolio LocalStorage
        function getMyEquityPortfolio() {
            try {
                return JSON.parse(localStorage.getItem('myEquityPortfolio') || '{}');
            } catch (e) {
                return {};
            }
        }

        function saveMyEquityPortfolio(port) {
            localStorage.setItem('myEquityPortfolio', JSON.stringify(port));
            updateEquityAllocationPlan();
            renderStockSwings();
            renderStockCore();
            renderStockLedgerTable();
        }

        function toggleEquityTrade(tradeId, ticker, shares, price, stop, tp1, tp2, sector) {
            const port = getMyEquityPortfolio();
            if (port[tradeId]) {
                delete port[tradeId];
            } else {
                port[tradeId] = {
                    tradeId,
                    ticker,
                    shares,
                    price,
                    stop,
                    tp1,
                    tp2,
                    sector,
                    capitalDeployed: Math.round(shares * price),
                    dateAdded: new Date().toISOString().split('T')[0]
                };
            }
            saveMyEquityPortfolio(port);
        }

        function clearEquityPortfolioConfirm() {
            if (confirm('Clear all trades from My Stock Portfolio?')) {
                saveMyEquityPortfolio({});
            }
        }

        function resetEquityAllocator() {
            setEquityCapital(100000);
            document.getElementById('eq-alloc-architecture').value = 'balanced';
            document.getElementById('eq-dry-powder-mode').value = 'regime_adaptive';
            updateEquityAllocationPlan();
        }

        function switchStockView(view) {
            activeStockView = view;
            const recsEl = document.getElementById('stock-view-recs-container');
            const perfEl = document.getElementById('stock-view-perf-container');
            const btnRecs = document.getElementById('btn-view-recs');
            const btnPerf = document.getElementById('btn-view-perf');
            const expl = document.getElementById('stock-view-explainer');

            if (view === 'recs') {
                recsEl.classList.remove('hidden');
                perfEl.classList.add('hidden');
                btnRecs.className = 'subview-btn active px-3.5 py-1 rounded text-xs font-bold transition bg-blue-600 text-white shadow flex items-center gap-1.5';
                btnPerf.className = 'subview-btn px-3.5 py-1 rounded text-xs font-medium text-slate-400 hover:text-white transition flex items-center gap-1.5';
                if (expl) expl.textContent = 'Active Mode: Cash Equities, Fixed Dollar-at-Risk Sizing (1.5%) & 50 EMA Trailing Stops.';
            } else {
                recsEl.classList.add('hidden');
                perfEl.classList.remove('hidden');
                btnRecs.className = 'subview-btn px-3.5 py-1 rounded text-xs font-medium text-slate-400 hover:text-white transition flex items-center gap-1.5';
                btnPerf.className = 'subview-btn active px-3.5 py-1 rounded text-xs font-bold transition bg-blue-600 text-white shadow flex items-center gap-1.5';
                if (expl) expl.textContent = 'Audit Ledger: Tracking Execution & Performance from data/stock_trades_log.json';
                loadStockPerformanceData();
            }
        }

        function setEquityCapital(amt) {
            if (isNaN(amt) || amt <= 0) amt = 50000;
            equityDeployCapital = amt;
            document.querySelectorAll('.eq-cap-btn').forEach(b => b.classList.remove('active', 'bg-blue-600', 'text-white'));
            if (amt === 10000) document.getElementById('btn-eqcap-10k')?.classList.add('active', 'bg-blue-600', 'text-white');
            if (amt === 25000) document.getElementById('btn-eqcap-25k')?.classList.add('active', 'bg-blue-600', 'text-white');
            if (amt === 50000) document.getElementById('btn-eqcap-50k')?.classList.add('active', 'bg-blue-600', 'text-white');
            if (amt === 100000) document.getElementById('btn-eqcap-100k')?.classList.add('active', 'bg-blue-600', 'text-white');
            const inp = document.getElementById('equity-custom-capital');
            if (inp) inp.value = amt;
            updateEquityAllocationPlan();
        }

        function updateEquityAllocationPlan() {
            const port = getMyEquityPortfolio();
            let committedCapital = 0;
            let openPosCount = 0;
            Object.values(port).forEach(item => {
                committedCapital += (item.capitalDeployed || (item.shares * item.price) || 0);
                openPosCount++;
            });

            // Dynamic Dry Powder
            const dpMode = document.getElementById('eq-dry-powder-mode')?.value || 'regime_adaptive';
            let cashBufferPct = 0.25;
            if (dpMode === 'locked_15') cashBufferPct = 0.15;
            else if (dpMode === 'locked_25') cashBufferPct = 0.25;
            else if (dpMode === 'locked_35') cashBufferPct = 0.35;
            else {
                // Adaptive: check market commentary
                const verd = currentPayload?.market_commentary?.action_verdict || 'CAUTIOUS BUY';
                if (verd.includes('HOLD') || verd.includes('PRESERVE')) cashBufferPct = 0.35;
                else if (verd.includes('AGGRESSIVE')) cashBufferPct = 0.15;
                else cashBufferPct = 0.25;
            }

            const freeCashTarget = Math.round(equityDeployCapital * cashBufferPct);
            const deployableCapital = Math.max(0, equityDeployCapital - freeCashTarget);

            // Architecture
            const arch = document.getElementById('eq-alloc-architecture')?.value || 'balanced';
            let coreRatio = 0.60;
            let swingRatio = 0.40;
            if (arch === 'tactical') { coreRatio = 0.20; swingRatio = 0.80; }
            if (arch === 'secular') { coreRatio = 0.80; swingRatio = 0.20; }

            const coreBudget = Math.round(deployableCapital * coreRatio);
            const swingBudget = Math.round(deployableCapital * swingRatio);

            // Update DOM metrics cards
            const elTot = document.getElementById('eq-disp-total-cap');
            if (elTot) elTot.textContent = `$${equityDeployCapital.toLocaleString()}`;

            const elCom = document.getElementById('eq-disp-committed-cap');
            if (elCom) elCom.textContent = `$${committedCapital.toLocaleString()} (${openPosCount} pos)`;

            const elFree = document.getElementById('eq-disp-free-cash');
            if (elFree) elFree.textContent = `$${freeCashTarget.toLocaleString()} (${Math.round(cashBufferPct * 100)}%)`;

            const elCore = document.getElementById('eq-disp-core-budget');
            if (elCore) elCore.textContent = `$${coreBudget.toLocaleString()}`;

            const elSwing = document.getElementById('eq-disp-tactical-budget');
            if (elSwing) elSwing.textContent = `$${swingBudget.toLocaleString()}`;

            const elBadge = document.getElementById('eq-my-port-badge');
            if (elBadge) elBadge.textContent = openPosCount;

            renderStockSwings();
            renderStockCore();
        }

        // Data Loader
        async function loadLatestData(dateKey = 'latest') {
            try {
                const url = (dateKey === 'latest') ? './data/latest.json?t=' + Date.now() : `./data/history/${dateKey}.json`;
                const res = await fetch(url);
                if (!res.ok) throw new Error('Network error loading latest.json');
                currentPayload = await res.json();
                renderAll(currentPayload);
            } catch (err) {
                console.error('Failed to load latest.json:', err);
            }
        }

        async function loadStockPerformanceData() {
            try {
                const res = await fetch('./data/stock_trades_log.json?t=' + Date.now());
                if (!res.ok) throw new Error('Could not load stock_trades_log.json');
                stockTradesData = await res.json();
                renderStockPerformanceView(stockTradesData);
            } catch (e) {
                console.warn('Could not load stock trades log:', e);
            }
        }

        function renderAll(data) {
            if (!data) return;

            // Timestamp and clock
            const ts = data.macro_breadth?.timestamp || data.macro_breadth?.date || 'Live';
            const tsEl = document.getElementById('header-timestamp');
            if (tsEl) tsEl.textContent = `• data ${ts}`;

            renderExecutiveBriefing(data);
            renderSectorPills(data);
            renderFunnel(data);
            updateEquityAllocationPlan();
            renderUniverseTable();
        }

        function renderExecutiveBriefing(data) {
            const mc = data.market_commentary || {};
            const bm = data.benchmark_matrix || {};

            // Verdict
            const vEl = document.getElementById('briefing-verdict-badge');
            if (vEl) {
                vEl.textContent = mc.action_badge || mc.action_verdict || '🟡 CAUTIOUS BUY';
                if ((mc.action_verdict || '').includes('HOLD') || (mc.action_verdict || '').includes('PRESERVE')) {
                    vEl.className = 'px-3 py-1 rounded text-xs font-black bg-orange-950/80 text-orange-400 border border-orange-500/50 uppercase tracking-wide';
                } else if ((mc.action_verdict || '').includes('AGGRESSIVE')) {
                    vEl.className = 'px-3 py-1 rounded text-xs font-black bg-emerald-950/80 text-emerald-400 border border-emerald-500/50 uppercase tracking-wide';
                } else {
                    vEl.className = 'px-3 py-1 rounded text-xs font-black bg-amber-950/80 text-amber-400 border border-amber-500/50 uppercase tracking-wide';
                }
            }

            const regEl = document.getElementById('briefing-regime-badge');
            if (regEl) regEl.textContent = bm.regime || 'MIXED ROTATION';

            // Indices
            const idxs = bm.indices || {};
            ['SPY', 'QQQ', 'RSP', 'IWM'].forEach(sym => {
                const info = idxs[sym] || {};
                const pEl = document.getElementById(`idx-${sym.toLowerCase()}-price`);
                if (pEl) pEl.textContent = `$${parseFloat(info.price || 0).toFixed(2)}`;
                const sEl = document.getElementById(`idx-${sym.toLowerCase()}-status`);
                if (sEl) {
                    const isAbove = (info.status === 'ABOVE');
                    const pctStr = (info.vs_ema50_pct > 0 ? '+' : '') + parseFloat(info.vs_ema50_pct || 0).toFixed(2) + '%';
                    sEl.textContent = `● ${pctStr} (${isAbove ? 'Above' : 'Below'})`;
                    sEl.className = isAbove 
                        ? 'px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-950/60 text-emerald-400 border border-emerald-500/30'
                        : 'px-1.5 py-0.5 rounded text-[10px] font-bold bg-rose-950/60 text-rose-400 border border-rose-500/30';
                }
            });

            // Narratives
            const mEl = document.getElementById('briefing-macro-narrative');
            if (mEl) mEl.textContent = mc.macro_narrative || 'Macro regime indicates selective market expansion.';
            const sEl = document.getElementById('briefing-sector-narrative');
            if (sEl) sEl.textContent = mc.sector_flow_narrative || 'Capital concentration in strong sectors.';

            // Mandates
            const mandEl = document.getElementById('briefing-mandates-list');
            if (mandEl && mc.execution_mandates) {
                mandEl.innerHTML = mc.execution_mandates.map(m => `<li>${m}</li>`).join('');
            }
        }

        function renderFunnel(data) {
            const f = data.funnel_diagnostic || (data.macro_breadth && data.macro_breadth.funnel_diagnostic) || {
                scanned: 476, below_floor: 265, stale_reclaim: 30, wrong_retrace: 6, low_runway: 4, pending_eod: 0, qualified: (data.stock_recommendations || []).length
            };
            const fEl = document.getElementById('scanner-funnel-container');
            if (fEl) {
                fEl.innerHTML = `
                    <span class="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-bold">${f.scanned} Scanned</span>
                    <span class="text-slate-600">➔</span>
                    <span class="px-2 py-0.5 rounded bg-rose-950/40 text-rose-400 border border-rose-500/20">${f.below_floor} Below Floor</span>
                    <span class="text-slate-600">➔</span>
                    <span class="px-2 py-0.5 rounded bg-amber-950/40 text-amber-400 border border-amber-500/20">${f.stale_reclaim} Stale (>3d)</span>
                    <span class="text-slate-600">➔</span>
                    <span class="px-2 py-0.5 rounded bg-orange-950/40 text-orange-400 border border-orange-500/20">${f.low_runway || 0} Low Runway</span>
                    <span class="text-slate-600">➔</span>
                    <span class="px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-500/30 font-bold">${(data.stock_recommendations || []).length} Equity Qualified</span>
                `;
            }
        }

        function renderSectorPills(data) {
            const container = document.getElementById('sector-nav-pills');
            if (!container) return;
            const sectors = ['ALL', 'TECH SOFTWARE', 'MATERIALS', 'INDUSTRIALS', 'FINANCIALS', 'HEALTHCARE', 'ENERGY', 'TECH CORE', 'CONSUMER DISC', 'CONSUMER STAPLES', 'COMM SERVICES', 'UTILITIES', 'TECH SEMIS', 'REAL ESTATE', 'INDEX'];
            container.innerHTML = sectors.map(sec => {
                const isActive = (activeGlobalSector === (sec === 'ALL' ? '' : sec));
                return `<button onclick="filterBySector('${sec === 'ALL' ? '' : sec}')" class="tag-pill ${isActive ? 'active' : ''}">${sec}</button>`;
            }).join('');
        }

        function filterBySector(sec) {
            activeGlobalSector = sec.toUpperCase();
            renderSectorPills(currentPayload);
            const banner = document.getElementById('active-filter-banner');
            const label = document.getElementById('active-filter-label');
            if (activeGlobalSector) {
                if (banner) banner.classList.remove('hidden');
                if (label) label.textContent = activeGlobalSector;
            } else {
                if (banner) banner.classList.add('hidden');
            }
            renderStockSwings();
            renderStockCore();
            renderStockLedgerTable();
            renderUniverseTable();
        }

        function clearFilter() {
            activeGlobalSector = '';
            document.getElementById('global-search-input').value = '';
            document.getElementById('stock-perf-search').value = '';
            document.getElementById('eq-ticker-search').value = '';
            filterBySector('');
        }

        function handleGlobalSearch(val) {
            val = (val || '').toUpperCase().trim();
            activeGlobalSector = val;
            renderStockSwings();
            renderStockCore();
            renderStockLedgerTable();
            renderUniverseTable();
        }

        // ==========================================
        // RENDER TABLE 1: TACTICAL EQUITY SWINGS
        // ==========================================
        // ---------------------------------------------------------------
        // Score Breakdown Explainability (Feature 1) - see index.html for the
        // matching options-side implementation and full rationale comment.
        // ---------------------------------------------------------------
        const SCORE_COMPONENT_CONFIG = {
            stock: [
                { key: 'reclaim_freshness', label: 'Reclaim Freshness', max: 20 },
                { key: 'rvol', label: 'Volume (RVOL)', max: 20 },
                { key: 'sector_rs', label: 'Sector Relative Strength', max: 15 },
                { key: 'beta_elasticity', label: 'Beta Elasticity', max: 15 },
                { key: 'momentum', label: 'Momentum (RSI/MACD)', max: 15 },
                { key: 'market_structure', label: 'Market Structure', max: 15 }
            ],
            options: [
                { key: 'directional_foundation', label: 'Directional Foundation', max: 35 },
                { key: 'iv_rank_efficiency', label: 'IV Rank Efficiency', max: 20 },
                { key: 'liquidity_quality', label: 'Liquidity Quality', max: 20 },
                { key: 'overhead_runway', label: 'Overhead Runway', max: 15 },
                { key: 'momentum', label: 'Momentum Hook', max: 10 },
                { key: 'earnings_penalty', label: 'Earnings Blackout Penalty', max: 0, penalty: true }
            ]
        };
        function renderScoreBreakdownBars(breakdown, type) {
            const config = SCORE_COMPONENT_CONFIG[type] || [];
            if (!breakdown || Object.keys(breakdown).length === 0) {
                return `<div class="text-[10px] text-slate-500 italic py-1">Breakdown unavailable for this recommendation.</div>`;
            }
            return config.map(c => {
                const val = breakdown[c.key];
                if (val === undefined || val === null) return '';
                if (c.penalty) {
                    if (val >= 0) return '';
                    return `
                        <div class="flex items-center gap-2 py-0.5">
                            <div class="w-36 text-[10px] text-slate-400 shrink-0">${c.label}</div>
                            <div class="flex-1 text-[10px] font-mono font-bold text-rose-400">${val.toFixed(1)} pts</div>
                        </div>`;
                }
                const pct = Math.max(0, Math.min(100, (val / c.max) * 100));
                const barColor = pct >= 75 ? 'bg-emerald-500' : (pct >= 45 ? 'bg-amber-500' : 'bg-rose-500');
                return `
                    <div class="flex items-center gap-2 py-0.5">
                        <div class="w-36 text-[10px] text-slate-400 shrink-0">${c.label}</div>
                        <div class="flex-1 h-2 rounded bg-slate-800 overflow-hidden">
                            <div class="h-full ${barColor}" style="width:${pct}%"></div>
                        </div>
                        <div class="w-16 text-right text-[10px] font-mono text-slate-300 shrink-0">${val.toFixed(1)}/${c.max}</div>
                    </div>`;
            }).join('');
        }
        function buildBreakdownToggle(rowId) {
            return `<button onclick="toggleBreakdownRow('${rowId}')" id="${rowId}-btn" class="text-[9px] font-mono text-sky-400 hover:text-sky-300 underline decoration-dotted">▼ Score Breakdown</button>`;
        }
        function buildBreakdownRow(rowId, colspan, breakdown, type, totalScore) {
            const tr = document.createElement('tr');
            tr.id = `${rowId}-detail`;
            tr.className = 'hidden bg-slate-950/60';
            tr.innerHTML = `<td colspan="${colspan}" class="py-2 px-4">
                <div class="text-[10px] font-bold text-slate-400 mb-1">Alpha Score Breakdown — ${totalScore}/100 total</div>
                ${renderScoreBreakdownBars(breakdown, type)}
            </td>`;
            return tr;
        }
        function toggleBreakdownRow(rowId) {
            const row = document.getElementById(`${rowId}-detail`);
            const btn = document.getElementById(`${rowId}-btn`);
            if (!row) return;
            const isHidden = row.classList.contains('hidden');
            row.classList.toggle('hidden');
            if (btn) btn.textContent = isHidden ? '▲ Score Breakdown' : '▼ Score Breakdown';
        }

        function renderStockSwings() {
            const tbody = document.getElementById('stock-swings-body');
            if (!tbody) return;
            tbody.innerHTML = '';

            let recs = (currentPayload?.stock_recommendations) || [];
            if (activeGlobalSector) {
                recs = recs.filter(r => (r.sector || '').toUpperCase().includes(activeGlobalSector) || (r.subsector || '').toUpperCase().includes(activeGlobalSector) || r.ticker.toUpperCase() === activeGlobalSector);
            }
            if (activeStockProng !== 'ALL') {
                recs = recs.filter(r => (r.strategy_prong || 'BALANCED') === activeStockProng);
            }

            const countEl = document.getElementById('eq-swings-count');
            if (countEl) countEl.textContent = `${recs.length} Swings Qualified`;

            if (recs.length === 0) {
                tbody.innerHTML = '<tr><td colspan="10" class="py-4 text-center text-slate-500">No active tactical equity swing setups matching filter.</td></tr>';
                return;
            }

            const port = getMyEquityPortfolio();
            const riskPerTradeDollars = equityDeployCapital * 0.0045; // 0.45% dollar-at-risk per idea ($450 on $100k, $2,250 on $500k)
            const maxCapPerStock = equityDeployCapital * 0.06; // 6.0% max capital ceiling ($6,000 on $100k, $30,000 on $500k)

            recs.forEach((item, idx) => {
                const tradeId = `STOCK_${item.ticker}_SWING`;
                const isTaken = !!port[tradeId];
                const portItem = port[tradeId] || {};

                // Dynamic share calculation based on user's capital tier
                const riskPerShare = parseFloat(item.risk_per_share) || (parseFloat(item.price) - parseFloat(item.stop)) || (parseFloat(item.price) * 0.08);
                let dynamicShares = Math.floor(riskPerTradeDollars / riskPerShare);
                // Cap at 20% total equity
                if (dynamicShares * parseFloat(item.price) > maxCapPerStock) {
                    dynamicShares = Math.floor(maxCapPerStock / parseFloat(item.price));
                }
                dynamicShares = Math.max(1, dynamicShares);
                const capitalDeployed = Math.round(dynamicShares * parseFloat(item.price));
                const actualRiskDollars = Math.round(dynamicShares * riskPerShare);
                const riskPct = ((actualRiskDollars / equityDeployCapital) * 100).toFixed(2);

                const rankTitle = idx === 0 ? "Rank #1 — Primary Swing" : (idx === 1 ? "Rank #2 — Secondary Swing" : `Rank #${idx+1} — Tactical Swing`);
                const rankBadge = idx === 0 ? "bg-emerald-950/60 text-emerald-400 border border-emerald-500/30" : "bg-blue-950/60 text-blue-300 border border-blue-500/30";

                let portBtnHtml = '';
                if (isTaken) {
                    portBtnHtml = `<button onclick="toggleEquityTrade('${tradeId}', '${item.ticker}', ${portItem.shares || dynamicShares}, ${item.price}, ${item.stop}, ${item.tp1}, ${item.tp2}, '${item.sector}')" class="mt-1.5 w-full py-1 px-2 rounded text-[10px] font-bold bg-blue-600 text-white border border-blue-400 hover:bg-rose-600 transition flex items-center justify-center gap-1"><span>✓</span> In My Portfolio (${portItem.shares} sh · $${(portItem.capitalDeployed || Math.round(portItem.shares * item.price)).toLocaleString()})</button>`;
                } else {
                    portBtnHtml = `<button onclick="toggleEquityTrade('${tradeId}', '${item.ticker}', ${dynamicShares}, ${item.price}, ${item.stop}, ${item.tp1}, ${item.tp2}, '${item.sector}')" class="mt-1.5 w-full py-1 px-2 rounded text-[10px] font-bold bg-slate-800 text-sky-400 border border-slate-700 hover:bg-blue-600 hover:text-white transition flex items-center justify-center gap-1"><span>+</span> Mark as Taken (${dynamicShares} sh)</button>`;
                }

                const tr = document.createElement('tr');
                tr.className = 'hover:bg-slate-800/40 transition';
                tr.innerHTML = `
                    <td class="py-2.5 px-2.5 font-bold text-sky-400 text-xs">
                        <div class="text-sm">${item.ticker}</div>
                        <span class="px-1.5 py-0.2 rounded text-[9px] font-black bg-emerald-950/80 text-emerald-400 border border-emerald-500/40">BUY SHARES</span>
                        <div class="mt-1"><span class="px-1.5 py-0.2 rounded text-[8px] font-black ${item.strategy_prong === 'HIGH_RISK' ? 'bg-amber-950/90 text-amber-300 border border-amber-500/40' : 'bg-sky-950/90 text-sky-300 border border-sky-500/40'}">${item.prong_badge || (item.strategy_prong === 'HIGH_RISK' ? '🚀 HIGH RISK (SPRINT)' : '⚖️ BALANCED (SWING)')}</span></div>
                    </td>
                    <td class="py-2.5 px-2.5 text-slate-300">
                        <div class="font-semibold text-slate-200">${item.sector}</div>
                        <div class="text-[10px] text-slate-400">${item.subsector || ''}</div>
                    </td>
                    <td class="py-2.5 px-2.5 font-mono text-white font-bold">$${parseFloat(item.price).toFixed(2)}</td>
                    <td class="py-2.5 px-2.5 font-mono text-amber-400 font-semibold">
                        $${parseFloat(item.stop).toFixed(2)}
                        <div class="text-[9px] text-slate-500 font-mono">-${(((item.price - item.stop)/item.price)*100).toFixed(1)}%</div>
                    </td>
                    <td class="py-2.5 px-2.5 font-mono text-emerald-400 font-semibold">
                        <div>$${parseFloat(item.tp1).toFixed(2)} <span class="text-[9px] text-slate-400 font-normal">(Scale 50%)</span></div>
                        <div class="text-slate-300 text-[10px]">$${parseFloat(item.tp2).toFixed(2)} <span class="text-[9px] text-slate-500 font-normal">(50 EMA Trail)</span></div>
                    </td>
                    <td class="py-2.5 px-2.5 font-semibold text-amber-300">${item.rr_ratio || '1:2.5'}</td>
                    <td class="py-2.5 px-2.5">
                        <span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-950/60 text-emerald-400 border border-emerald-500/30">D${item.reclaim_days || 1} RECLAIM</span>
                        <div class="text-[10px] text-slate-300 mt-0.5">RVOL: <b class="text-white">${item.rvol || 1.0}x</b></div>
                        <div class="mt-1 flex flex-wrap gap-1 text-[8px] font-mono">
                            <span class="px-1 py-0.2 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-500/30">RSI: ${item.rsi || 52} (≥45 🟢)</span>
                            <span class="px-1 py-0.2 rounded bg-sky-950/80 text-sky-300 border border-sky-500/30">MACD: ↗ Hook</span>
                            <span class="px-1 py-0.2 rounded bg-purple-950/80 text-purple-300 border border-purple-500/30">β: ${item.beta || 1.2}</span>
                        </div>
                    </td>
                    <td class="py-2.5 px-2.5 text-[11px] font-mono">
                        <span class="px-1.5 py-0.5 rounded text-[10px] font-bold ${item.has_200sma === false ? 'bg-slate-800 text-slate-400 border border-slate-700' : 'bg-emerald-950/60 text-emerald-400 border border-emerald-500/30'}">${item.overhead_runway_label || (item.overhead_runway_pct !== null && item.overhead_runway_pct !== undefined ? (item.overhead_runway_pct >= 900 ? 'CLEAR (Above 200 SMA)' : item.overhead_runway_pct + '% Runway') : 'N/A (<200d History)')}</span>
                        ${item.structure_badge ? `<div class="mt-1"><span class="px-1.5 py-0.5 rounded text-[9px] font-black ${item.structure_badge.includes('HH/HL') ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-500/40' : (item.structure_badge.includes('BASE') ? 'bg-amber-950/80 text-amber-300 border border-amber-500/40' : 'bg-slate-800 text-slate-400')}">${item.structure_badge}</span></div>` : ''}
                    </td>
                    <td class="py-2.5 px-2.5 space-y-1">
                        <div><span class="px-1.5 py-0.5 rounded text-[9px] font-black ${rankBadge}">★ ${rankTitle}</span></div>
                        ${item.alpha_score !== undefined ? `<div class="mt-0.5"><span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-purple-950/60 text-purple-300 border border-purple-500/30">ALPHA: ${item.alpha_score}/100</span></div>` : ''}
                        <div class="text-xs font-mono font-bold text-white">Buy ${dynamicShares} Shares</div>
                        <div class="text-[10px] font-mono text-slate-400">$${capitalDeployed.toLocaleString()} deployed · ${riskPct}% risk ($${actualRiskDollars})</div>
                        ${portBtnHtml}
                    </td>
                    <td class="py-2.5 px-2.5">
                        <div class="font-mono font-bold text-emerald-400 text-xs">BUY ${dynamicShares} SHARES @ $${parseFloat(item.price).toFixed(2)} LIMIT · STOP @ $${parseFloat(item.stop).toFixed(2)}</div>
                        <div class="text-[10px] text-slate-300 font-mono mt-0.5">Scale 50% at TP1 ($${parseFloat(item.tp1).toFixed(2)}) · Move Stop to Breakeven · Trail on 50 EMA</div>
                        <div class="text-[10px] text-sky-400 font-mono mt-0.5">↳ Common stock cash swing · Direct equity ownership · No expiration or theta decay</div>
                        <div class="mt-1">${buildBreakdownToggle(`stockswing-${item.ticker}-${idx}`)}</div>
                    </td>
                `;
                tbody.appendChild(tr);
                tbody.appendChild(buildBreakdownRow(`stockswing-${item.ticker}-${idx}`, 10, item.alpha_score_breakdown, 'stock', item.alpha_score !== undefined ? item.alpha_score : 0));
            });
        }

        // ==========================================
        // RENDER TABLE 2: STRATEGIC CORE STOCKS
        // ==========================================
        function renderStockCore() {
            const tbody = document.getElementById('stock-core-body');
            if (!tbody) return;
            tbody.innerHTML = '';

            let core = (currentPayload?.core_stocks) || [];
            if (activeGlobalSector) {
                core = core.filter(r => (r.sector || '').toUpperCase().includes(activeGlobalSector) || (r.subsector || '').toUpperCase().includes(activeGlobalSector) || r.ticker.toUpperCase() === activeGlobalSector);
            }

            const countEl = document.getElementById('eq-core-count');
            if (countEl) countEl.textContent = `${core.length} Core Compounders`;

            if (core.length === 0) {
                tbody.innerHTML = '<tr><td colspan="9" class="py-4 text-center text-slate-500">No active strategic core growth setups matching filter.</td></tr>';
                return;
            }

            const port = getMyEquityPortfolio();
            const coreBudgetPerStock = Math.round((equityDeployCapital * 0.60 * 0.75) / Math.max(1, core.length));

            core.forEach((item, idx) => {
                const tradeId = `STOCK_${item.ticker}_CORE`;
                const isTaken = !!port[tradeId];
                const portItem = port[tradeId] || {};

                const shares = Math.max(1, Math.floor(coreBudgetPerStock / parseFloat(item.price)));
                const capitalDeployed = Math.round(shares * parseFloat(item.price));

                let portBtnHtml = '';
                if (isTaken) {
                    portBtnHtml = `<button onclick="toggleEquityTrade('${tradeId}', '${item.ticker}', ${portItem.shares || shares}, ${item.price}, ${item.macro_stop}, ${item.tp1}, ${item.tp2}, '${item.sector}')" class="mt-1.5 w-full py-1 px-2 rounded text-[10px] font-bold bg-sky-600 text-white border border-sky-400 hover:bg-rose-600 transition flex items-center justify-center gap-1"><span>✓</span> In My Portfolio (${portItem.shares} sh · $${(portItem.capitalDeployed || Math.round(portItem.shares * item.price)).toLocaleString()})</button>`;
                } else {
                    portBtnHtml = `<button onclick="toggleEquityTrade('${tradeId}', '${item.ticker}', ${shares}, ${item.price}, ${item.macro_stop}, ${item.tp1}, ${item.tp2}, '${item.sector}')" class="mt-1.5 w-full py-1 px-2 rounded text-[10px] font-bold bg-slate-800 text-sky-400 border border-slate-700 hover:bg-sky-600 hover:text-white transition flex items-center justify-center gap-1"><span>+</span> Mark as Taken (${shares} sh)</button>`;
                }

                const tr = document.createElement('tr');
                tr.className = 'hover:bg-slate-800/40 transition';
                tr.innerHTML = `
                    <td class="py-2.5 px-2.5 font-bold text-sky-400 text-xs">
                        <div>${item.ticker}</div>
                        <span class="px-1.5 py-0.2 rounded text-[9px] font-black bg-sky-950/80 text-sky-400 border border-sky-500/40">CORE STOCK</span>
                    </td>
                    <td class="py-2.5 px-2.5 text-slate-300">
                        <div class="font-semibold text-slate-200">${item.sector}</div>
                        <div class="text-[10px] text-slate-400">${item.subsector || ''}</div>
                    </td>
                    <td class="py-2.5 px-2.5 font-mono text-white font-bold">$${parseFloat(item.price).toFixed(2)}</td>
                    <td class="py-2.5 px-2.5 font-mono text-rose-400 font-semibold">
                        $${parseFloat(item.macro_stop).toFixed(2)}
                        <div class="text-[9px] text-slate-500 font-mono">3% below 200 SMA</div>
                    </td>
                    <td class="py-2.5 px-2.5 font-mono text-emerald-400 font-semibold">
                        <div>$${parseFloat(item.tp1).toFixed(2)} / $${parseFloat(item.tp2).toFixed(2)}</div>
                    </td>
                    <td class="py-2.5 px-2.5 font-semibold text-amber-300">${item.rr_ratio || '1:2.4'}</td>
                    <td class="py-2.5 px-2.5">
                        <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950/60 text-emerald-400 border border-emerald-500/30">${item.trend_stack || 'Price >= EMA50 >= SMA200'}</span>
                        <div class="text-[10px] text-slate-400 mt-1">Stage: <b class="text-white">${item.weekly_stage || 'STAGE 2 (Advancing)'}</b></div>
                    </td>
                    <td class="py-2.5 px-2.5 space-y-1">
                        <div class="text-xs font-mono font-bold text-white">Buy ${shares} Shares</div>
                        <div class="text-[10px] font-mono text-slate-400">$${capitalDeployed.toLocaleString()} capital commitment</div>
                        ${portBtnHtml}
                    </td>
                    <td class="py-2.5 px-2.5">
                        <div class="font-mono font-bold text-sky-300 text-xs">BUY ${shares} SHARES @ $${parseFloat(item.price).toFixed(2)} LIMIT · MACRO STOP @ $${parseFloat(item.macro_stop).toFixed(2)}</div>
                        <div class="text-[10px] text-slate-300 font-mono mt-0.5">${item.execution_guidance || 'Secular Core Hold · Macro Trailing Stop on 200 SMA · Quarterly Rebalance'}</div>
                        <div class="mt-1">${buildBreakdownToggle(`stockcore-${item.ticker}-${idx}`)}</div>
                    </td>
                `;
                tbody.appendChild(tr);
                tbody.appendChild(buildBreakdownRow(`stockcore-${item.ticker}-${idx}`, 9, item.alpha_score_breakdown, 'stock', item.alpha_score !== undefined ? item.alpha_score : 0));
            });
        }

        // ==========================================
        // RENDER VIEW 2: STOCK PERFORMANCE LEDGER
        // ==========================================
        function renderStockPerformanceView(logData) {
            if (!logData) return;
            stockTradesData = logData;
            const summary = logData.summary || {};
            const trades = logData.trades || [];

            // Metrics KPI Ribbon
            document.getElementById('eq-perf-total').textContent = summary.total_recommendations || trades.length || 0;
            document.getElementById('eq-perf-open').textContent = summary.active_open !== undefined ? summary.active_open : trades.filter(t => t.status === 'OPEN').length;
            const sprintCount = summary.sprint_open !== undefined ? summary.sprint_open : (trades.filter(t => (t.status === 'OPEN' || t.status === 'TP1_SCALED') && t.strategy_prong !== 'CORE').length);
            const anchorCount = summary.anchor_open !== undefined ? summary.anchor_open : (trades.filter(t => (t.status === 'OPEN' || t.status === 'TP1_SCALED') && t.strategy_prong === 'CORE').length);
            const eqDecoupledEl = document.getElementById('eq-decoupled-books');
            if (eqDecoupledEl) {
                eqDecoupledEl.textContent = `Sprint: ${sprintCount}/12 · Anchor: ${anchorCount}/6`;
            }
            document.getElementById('eq-perf-closed').textContent = summary.closed_trades !== undefined ? summary.closed_trades : trades.filter(t => t.status !== 'OPEN').length;
            document.getElementById('eq-perf-winrate').textContent = `${parseFloat(summary.win_rate_pct || 0).toFixed(1)}%`;
            document.getElementById('eq-perf-pf').textContent = parseFloat(summary.profit_factor || 0) > 0 ? `${parseFloat(summary.profit_factor).toFixed(2)}x` : '--';
            document.getElementById('eq-perf-realized').textContent = `$${parseFloat(summary.gross_realized_gain || 0).toFixed(2)}`;

            // Calculate floating unrealized gain
            let floatingGain = 0;
            trades.forEach(t => {
                if (t.status === 'OPEN' && t.current_price && t.entry_price && t.shares) {
                    floatingGain += (t.current_price - t.entry_price) * t.shares;
                }
            });
            const flEl = document.getElementById('eq-perf-floating');
            if (flEl) {
                flEl.textContent = (floatingGain >= 0 ? '+' : '') + `$${floatingGain.toFixed(2)}`;
                flEl.className = floatingGain >= 0 ? 'text-lg font-black text-emerald-400 font-mono mt-0.5' : 'text-lg font-black text-rose-400 font-mono mt-0.5';
            }

            document.getElementById('eq-perf-hold').textContent = `${parseFloat(summary.avg_holding_days || 5.0).toFixed(1)}d`;

            renderStockLedgerTable();
            runStockSimulation();
        }

        function setStockPerfFilter(f) {
            activeStockPerfFilter = f;
            document.querySelectorAll('[id^="btn-spfilt-"]').forEach(b => b.classList.remove('active'));
            const map = { 'ALL': 'all', 'OPEN': 'open', 'WON': 'won', 'LOST': 'lost', 'MY_PORTFOLIO': 'my-port' };
            document.getElementById(`btn-spfilt-${map[f]}`)?.classList.add('active');
            renderStockLedgerTable();
        }

        function renderStockLedgerTable() {
            const tbody = document.getElementById('stock-ledger-body');
            if (!tbody) return;
            tbody.innerHTML = '';

            let trades = (stockTradesData.trades) || [];
            const query = (document.getElementById('stock-perf-search')?.value || '').toLowerCase().trim();
            const port = getMyEquityPortfolio();

            if (query) {
                trades = trades.filter(t => t.ticker.toLowerCase().includes(query) || (t.sector || '').toLowerCase().includes(query) || (t.subsector || '').toLowerCase().includes(query));
            }
            if (activeGlobalSector) {
                trades = trades.filter(t => (t.sector || '').toUpperCase().includes(activeGlobalSector) || (t.subsector || '').toUpperCase().includes(activeGlobalSector));
            }

            // Filter status
            if (activeStockPerfFilter === 'OPEN') {
                trades = trades.filter(t => t.status === 'OPEN' || t.status === 'TP1_HIT');
            } else if (activeStockPerfFilter === 'WON') {
                trades = trades.filter(t => t.status === 'TP1_HIT' || t.status === 'TP2_HIT' || t.status === 'CLOSED_WIN');
            } else if (activeStockPerfFilter === 'LOST') {
                trades = trades.filter(t => t.status === 'STOPPED_OUT' || t.status === 'CLOSED_LOSS');
            } else if (activeStockPerfFilter === 'MY_PORTFOLIO') {
                trades = trades.filter(t => !!port[`STOCK_${t.ticker}_SWING`] || !!port[`STOCK_${t.ticker}_CORE`] || !!port[t.id]);
            }

            const countEl = document.getElementById('stock-ledger-count');
            if (countEl) countEl.textContent = `${trades.length} trades shown`;

            if (trades.length === 0) {
                tbody.innerHTML = '<tr><td colspan="16" class="py-4 text-center text-slate-500">No stock trades matching filter criteria.</td></tr>';
                return;
            }

            trades.forEach(t => {
                const tradeId = t.id || `STOCK_${t.ticker}_SWING`;
                const isTaken = !!port[tradeId] || !!port[`STOCK_${t.ticker}_SWING`] || !!port[`STOCK_${t.ticker}_CORE`];

                let statusBadge = '';
                if (t.status === 'OPEN') statusBadge = '<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-sky-950/60 text-sky-400 border border-sky-500/30">ACTIVE OPEN</span>';
                else if (t.status === 'TP1_HIT' || t.status === 'TP1_SCALED') statusBadge = '<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-950/60 text-emerald-400 border border-emerald-500/30">TP1 SCALED (+2.5 R)</span>';
                else if (t.status === 'TP2_HIT' || t.status === 'CLOSED_TRAILING_PROFIT') statusBadge = '<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-400/40">★ TARGET HIT</span>';
                else if (t.status === 'CLOSED_EVICTED') statusBadge = '<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-purple-950/60 text-purple-400 border border-purple-500/40">● EVICTED</span>';
                else if (t.status === 'CLOSED_BREAKEVEN') statusBadge = '<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-blue-950/60 text-blue-400 border border-blue-500/40">● BREAKEVEN</span>';
                else if (t.status === 'STAGNATION_EXIT') statusBadge = '<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-slate-800 text-slate-300 border border-slate-700">● STAGNATION</span>';
                else if (t.status === 'STOPPED_OUT') statusBadge = '<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-rose-950/60 text-rose-400 border border-rose-500/30">STOPPED OUT</span>';
                else statusBadge = `<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-slate-800 text-slate-300">${t.status}</span>`;

                let healthBadge = '';
                if (t.status === 'OPEN' || t.status === 'TP1_SCALED') {
                    if (t.active_health_tier === 'TIER_A_HOUSE_MONEY') {
                        healthBadge = `<div class="mt-0.5"><span class="px-1.5 py-0.2 rounded text-[8px] font-black bg-blue-950/90 text-blue-300 border border-blue-500/40">🔵 HOUSE MONEY${t.current_alpha_score ? ' (' + t.current_alpha_score + ')' : ''}</span></div>`;
                    } else if (t.active_health_tier === 'TIER_D_EVICTION_CANDIDATE') {
                        healthBadge = `<div class="mt-0.5"><span class="px-1.5 py-0.2 rounded text-[8px] font-black bg-rose-950/90 text-rose-300 border border-rose-500/40 animate-pulse">🔴 EVICTION READY${t.current_alpha_score ? ' (' + t.current_alpha_score + ')' : ''}</span></div>`;
                    } else if (t.active_health_tier === 'TIER_C_STAGNANT') {
                        healthBadge = `<div class="mt-0.5"><span class="px-1.5 py-0.2 rounded text-[8px] font-black bg-amber-950/90 text-amber-300 border border-amber-500/40">🟡 STAGNANT${t.current_alpha_score ? ' (' + t.current_alpha_score + ')' : ''}</span></div>`;
                    } else if (t.active_health_tier === 'TIER_B_ON_TRACK' || t.current_alpha_score) {
                        healthBadge = `<div class="mt-0.5"><span class="px-1.5 py-0.2 rounded text-[8px] font-black bg-emerald-950/90 text-emerald-300 border border-emerald-500/40">🟢 ON-TRACK${t.current_alpha_score ? ' (' + t.current_alpha_score + ')' : ''}</span></div>`;
                    }
                }

                const pnl = parseFloat(t.pnl_pct || 0);
                const pnlClass = pnl > 0 ? 'text-emerald-400 font-bold' : (pnl < 0 ? 'text-rose-400 font-bold' : 'text-slate-300 font-bold');

                const tr = document.createElement('tr');
                tr.className = 'hover:bg-slate-800/40 transition';
                tr.innerHTML = `
                    <td class="py-2.5 px-2.5 font-mono text-slate-400 text-xs">${t.entry_date}</td>
                    <td class="py-2.5 px-2.5 font-bold text-sky-400 text-xs">
                        <div>${t.ticker}</div>
                        ${t.strategy_prong ? `<div class="mt-0.5"><span class="px-1 py-0.2 rounded text-[8px] font-black ${t.strategy_prong === 'HIGH_RISK' ? 'bg-amber-950/80 text-amber-300 border border-amber-500/30' : 'bg-sky-950/80 text-sky-300 border border-sky-500/30'}">${t.strategy_prong === 'HIGH_RISK' ? '🚀 SPRINT' : '⚖️ SWING'}</span></div>` : ''}
                        ${healthBadge}
                        ${t.structure_badge ? `<div class="mt-0.5"><span class="px-1 py-0.2 rounded text-[8px] font-black ${t.structure_badge.includes('HH/HL') ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-500/30' : 'bg-amber-950/80 text-amber-300 border border-amber-500/30'}">${t.structure_badge}</span></div>` : ''}
                    </td>
                    <td class="py-2.5 px-2.5 text-slate-300">
                        <div>${t.sector}</div>
                        <div class="text-[9px] text-slate-500">${t.subsector || ''}</div>
                    </td>
                    <td class="py-2.5 px-2.5 font-mono font-bold text-white">${t.shares}</td>
                    <td class="py-2.5 px-2.5 font-mono text-white">$${parseFloat(t.entry_price).toFixed(2)}</td>
                    <td class="py-2.5 px-2.5 font-mono text-amber-400">$${parseFloat(t.stop_price).toFixed(2)}</td>
                    <td class="py-2.5 px-2.5 font-mono text-emerald-400">$${parseFloat(t.tp1).toFixed(2)} / $${parseFloat(t.tp2).toFixed(2)}</td>
                    <td class="py-2.5 px-2.5 font-mono text-white">$${parseFloat(t.current_price || t.exit_price || t.entry_price).toFixed(2)}</td>
                    <td class="py-2.5 px-2.5 font-mono ${pnlClass}">${pnl > 0 ? '+' : ''}${pnl.toFixed(2)}%</td>
                    <td class="py-2.5 px-2.5 font-mono text-slate-300">$${Math.round(t.capital_deployed || (t.shares * t.entry_price)).toLocaleString()}</td>
                    <td class="py-2.5 px-2.5 font-mono text-slate-400">$${Math.round(t.actual_risk_dollars || ((t.entry_price - t.stop_price) * t.shares)).toLocaleString()}</td>
                    <td class="py-2.5 px-2.5 font-mono text-slate-400">${t.days_active || 1}d</td>
                    <td class="py-2.5 px-2.5">${statusBadge}</td>
                    <td class="py-2.5 px-2.5 text-[10px] text-slate-300">${t.exit_reason || t.execution_guidance || 'Active 50 EMA tracking'}</td>
                    <td class="py-2.5 px-2.5 font-mono text-[10px] text-slate-400">${t.order_ticket || ''}</td>
                    <td class="py-2.5 px-2.5 text-center">
                        <button onclick="toggleEquityTrade('${tradeId}', '${t.ticker}', ${t.shares}, ${t.entry_price}, ${t.stop_price}, ${t.tp1}, ${t.tp2}, '${t.sector}')" class="px-2 py-0.5 rounded text-[9px] font-bold ${isTaken ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'}">
                            ${isTaken ? '✓ Added' : '+ Add'}
                        </button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        }

        // ==========================================
        // STOCK PORTFOLIO SIMULATOR
        // ==========================================
        function setEqSimCap(amt) {
            eqSimCapital = amt;
            document.querySelectorAll('[id^="btn-eqsim-"]').forEach(b => b.classList.remove('active', 'bg-blue-600', 'text-white'));
            const map = { 10000: '10k', 25000: '25k', 50000: '50k', 100000: '100k' };
            if (map[amt]) document.getElementById(`btn-eqsim-${map[amt]}`)?.classList.add('active', 'bg-blue-600', 'text-white');
            runStockSimulation();
        }

        function runStockSimulation() {
            const trades = (stockTradesData.trades) || [];
            let totalRealized = 0;
            let totalFloating = 0;

            trades.forEach(t => {
                const pnl = parseFloat(t.pnl_pct || 0) / 100;
                const stopDistPct = Math.max(0.02, Math.abs((t.entry_price - t.stop_price) / t.entry_price));
                const riskDollars = eqSimCapital * 0.0045; // 0.45% dollar-at-risk per trade ($450 on $100k)
                const maxCap = eqSimCapital * 0.06; // 6.0% max capital ceiling ($6,000 on $100k)
                const cappedSize = Math.min(riskDollars / stopDistPct, maxCap);

                if (t.status === 'OPEN' || t.status === 'TP1_HIT') {
                    totalFloating += (cappedSize * pnl);
                } else {
                    totalRealized += (cappedSize * pnl);
                }
            });

            const finalVal = eqSimCapital + totalRealized + totalFloating;
            const el = document.getElementById('eq-sim-equity-val');
            if (el) {
                const netPct = (((finalVal - eqSimCapital) / eqSimCapital) * 100).toFixed(2);
                el.innerHTML = `$${finalVal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} <span class="text-xs ${finalVal >= eqSimCapital ? 'text-emerald-400' : 'text-rose-400'}">(${netPct >= 0 ? '+' : ''}${netPct}%)</span>`;
            }
        }

        // ==========================================
        // RENDER FULL UNIVERSE TABLE
        // ==========================================
        function renderUniverseTable() {
            const tbody = document.getElementById('eq-universe-body');
            if (!tbody) return;
            tbody.innerHTML = '';

            let tickers = (currentPayload?.tickers) || [];
            const query = (document.getElementById('eq-ticker-search')?.value || '').toLowerCase().trim();
            const qual = document.getElementById('eq-filter-qualified')?.value || 'ALL';

            if (query) {
                tickers = tickers.filter(t => t.ticker.toLowerCase().includes(query) || (t.sector || '').toLowerCase().includes(query) || (t.subsector || '').toLowerCase().includes(query));
            }
            if (activeGlobalSector) {
                tickers = tickers.filter(t => (t.sector || '').toUpperCase().includes(activeGlobalSector) || (t.subsector || '').toUpperCase().includes(activeGlobalSector));
            }
            if (qual === 'YES') {
                tickers = tickers.filter(t => t.qualified === 'YES');
            } else if (qual === 'NO') {
                tickers = tickers.filter(t => t.qualified !== 'YES');
            }

            if (tickers.length === 0) {
                tbody.innerHTML = '<tr><td colspan="10" class="py-4 text-center text-slate-500">No stocks matching criteria.</td></tr>';
                return;
            }

            tickers.slice(0, 100).forEach(t => {
                const tr = document.createElement('tr');
                tr.className = 'hover:bg-slate-800/40 transition';
                tr.innerHTML = `
                    <td class="py-2 px-2.5 font-bold text-sky-400 font-mono">${t.ticker}</td>
                    <td class="py-2 px-2.5 text-slate-300">${t.sector}</td>
                    <td class="py-2 px-2.5 font-mono text-white">$${parseFloat(t.price).toFixed(2)}</td>
                    <td class="py-2 px-2.5 font-mono text-slate-400">$${parseFloat(t.ema50).toFixed(2)}</td>
                    <td class="py-2 px-2.5 font-mono ${t.ema50_pct > 0 ? 'text-emerald-400' : 'text-rose-400'} font-bold">${t.ema50_pct > 0 ? '+' : ''}${parseFloat(t.ema50_pct).toFixed(2)}%</td>
                    <td class="py-2 px-2.5 font-mono text-slate-300">${t.rsi ? parseFloat(t.rsi).toFixed(1) : '--'}</td>
                    <td class="py-2 px-2.5 font-mono text-slate-400">${t.adr || '--'}</td>
                    <td class="py-2 px-2.5 font-mono ${t.return_pct > 0 ? 'text-emerald-400' : 'text-rose-400'}">${t.return_pct > 0 ? '+' : ''}${parseFloat(t.return_pct || 0).toFixed(2)}%</td>
                    <td class="py-2 px-2.5"><span class="px-1.5 py-0.5 rounded text-[9px] font-bold ${t.state === 'RECLAIMED' ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-500/30' : 'bg-rose-950/60 text-rose-400 border border-rose-500/30'}">${t.state || 'BELOW'}</span></td>
                    <td class="py-2 px-2.5"><span class="px-1.5 py-0.5 rounded text-[9px] font-bold ${t.qualified === 'YES' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'bg-slate-800 text-slate-500'}">${t.qualified === 'YES' ? 'YES' : 'NO'}</span></td>
                `;
                tbody.appendChild(tr);
            });
        }

        // Live Clock
        function startClock() {
            function tick() {
                const now = new Date();
                const clockEl = document.getElementById('header-clock');
                if (clockEl) clockEl.textContent = now.toLocaleTimeString();
            }
            tick();
            setInterval(tick, 1000);
        }

        // Auto Refresh
        let refreshTimer = null;
        function setupAutoRefresh() {
            const select = document.getElementById('auto-refresh');
            if (!select) return;
            function restart() {
                if (refreshTimer) clearInterval(refreshTimer);
                const sec = parseInt(select.value);
                if (sec > 0) {
                    refreshTimer = setInterval(() => {
                        loadLatestData();
                        loadStockPerformanceData();
                    }, sec * 1000);
                }
            }
            select.addEventListener('change', restart);
            restart();
        }

        function refreshData() {
            loadLatestData();
            loadStockPerformanceData();
        }

        // Startup Initialization
        window.addEventListener('DOMContentLoaded', () => {
            startClock();
            setupAutoRefresh();
            loadLatestData();
            loadStockPerformanceData();
        });
    
        // ==========================================
        // CROSS-DEVICE PORTFOLIO PORTABILITY (JSON)
        // ==========================================
        function openEquityExportModal() {
            const port = getMyEquityPortfolio();
            const jsonStr = JSON.stringify(port, null, 2);
            const textarea = document.getElementById('equity-export-json-textarea');
            if (textarea) textarea.value = jsonStr;
            const modal = document.getElementById('equity-export-modal');
            if (modal) {
                modal.classList.remove('hidden');
                if (modal.style) modal.style.display = 'flex';
            }
        }

        function closeEquityExportModal() {
            const modal = document.getElementById('equity-export-modal');
            if (modal) {
                modal.classList.add('hidden');
                if (modal.style) modal.style.display = 'none';
            }
        }

        function copyEquityExportJSON() {
            const textarea = document.getElementById('equity-export-json-textarea');
            if (!textarea) return;
            const textToCopy = textarea.value;
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(textToCopy).then(() => {
                    const btn = document.getElementById('btn-equity-copy-json');
                    if (btn) {
                        const orig = btn.innerHTML;
                        btn.innerHTML = '✓ Copied!';
                        setTimeout(() => { btn.innerHTML = orig; }, 2000);
                    }
                }).catch(() => {
                    alert('Portfolio JSON copied to clipboard!');
                });
            } else {
                textarea.select();
                document.execCommand('copy');
                alert('Portfolio JSON copied to clipboard!');
            }
        }

        function downloadEquityExportJSON() {
            const textarea = document.getElementById('equity-export-json-textarea');
            if (!textarea) return;
            const blob = new Blob([textarea.value], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `my_equity_portfolio_${new Date().toISOString().split('T')[0]}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }

        function openEquityImportModal() {
            const textarea = document.getElementById('equity-import-json-textarea');
            if (textarea) textarea.value = '';
            const status = document.getElementById('equity-import-status');
            if (status) { status.className = 'text-xs hidden'; status.textContent = ''; }
            const modal = document.getElementById('equity-import-modal');
            if (modal) {
                modal.classList.remove('hidden');
                if (modal.style) modal.style.display = 'flex';
            }
        }

        function closeEquityImportModal() {
            const modal = document.getElementById('equity-import-modal');
            if (modal) {
                modal.classList.add('hidden');
                if (modal.style) modal.style.display = 'none';
            }
        }

        function handleEquityFileSelect(event) {
            const file = event.target.files && event.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = function(e) {
                const textarea = document.getElementById('equity-import-json-textarea');
                if (textarea) textarea.value = e.target.result;
            };
            reader.readAsText(file);
        }

        function importEquityPortfolioJSON(replaceMode = false) {
            const textarea = document.getElementById('equity-import-json-textarea');
            const status = document.getElementById('equity-import-status');
            if (!textarea) return;
            const raw = textarea.value.trim();
            if (!raw) {
                if (status) {
                    status.className = 'text-xs text-rose-400 block';
                    status.textContent = 'Please paste valid JSON or choose a file first.';
                }
                return;
            }
            try {
                let parsed = JSON.parse(raw);
                if (parsed && parsed.portfolio && typeof parsed.portfolio === 'object') {
                    parsed = parsed.portfolio;
                }
                if (typeof parsed !== 'object' || Array.isArray(parsed) || parsed === null) {
                    throw new Error('Portfolio JSON must be an object of trades.');
                }
                let current = replaceMode ? {} : getMyEquityPortfolio();
                let count = 0;
                for (const [k, v] of Object.entries(parsed)) {
                    if (v && typeof v === 'object') {
                        current[k] = v;
                        count++;
                    }
                }
                saveMyEquityPortfolio(current);
                if (status) {
                    status.className = 'text-xs text-emerald-400 block';
                    status.textContent = `Successfully ${replaceMode ? 'restored' : 'merged'} ${count} position(s)!`;
                }
                setTimeout(() => {
                    closeEquityImportModal();
                }, 1000);
            } catch (e) {
                if (status) {
                    status.className = 'text-xs text-rose-400 block';
                    status.textContent = 'Invalid JSON: ' + e.message;
                }
            }
        }