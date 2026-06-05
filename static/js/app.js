/* ============ Cofre — app.js ============ */

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

/* ---------- API ---------- */
async function _req(method, p, body) {
  const opt = { method };
  if (body !== undefined) { opt.headers = { "Content-Type": "application/json" }; opt.body = JSON.stringify(body); }
  const r = await fetch("/api" + p, opt);
  if (r.status === 401) { window.location = "/login"; return new Promise(() => {}); }
  return r.json();
}
const api = {
  get: p => _req("GET", p),
  post: (p, b) => _req("POST", p, b || {}),
  put: (p, b) => _req("PUT", p, b || {}),
  del: p => _req("DELETE", p),
};

/* ---------- formatação ---------- */
const brl = n => (n < 0 ? "-" : "") + "R$ " + Math.abs(n).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const monthLabel = m => { const [y, mo] = m.split("-"); return new Date(y, mo - 1, 1).toLocaleDateString("pt-BR", { month: "long", year: "numeric" }); };
const monthsAhead = (iso, k) => { const [y, m, d] = iso.split("-").map(Number); const dt = new Date(y, m - 1 + k, 1); return dt.toLocaleDateString("pt-BR", { month: "short", year: "numeric" }); };
const dateBR = iso => { const [y, m, d] = iso.split("-"); return `${d}/${m}/${y}`; };
const todayISO = () => new Date().toISOString().slice(0, 10);
const clsAmt = n => n > 0 ? "pos" : n < 0 ? "neg" : "";

/* ---------- estado ---------- */
const state = {
  view: "dashboard",
  month: todayISO().slice(0, 7),
  accounts: [],
  categories: [],   // grupos com categorias
  chart: null,
};

async function loadRefs() {
  state.accounts = await api.get("/accounts");
  state.categories = await api.get("/categories");
}
function flatCategories() {
  const out = [];
  state.categories.forEach(g => g.categories.forEach(c => out.push({ ...c, group: g.name })));
  return out;
}

/* ---------- toast ---------- */
let toastT;
function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.classList.add("show");
  clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove("show"), 1800);
}

/* ---------- modal ---------- */
function openModal(html) { $("#modal").innerHTML = html; $("#modal-bg").classList.add("open"); }
function closeModal() { $("#modal-bg").classList.remove("open"); }
$("#modal-bg").addEventListener("click", e => { if (e.target.id === "modal-bg") closeModal(); });

/* ---------- navegação ---------- */
const TITLES = {
  dashboard: ["Painel", ""],
  budget: ["Orçamento", "Dê uma função a cada real"],
  transactions: ["Lançamentos", "Todas as entradas e saídas"],
  goals: ["Metas", "Objetivos por categoria"],
  calendar: ["Calendário", "Agenda financeira do mês"],
  cards: ["Cartões de Crédito", "Faturas, vencimentos e pagamentos"],
  forecast: ["Previsão de Orçamento", "Projeção dos próximos meses"],
  reports: ["Relatorios", "Evolucao de gastos por categoria"],
  health: ["Saude financeira", "Indicadores para acompanhar o rumo do dinheiro"],
  simulator: ["Simulador", "Teste compras, parcelas e metas antes de decidir"],
  networth: ["Patrimônio Líquido", "Tudo que você tem menos o que deve"],
  scheduled: ["Recorrentes & Previstos", "O que se repete ou está por vir"],
  accounts: ["Contas", "Seus saldos"],
  import: ["Importar Extrato", "CSV ou OFX do seu banco"],
  review: ["Revisão Semanal", "Um check-up rápido das finanças"],
  categories: ["Categorias", "Organize seus gastos"],
};
function setNav(view) {
  state.view = view;
  $$(".nav-item, .mobile-nav button").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  const [t, s] = TITLES[view] || [view, ""];
  $("#view-title").textContent = t; $("#view-sub").textContent = s;
}
function route(view) { setNav(view); render(); }
$$(".nav-item, .mobile-nav button").forEach(b => b.dataset.view && b.addEventListener("click", () => route(b.dataset.view)));

$("#fab").addEventListener("click", () => transactionModal());

/* ---------- render dispatcher ---------- */
async function render() {
  const el = $("#view"); el.innerHTML = '<div class="empty">Carregando…</div>';
  $("#topbar-actions").innerHTML = "";
  await loadRefs();
  ({ dashboard: renderDashboard, budget: renderBudget, transactions: renderTransactions,
     goals: renderGoals, calendar: renderCalendar,
     cards: renderCards, forecast: renderForecast, reports: renderReports,
     health: renderHealth, simulator: renderSimulator, networth: renderNetworth,
     scheduled: renderScheduled, accounts: renderAccounts, import: renderImport,
     review: renderReview, categories: renderCategories }[state.view] || renderDashboard)();
}

/* ============ PAINEL ============ */
async function renderDashboard() {
  const s = await api.get("/summary");
  const alerts = await api.get("/alerts");
  const insights = await api.get("/insights/month");
  const templates = await api.get("/templates");
  let nw = null;
  try { nw = (await api.get("/networth?months=2")).breakdown; } catch (e) {}
  const el = $("#view");
  el.innerHTML = `
    <div class="grid cards" style="margin-bottom:18px">
      <div class="card"><div class="label">Saldo total</div><div class="value num">${brl(s.total_balance)}</div></div>
      <div class="card"><div class="label">Entradas do mês</div><div class="value num pos">${brl(s.month_income)}</div></div>
      <div class="card"><div class="label">Saídas do mês</div><div class="value num neg">${brl(s.month_expense)}</div></div>
      ${nw ? `<div class="card" data-goto="networth" style="cursor:pointer"><div class="label">Patrimônio líquido</div><div class="value num">${brl(nw.net_worth)}</div></div>` : ""}
      <div class="card accent"><div class="label">Pronto para atribuir</div><div class="value num">${brl(s.ready_to_assign)}</div></div>
    </div>
    <div class="panel" style="margin-bottom:16px">
      <div class="panel-head"><h3>Alertas</h3>${alerts.length ? `<span class="tag">${alerts.length}</span>` : ""}</div>
      <div id="alerts"></div>
    </div>
    <div class="grid" style="grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px" id="dash-tools">
      <div class="panel">
        <div class="panel-head"><h3>Lançamento rápido</h3><button class="btn btn-sm" id="new-template">+ Modelo</button></div>
        <div id="quick-templates"></div>
      </div>
      <div class="panel">
        <div class="panel-head"><h3>Este mês</h3></div>
        <div id="month-insights"></div>
      </div>
    </div>
    <div class="grid" style="grid-template-columns:1.5fr 1fr;gap:16px" id="dash-grid">
      <div class="panel">
        <div class="panel-head"><h3>Entradas × Saídas (6 meses)</h3></div>
        <div class="chart-wrap"><canvas id="trendChart" height="170"></canvas></div>
      </div>
      <div class="panel">
        <div class="panel-head"><h3>Próximos previstos</h3></div>
        <div id="upcoming"></div>
      </div>
    </div>`;
  if (window.innerWidth < 820) $("#dash-grid").style.gridTemplateColumns = "1fr";
  if (window.innerWidth < 820) $("#dash-tools").style.gridTemplateColumns = "1fr";
  renderAlerts(alerts);
  renderQuickTemplates(templates);
  renderMonthInsights(insights);

  // próximos
  const up = $("#upcoming");
  if (!s.upcoming.length) up.innerHTML = '<div class="empty">Nenhum lançamento previsto.<br>Cadastre em "Recorrentes".</div>';
  else up.innerHTML = "<table><tbody>" + s.upcoming.map(u => `
    <tr><td>${dateBR(u.next_date)}<div style="color:var(--faint);font-size:12px">${u.payee || u.category_name || ""}</div></td>
    <td class="right num ${clsAmt(u.amount)}">${brl(u.amount)}</td></tr>`).join("") + "</tbody></table>";

  // gráfico
  const trend = await api.get("/reports/trend?months=6");
  drawTrend(trend);
  $$("[data-goto]").forEach(c => c.addEventListener("click", () => route(c.dataset.goto)));
}

function renderQuickTemplates(templates) {
  const el = $("#quick-templates");
  $("#new-template").addEventListener("click", () => templateModal());
  if (!templates.length) {
    el.innerHTML = '<div class="empty">Crie modelos para lançar gastos frequentes em um toque.</div>';
    return;
  }
  el.innerHTML = `<div class="quick-grid">${templates.slice(0, 8).map(t => `
    <button class="quick-tpl" data-post-template="${t.id}">
      <b>${esc(t.name)}</b>
      <small>${esc(t.category_name || t.account_name || "")}</small>
      <span class="num ${clsAmt(t.amount)}">${brl(t.amount)}</span>
    </button>`).join("")}</div>`;
  $$("[data-post-template]").forEach(b => b.addEventListener("click", async () => {
    await api.post(`/templates/${b.dataset.postTemplate}/post`, { date: todayISO() });
    toast("Lançado!");
    renderDashboard();
  }));
}

function renderMonthInsights(i) {
  const rows = [
    ["Maior gasto", i.biggest_expense ? `${i.biggest_expense.payee || i.biggest_expense.category_name || "Lançamento"} · ${brl(i.biggest_expense.amount)}` : "Sem gastos"],
    ["Categoria líder", i.top_category ? `${i.top_category.name} · ${brl(i.top_category.amount)}` : "Sem categoria"],
    ["Livre por dia", `${brl(i.daily_available)} por ${i.days_left} dia(s)`],
    ["Próxima entrada", i.next_income ? `${dateBR(i.next_income.next_date)} · ${brl(i.next_income.amount)}` : "Nenhuma prevista"],
  ];
  $("#month-insights").innerHTML = `<table><tbody>${rows.map(r => `<tr><td>${r[0]}</td><td class="right">${r[1]}</td></tr>`).join("")}</tbody></table>`;
}

function renderAlerts(alerts) {
  const el = $("#alerts");
  if (!alerts.length) {
    el.innerHTML = '<div class="empty">Nenhum alerta importante agora.</div>';
    return;
  }
  el.innerHTML = `<div class="alert-list">${alerts.map(a => `
    <button class="alert-item ${a.level}" ${a.view ? `data-alert-view="${a.view}"` : ""}>
      <span class="alert-dot"></span>
      <span class="alert-main">
        <b>${esc(a.title)}</b>
        <small>${esc(a.detail || "")}${a.due_date ? ` · ${dateBR(a.due_date)}` : ""}</small>
      </span>
      ${a.amount !== null ? `<span class="num ${clsAmt(a.amount)}">${brl(a.amount)}</span>` : ""}
    </button>`).join("")}</div>`;
  $$("[data-alert-view]").forEach(b => b.addEventListener("click", () => route(b.dataset.alertView)));
}

function drawTrend(trend) {
  if (state.chart) state.chart.destroy();
  const ctx = $("#trendChart"); if (!ctx) return;
  state.chart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: trend.map(t => { const [y, m] = t.month.split("-"); return m + "/" + y.slice(2); }),
      datasets: [
        { label: "Entradas", data: trend.map(t => t.income), backgroundColor: "#57d98a", borderRadius: 6 },
        { label: "Saídas", data: trend.map(t => t.expense), backgroundColor: "#f6776f", borderRadius: 6 },
      ],
    },
    options: {
      plugins: { legend: { labels: { color: "#98a1b2", font: { family: "Bricolage Grotesque" } } } },
      scales: {
        x: { ticks: { color: "#98a1b2" }, grid: { display: false } },
        y: { ticks: { color: "#98a1b2", callback: v => "R$" + v }, grid: { color: "#2a2f3a" } },
      },
    },
  });
}

/* ============ METAS ============ */
async function renderGoals() {
  $("#topbar-actions").innerHTML = `<button class="btn btn-gold" id="add-goal">+ Meta</button>`;
  $("#add-goal").addEventListener("click", () => goalModal());
  const goals = await api.get("/goals");
  $("#view").innerHTML = goals.length ? `<div class="grid cards">${goals.map(g => `
    <div class="card goal-card" data-goal="${g.id}" style="cursor:pointer">
      <div class="label">${esc(g.group_name || "Meta")}</div>
      <div style="font-weight:700;margin-top:8px">${esc(g.category_name)}</div>
      <div class="goal-bar"><span style="width:${g.progress}%"></span></div>
      <div style="display:flex;justify-content:space-between;gap:10px;margin-top:10px;color:var(--muted);font-size:13px">
        <span class="num">${brl(g.available)} / ${brl(g.target_amount)}</span>
        <b>${g.progress}%</b>
      </div>
      ${g.suggested_monthly !== null ? `<div style="color:var(--faint);font-size:12px;margin-top:8px">Sugestão: ${brl(g.suggested_monthly)}/mês até ${monthLabel(g.target_month)}</div>` : ""}
    </div>`).join("")}</div>` : '<div class="panel"><div class="empty">Nenhuma meta ainda.<br>Crie uma meta para uma categoria do orçamento.</div></div>';
  $$(".goal-card").forEach(c => c.addEventListener("click", () => goalModal(goals.find(g => g.id == c.dataset.goal))));
}

function goalModal(g = null) {
  const cats = flatCategories();
  if (!cats.length) { toast("Crie categorias primeiro."); route("categories"); return; }
  const isEdit = !!g;
  openModal(`
    <div class="modal-head"><h3>${isEdit ? "Editar" : "Nova"} meta</h3></div>
    <div class="modal-body">
      <div class="field"><label>Categoria</label><select id="goal-cat">${cats.map(c => `<option value="${c.id}" ${g && g.category_id == c.id ? "selected" : ""}>${c.group} › ${c.name}</option>`).join("")}</select></div>
      <div class="row2">
        <div class="field"><label>Valor alvo (R$)</label><input id="goal-amount" type="number" step="0.01" value="${g ? g.target_amount : ""}"></div>
        <div class="field"><label>Mês alvo</label><input id="goal-month" type="month" value="${g && g.target_month ? g.target_month : state.month}"></div>
      </div>
      <div class="field"><label>Observação</label><input id="goal-note" value="${g ? esc(g.note || "") : ""}"></div>
      <div class="modal-foot">
        ${isEdit ? '<button class="btn btn-ghost" id="goal-del" style="margin-right:auto;color:var(--red)">Excluir</button>' : ""}
        <button class="btn" onclick="closeModal()">Cancelar</button>
        <button class="btn btn-gold" id="goal-save">Salvar</button>
      </div>
    </div>`);
  $("#goal-save").addEventListener("click", async () => {
    const val = parseFloat(($("#goal-amount").value || "0").replace(",", ".")) || 0;
    if (!val) { toast("Informe o valor alvo."); return; }
    const body = { category_id: +$("#goal-cat").value, target_amount: val, target_month: $("#goal-month").value, note: $("#goal-note").value };
    if (isEdit) await api.put("/goals/" + g.id, body); else await api.post("/goals", body);
    closeModal(); toast("Meta salva!"); renderGoals();
  });
  if (isEdit) $("#goal-del").addEventListener("click", async () => {
    if (!confirm("Excluir esta meta?")) return;
    await api.del("/goals/" + g.id); closeModal(); toast("Meta excluída"); renderGoals();
  });
}

/* ============ ORÇAMENTO ============ */
async function renderBudget() {
  $("#topbar-actions").innerHTML = monthSwitcher() + ` <button class="btn btn-sm" id="copy-budget" title="Copiar orçamento de outro mês">⧉ Repetir</button>`;
  bindMonthSwitcher(renderBudget);
  $("#copy-budget").addEventListener("click", () => copyBudgetModal());
  const b = await api.get("/budget?month=" + state.month);
  const el = $("#view");
  let rows = "";
  b.groups.forEach(g => {
    if (!g.categories.length) return;
    rows += `<tr class="group-head"><td colspan="4">${g.name}</td></tr>`;
    g.categories.forEach(c => {
      const cls = c.available > 0 ? "avail-pos" : c.available < 0 ? "avail-neg" : "avail-zero";
      rows += `<tr>
        <td>${c.name}</td>
        <td class="right"><input class="assign-input num" data-cat="${c.id}" value="${c.assigned.toFixed(2)}"></td>
        <td class="right num ${clsAmt(c.activity)} hide-mobile">${brl(c.activity)}</td>
        <td class="right"><span class="avail-pill ${cls} num">${brl(c.available)}</span></td>
      </tr>`;
    });
  });
  const rtaCls = b.ready_to_assign < 0 ? "neg" : "";
  el.innerHTML = `
    <div class="rta-bar">
      <div><small>Pronto para atribuir</small><div class="amt num ${rtaCls}">${brl(b.ready_to_assign)}</div></div>
      <div style="text-align:right;color:var(--muted);font-size:13px">Atribuído: <b class="num">${brl(b.totals.assigned)}</b></div>
    </div>
    <div class="panel"><table>
      <thead><tr><th>Categoria</th><th class="right">Atribuído</th><th class="right hide-mobile">Movimento</th><th class="right">Disponível</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="4" class="empty">Crie categorias primeiro.</td></tr>'}</tbody>
    </table></div>
    <p style="color:var(--faint);font-size:12.5px;margin-top:12px">Dica: edite "Atribuído" e pressione Enter. O saldo positivo de uma categoria acumula para o mês seguinte (estilo YNAB).</p>`;

  $$(".assign-input").forEach(inp => {
    inp.addEventListener("keydown", e => { if (e.key === "Enter") inp.blur(); });
    inp.addEventListener("blur", async () => {
      const val = parseFloat(inp.value.replace(",", ".")) || 0;
      await api.post("/budget/assign", { category_id: +inp.dataset.cat, month: state.month, assigned: val });
      toast("Orçamento atualizado"); renderBudget();
    });
  });
}

function copyBudgetModal() {
  const prev = shiftMonthStr(state.month, -1);
  openModal(`
    <div class="modal-head"><h3>Repetir orçamento</h3>
      <div style="color:var(--muted);font-size:13px;margin-top:2px">Preencher ${monthLabel(state.month)} com valores de outro mês</div></div>
    <div class="modal-body">
      <div class="field"><label>Copiar valores de qual mês?</label>
        <input id="cb-source" type="month" value="${prev}"></div>
      <div class="field"><label>Como aplicar?</label>
        <div class="seg" id="cb-mode">
          <button type="button" data-mode="fill" class="on-income">Só preencher vazias</button>
          <button type="button" data-mode="overwrite">Substituir tudo</button>
        </div>
        <div id="cb-hint" style="color:var(--faint);font-size:12px;margin-top:8px">Mantém o que você já ajustou neste mês e preenche só as categorias ainda zeradas.</div>
      </div>
      <div class="modal-foot">
        <button class="btn" onclick="closeModal()">Cancelar</button>
        <button class="btn btn-gold" id="cb-save">Repetir orçamento</button></div>
    </div>`);
  let mode = "fill";
  $$("#cb-mode button").forEach(btn => btn.addEventListener("click", () => {
    mode = btn.dataset.mode;
    $$("#cb-mode button").forEach(x => x.classList.toggle("on-income", x.dataset.mode === mode));
    $("#cb-hint").textContent = mode === "fill"
      ? "Mantém o que você já ajustou neste mês e preenche só as categorias ainda zeradas."
      : "Substitui todos os valores deste mês pelos do mês de origem.";
  }));
  $("#cb-save").addEventListener("click", async () => {
    const source = $("#cb-source").value;
    if (source === state.month) { toast("Escolha um mês diferente do atual."); return; }
    const r = await api.post("/budget/copy", { target: state.month, source, mode });
    closeModal();
    toast(r.copied ? `${r.copied} categoria(s) preenchida(s)` : "Nada a copiar");
    renderBudget();
  });
}

function shiftMonthStr(month, k) {
  const [y, m] = month.split("-").map(Number);
  const total = y * 12 + (m - 1) + k;
  return `${String(Math.floor(total / 12)).padStart(4, "0")}-${String(total % 12 + 1).padStart(2, "0")}`;
}


/* ============ LANÇAMENTOS ============ */
async function renderTransactions() {
  $("#topbar-actions").innerHTML =
    `<input id="txn-search" class="btn" style="background:var(--surface);width:180px" placeholder="Buscar…">
     <button class="btn btn-sm" id="tpl-btn">Modelos</button>
     <button class="btn btn-gold" id="add-txn">+ Lançamento</button>`;
  $("#add-txn").addEventListener("click", () => transactionModal());
  $("#tpl-btn").addEventListener("click", () => templateModal());
  const search = $("#txn-search");
  search.addEventListener("input", () => { clearTimeout(search._t); search._t = setTimeout(loadTxns, 300); });

  $("#view").innerHTML = `<div class="panel"><div id="txn-list"></div></div>`;
  loadTxns();

  async function loadTxns() {
    const s = search.value ? "&search=" + encodeURIComponent(search.value) : "";
    const txns = await api.get("/transactions?limit=300" + s);
    const list = $("#txn-list");
    if (!txns.length) { list.innerHTML = '<div class="empty">Nenhum lançamento ainda.<br>Toque em "+ Lançamento".</div>'; return; }
    list.innerHTML = "<table><thead><tr><th>Data</th><th>Descrição</th><th class='hide-mobile'>Categoria</th><th class='hide-mobile'>Conta</th><th class='right'>Valor</th></tr></thead><tbody>" +
      txns.map(t => `<tr data-id="${t.id}" class="txn-row" style="cursor:pointer">
        <td class="num">${dateBR(t.date)}</td>
        <td>${t.payee || "—"}${t.installment_total > 1 ? ` <span class="tag" style="font-size:10px;background:rgba(108,182,240,.15);color:var(--blue)">${t.installment_num}/${t.installment_total}</span>` : ""}${t.memo ? `<div style="color:var(--faint);font-size:12px">${t.memo}</div>` : ""}</td>
        <td class="hide-mobile">${t.category_name ? `<span class="tag">${t.category_name}</span>` : (t.amount > 0 ? '<span class="tag">Renda</span>' : "—")}</td>
        <td class="hide-mobile" style="color:var(--muted)">${t.account_name}</td>
        <td class="right num ${clsAmt(t.amount)}">${brl(t.amount)}</td>
      </tr>`).join("") + "</tbody></table>";
    $$(".txn-row").forEach(r => r.addEventListener("click", () => {
      const t = txns.find(x => x.id == r.dataset.id); transactionModal(t);
    }));
  }
}

function transactionModal(t = null) {
  if (!state.accounts.length) { toast("Crie uma conta primeiro."); route("accounts"); return; }
  const isEdit = !!t;
  const amount = t ? Math.abs(t.amount) : "";
  const isExpense = t ? t.amount < 0 : true;
  const cats = flatCategories();
  const isInstallment = t && t.installment_total > 1;
  openModal(`
    <div class="modal-head"><h3>${isEdit ? "Editar" : "Novo"} lançamento</h3>
      ${isInstallment ? `<div style="color:var(--muted);font-size:13px;margin-top:2px">Parcela ${t.installment_num} de ${t.installment_total}</div>` : ""}</div>
    <div class="modal-body">
      <div class="seg" id="seg-type">
        <button type="button" data-type="expense" class="${isExpense ? "on-expense" : ""}">Saída</button>
        <button type="button" data-type="income" class="${!isExpense ? "on-income" : ""}">Entrada</button>
      </div>
      <div class="field"><label>${isEdit ? "Valor (R$)" : "Valor total (R$)"}</label><input id="f-amount" type="number" step="0.01" inputmode="decimal" value="${amount}" placeholder="0,00"></div>
      ${isEdit ? "" : `<div class="field" id="inst-field">
        <label>Parcelas</label>
        <select id="f-inst">${Array.from({length: 48}, (_, i) => i + 1).map(n => `<option value="${n}">${n === 1 ? "À vista (1x)" : n + "x"}</option>`).join("")}</select>
        <div id="inst-hint" style="color:var(--faint);font-size:12px;margin-top:6px;display:none"></div>
      </div>`}
      <div class="row2">
        <div class="field"><label>${isEdit ? "Data" : "Data da 1ª parcela"}</label><input id="f-date" type="date" value="${t ? t.date : todayISO()}"></div>
        <div class="field"><label>Conta</label><select id="f-account">${state.accounts.map(a => `<option value="${a.id}" ${t && t.account_id == a.id ? "selected" : ""}>${a.name}</option>`).join("")}</select></div>
      </div>
      <div class="field" id="cat-field"><label>Categoria</label><select id="f-cat"><option value="">— Sem categoria (renda) —</option>${cats.map(c => `<option value="${c.id}" ${t && t.category_id == c.id ? "selected" : ""}>${c.group} › ${c.name}</option>`).join("")}</select></div>
      ${isEdit ? "" : `<div id="split-tools">
        <button type="button" class="btn btn-sm" id="split-toggle">Dividir em categorias</button>
        <div id="split-box" style="display:none;margin-top:10px">
          <div class="split-head">
            <span>Divisões</span><span id="split-total" class="num">R$ 0,00</span>
          </div>
          <div id="split-rows"></div>
          <button type="button" class="btn btn-sm" id="split-add" style="margin-top:8px">+ Linha</button>
        </div>
      </div>`}
      <div class="field"><label>Descrição</label><input id="f-payee" value="${t ? esc(t.payee) : ""}" placeholder="Ex.: Mercado Pão de Açúcar"></div>
      <div class="field"><label>Observação</label><input id="f-memo" value="${t ? esc(t.memo) : ""}"></div>
      <div class="modal-foot">
        ${isEdit ? '<button class="btn btn-ghost" id="del-txn" style="margin-right:auto;color:var(--red)">Excluir</button>' : ""}
        <button class="btn" onclick="closeModal()">Cancelar</button>
        <button class="btn btn-gold" id="save-txn">Salvar</button>
      </div>
    </div>`);

  let type = isExpense ? "expense" : "income";
  const updateType = () => {
    $$("#seg-type button").forEach(b => { b.classList.remove("on-expense", "on-income"); if (b.dataset.type === type) b.classList.add(type === "expense" ? "on-expense" : "on-income"); });
    if (!isEdit && type === "income" && splitActive) toggleSplit(false);
  };
  $$("#seg-type button").forEach(b => b.addEventListener("click", () => { type = b.dataset.type; updateType(); }));

  let splitActive = false;
  const catOptions = '<option value="">— Categoria —</option>' + cats.map(c => `<option value="${c.id}">${c.group} › ${c.name}</option>`).join("");
  const addSplitRow = (amount = "") => {
    const rows = $("#split-rows");
    const div = document.createElement("div");
    div.className = "split-row";
    div.innerHTML = `<select class="split-cat">${catOptions}</select>
      <input class="split-amount num" type="number" step="0.01" inputmode="decimal" value="${amount}" placeholder="0,00">
      <button type="button" class="icon-btn split-del" title="Remover">×</button>`;
    rows.appendChild(div);
    div.querySelector(".split-del").addEventListener("click", () => { div.remove(); updateSplitTotal(); });
    div.querySelector(".split-amount").addEventListener("input", updateSplitTotal);
  };
  const updateSplitTotal = () => {
    const sum = $$(".split-amount").reduce((acc, inp) => acc + (parseFloat((inp.value || "0").replace(",", ".")) || 0), 0);
    const total = parseFloat(($("#f-amount").value || "0").replace(",", ".")) || 0;
    const label = $("#split-total");
    if (!label) return;
    label.textContent = `${brl(sum)} / ${brl(total)}`;
    label.classList.toggle("neg", Math.round(sum * 100) !== Math.round(total * 100));
  };
  const toggleSplit = on => {
    splitActive = on;
    $("#split-box").style.display = on ? "block" : "none";
    $("#cat-field").style.display = on ? "none" : "block";
    $("#split-toggle").textContent = on ? "Usar uma categoria" : "Dividir em categorias";
    if (on && !$(".split-row")) {
      const total = parseFloat(($("#f-amount").value || "0").replace(",", ".")) || 0;
      addSplitRow(total ? total.toFixed(2) : "");
      addSplitRow("");
    }
    updateSplitTotal();
  };
  if (!isEdit) {
    $("#split-toggle").addEventListener("click", () => {
      if (type === "income") { toast("Divisão está disponível para saídas."); return; }
      toggleSplit(!splitActive);
    });
    $("#split-add").addEventListener("click", () => addSplitRow(""));
    $("#f-amount").addEventListener("input", updateSplitTotal);
  }

  // Dica dinâmica de parcelamento (valor por parcela).
  const updateHint = () => {
    if (isEdit) return;
    const n = +$("#f-inst").value;
    const val = parseFloat(($("#f-amount").value || "0").replace(",", ".")) || 0;
    const hint = $("#inst-hint");
    if (n > 1 && val > 0) {
      hint.style.display = "block";
      hint.textContent = `${n}x de ${brl(val / n)} — total ${brl(val)}, terminando em ${monthsAhead($("#f-date").value, n - 1)}`;
    } else {
      hint.style.display = "none";
    }
  };
  if (!isEdit) {
    $("#f-inst").addEventListener("change", updateHint);
    $("#f-amount").addEventListener("input", updateHint);
    $("#f-date").addEventListener("change", updateHint);
  }

  $("#save-txn").addEventListener("click", async () => {
    const val = parseFloat($("#f-amount").value.replace(",", ".")) || 0;
    if (!val) { toast("Informe um valor."); return; }
    const body = {
      account_id: +$("#f-account").value,
      category_id: $("#f-cat").value ? +$("#f-cat").value : null,
      date: $("#f-date").value, payee: $("#f-payee").value, memo: $("#f-memo").value,
      amount: type === "expense" ? -Math.abs(val) : Math.abs(val),
    };
    if (!isEdit && splitActive) {
      const splits = $$(".split-row").map(row => ({
        category_id: $(".split-cat", row).value ? +$(".split-cat", row).value : null,
        amount: parseFloat(($(".split-amount", row).value || "0").replace(",", ".")) || 0,
      })).filter(x => x.amount > 0);
      const splitTotal = splits.reduce((acc, x) => acc + x.amount, 0);
      if (Math.round(splitTotal * 100) !== Math.round(val * 100)) {
        toast("A soma das divisões precisa bater com o total.");
        return;
      }
      body.splits = splits;
      body.category_id = null;
    }
    if (isEdit) {
      await api.put("/transactions/" + t.id, body);
    } else {
      const inst = +$("#f-inst").value;
      if (inst > 1) body.installments = inst;
      const res = await api.post("/transactions", body);
      if (res.error) { toast(res.error); return; }
      if (res.splits) { closeModal(); toast(`${res.splits} divisões salvas!`); render(); return; }
      if (res.installments > 1) { closeModal(); toast(`${res.installments} parcelas criadas!`); render(); return; }
    }
    closeModal(); toast("Salvo!"); render();
  });
  if (isEdit) $("#del-txn").addEventListener("click", async () => {
    if (isInstallment) {
      const all = confirm(`Esta é a parcela ${t.installment_num}/${t.installment_total}.\n\nOK = excluir TODAS as ${t.installment_total} parcelas.\nCancelar = volto e você escolhe.`);
      if (all) {
        await api.del(`/transactions/${t.id}?scope=all`);
        closeModal(); toast("Parcelamento excluído"); render();
      }
      return;
    }
    if (!confirm("Excluir este lançamento?")) return;
    await api.del("/transactions/" + t.id); closeModal(); toast("Excluído"); render();
  });
}

async function templateModal(t = null) {
  if (!state.accounts.length) { toast("Crie uma conta primeiro."); route("accounts"); return; }
  const templates = await api.get("/templates");
  const cats = flatCategories();
  const isEdit = !!t;
  const cur = t || { amount: "", account_id: state.accounts[0].id, category_id: "", name: "", payee: "", memo: "" };
  openModal(`
    <div class="modal-head"><h3>${isEdit ? "Editar" : "Novo"} modelo</h3></div>
    <div class="modal-body">
      ${!isEdit && templates.length ? `<div class="quick-grid">${templates.map(x => `
        <button type="button" class="quick-tpl" data-edit-template="${x.id}">
          <b>${esc(x.name)}</b><small>${esc(x.category_name || x.account_name || "")}</small>
          <span class="num ${clsAmt(x.amount)}">${brl(x.amount)}</span>
        </button>`).join("")}</div>` : ""}
      <div class="field"><label>Nome do atalho</label><input id="tpl-name" value="${esc(cur.name)}" placeholder="Ex.: Mercado, Uber, Almoço"></div>
      <div class="field"><label>Valor padrão (R$)</label><input id="tpl-amount" type="number" step="0.01" value="${cur.amount ? Math.abs(cur.amount) : ""}"></div>
      <div class="row2">
        <div class="field"><label>Conta</label><select id="tpl-account">${state.accounts.map(a => `<option value="${a.id}" ${cur.account_id == a.id ? "selected" : ""}>${a.name}</option>`).join("")}</select></div>
        <div class="field"><label>Tipo</label><select id="tpl-type"><option value="expense" ${cur.amount <= 0 ? "selected" : ""}>Saída</option><option value="income" ${cur.amount > 0 ? "selected" : ""}>Entrada</option></select></div>
      </div>
      <div class="field"><label>Categoria</label><select id="tpl-cat"><option value="">— Sem categoria —</option>${cats.map(c => `<option value="${c.id}" ${cur.category_id == c.id ? "selected" : ""}>${c.group} › ${c.name}</option>`).join("")}</select></div>
      <div class="field"><label>Descrição</label><input id="tpl-payee" value="${esc(cur.payee || "")}"></div>
      <div class="field"><label>Observação</label><input id="tpl-memo" value="${esc(cur.memo || "")}"></div>
      <div class="modal-foot">
        ${isEdit ? '<button class="btn btn-ghost" id="tpl-del" style="margin-right:auto;color:var(--red)">Excluir</button>' : ""}
        <button class="btn" onclick="closeModal()">Cancelar</button>
        <button class="btn btn-gold" id="tpl-save">Salvar modelo</button>
      </div>
    </div>`);
  $$("[data-edit-template]").forEach(b => b.addEventListener("click", () => {
    const found = templates.find(x => x.id == b.dataset.editTemplate);
    templateModal(found);
  }));
  $("#tpl-save").addEventListener("click", async () => {
    const val = parseFloat(($("#tpl-amount").value || "0").replace(",", ".")) || 0;
    if (!$("#tpl-name").value || !val) { toast("Informe nome e valor."); return; }
    const body = {
      name: $("#tpl-name").value,
      account_id: +$("#tpl-account").value,
      category_id: $("#tpl-cat").value ? +$("#tpl-cat").value : null,
      payee: $("#tpl-payee").value,
      memo: $("#tpl-memo").value,
      amount: $("#tpl-type").value === "expense" ? -Math.abs(val) : Math.abs(val),
    };
    if (isEdit) await api.put("/templates/" + t.id, body); else await api.post("/templates", body);
    closeModal(); toast("Modelo salvo!"); render();
  });
  if (isEdit) $("#tpl-del").addEventListener("click", async () => {
    if (!confirm("Excluir este modelo?")) return;
    await api.del("/templates/" + t.id);
    closeModal(); toast("Modelo excluído"); render();
  });
}

/* ============ CALENDÁRIO ============ */
async function renderCalendar() {
  $("#topbar-actions").innerHTML = monthSwitcher();
  bindMonthSwitcher(renderCalendar);
  const data = await api.get("/calendar?month=" + state.month);
  const byDay = {};
  data.events.forEach(e => {
    if (!byDay[e.date]) byDay[e.date] = [];
    byDay[e.date].push(e);
  });
  const end = new Date(+state.month.slice(0, 4), +state.month.slice(5, 7), 0).getDate();
  const days = Array.from({length: end}, (_, i) => `${state.month}-${String(i + 1).padStart(2, "0")}`);
  $("#view").innerHTML = `<div class="calendar-grid">${days.map(d => `
    <div class="cal-day">
      <div class="cal-date">${d.slice(8)}</div>
      ${(byDay[d] || []).slice(0, 4).map(e => `
        <button class="cal-event ${e.kind}" data-cal-view="${e.view}">
          <span>${esc(e.title)}</span><b class="num ${clsAmt(e.amount)}">${brl(e.amount)}</b>
        </button>`).join("")}
    </div>`).join("")}</div>`;
  $$("[data-cal-view]").forEach(b => b.addEventListener("click", () => route(b.dataset.calView)));
}

/* ============ REVISÃO ============ */
async function renderReview() {
  const r = await api.get("/review");
  const block = (title, items, empty, view, renderItem) => `
    <div class="panel">
      <div class="panel-head"><h3>${title}</h3><span class="tag">${items.length}</span></div>
      ${items.length ? `<div class="review-list">${items.map(renderItem).join("")}</div>` : `<div class="empty">${empty}</div>`}
      ${items.length ? `<div style="padding:12px 16px;border-top:1px solid var(--border)"><button class="btn btn-sm" data-review-view="${view}">Abrir</button></div>` : ""}
    </div>`;
  $("#view").innerHTML = `<div class="review-grid">
    ${block("Categorizar", r.uncategorized, "Nenhum gasto sem categoria.", "transactions", t => `<div class="review-item"><b>${esc(t.payee || "Lançamento")}</b><span class="num">${brl(t.amount)}</span><small>${dateBR(t.date)}</small></div>`)}
    ${block("Orçamento estourado", r.overbudget, "Nenhuma categoria estourada.", "budget", x => `<div class="review-item"><b>${esc(x.name)}</b><span class="num neg">${brl(x.available)}</span><small>${esc(x.group)}</small></div>`)}
    ${block("Perto do limite", r.near_limit, "Nada perto do limite.", "budget", x => `<div class="review-item"><b>${esc(x.name)}</b><span class="num">${brl(x.available)}</span><small>${esc(x.group)}</small></div>`)}
    ${block("Vencimentos", r.due, "Nada vencendo nos próximos dias.", "scheduled", s => `<div class="review-item"><b>${esc(s.payee || s.category_name || "Previsto")}</b><span class="num ${clsAmt(s.amount)}">${brl(s.amount)}</span><small>${dateBR(s.next_date)}</small></div>`)}
    ${block("Metas em andamento", r.goals, "Nenhuma meta pendente.", "goals", g => `<div class="review-item"><b>${esc(g.category_name)}</b><span>${g.progress}%</span><small>Faltam ${brl(g.remaining)}</small></div>`)}
  </div>`;
  $$("[data-review-view]").forEach(b => b.addEventListener("click", () => route(b.dataset.reviewView)));
}

/* ============ PREVISÃO ============ */
async function renderForecast() {
  $("#topbar-actions").innerHTML = `<select id="fc-months" class="btn" style="background:var(--surface)">
    <option value="3">3 meses</option><option value="6" selected>6 meses</option><option value="12">12 meses</option></select>`;
  $("#fc-months").addEventListener("change", renderForecast);
  const months = $("#fc-months") ? +$("#fc-months").value : 6;
  const f = await api.get("/forecast?months=" + months);
  const last = f.points[f.points.length - 1];
  $("#view").innerHTML = `
    <div class="grid cards" style="margin-bottom:18px">
      <div class="card"><div class="label">Saldo hoje</div><div class="value num">${brl(f.current_balance)}</div></div>
      <div class="card accent"><div class="label">Projeção em ${last.label}</div><div class="value num">${brl(last.balance)}</div></div>
    </div>
    <div class="panel"><div class="panel-head"><h3>Trajetória de saldo projetada</h3></div>
      <div class="chart-wrap"><canvas id="fcChart" height="150"></canvas></div></div>
    <div class="panel" style="margin-top:16px"><div class="panel-head"><h3>Detalhe mês a mês</h3></div>
      <table><thead><tr><th>Mês</th><th class="right">Entradas</th><th class="right">Saídas</th><th class="right">Saldo projetado</th></tr></thead>
      <tbody>${f.points.slice(1).map(p => `<tr><td>${p.label}</td>
        <td class="right num pos">${brl(p.income)}</td>
        <td class="right num neg">${brl(p.expense)}</td>
        <td class="right num ${p.balance < 0 ? "neg" : ""}">${brl(p.balance)}</td></tr>`).join("")}</tbody></table>
    </div>
    <p style="color:var(--faint);font-size:12.5px;margin-top:12px">A projeção combina seus lançamentos recorrentes com a média de gastos dos últimos 3 meses por categoria.</p>`;
  if (state.chart) state.chart.destroy();
  state.chart = new Chart($("#fcChart"), {
    type: "line",
    data: { labels: f.points.map(p => p.label), datasets: [{
      label: "Saldo", data: f.points.map(p => p.balance),
      borderColor: "#e7bd6b", backgroundColor: "rgba(231,189,107,.12)", fill: true, tension: .3, pointRadius: 4, pointBackgroundColor: "#e7bd6b" }] },
    options: { plugins: { legend: { display: false } },
      scales: { x: { ticks: { color: "#98a1b2" }, grid: { display: false } },
        y: { ticks: { color: "#98a1b2", callback: v => "R$" + v }, grid: { color: "#2a2f3a" } } } },
  });
}

/* ============ RELATORIOS ============ */
const reportState = { mode: "timeline", categoryId: "all", months: 12 };

async function renderReports() {
  const cats = flatCategories();
  if (reportState.mode === "evolution" && (reportState.categoryId === "all" || !reportState.categoryId) && cats.length) reportState.categoryId = cats[0].id;
  if (reportState.mode === "timeline" && !reportState.categoryId) reportState.categoryId = "all";
  const catOptions = (reportState.mode === "timeline" ? '<option value="all">Todas as categorias</option>' : "") +
    cats.map(c => `<option value="${c.id}" ${reportState.categoryId == c.id ? "selected" : ""}>${esc(c.group)} > ${esc(c.name)}</option>`).join("");
  $("#topbar-actions").innerHTML = `
    <div class="seg" id="rep-mode" style="min-width:220px">
      <button data-mode="timeline" class="${reportState.mode === "timeline" ? "on-income" : ""}">Timeline</button>
      <button data-mode="evolution" class="${reportState.mode === "evolution" ? "on-income" : ""}">Evolucao</button>
    </div>
    <select id="rep-cat" class="btn" style="background:var(--surface);max-width:260px">
      ${catOptions}
    </select>
    <select id="rep-months" class="btn" style="background:var(--surface);display:${reportState.mode === "evolution" ? "inline-block" : "none"}">
      <option value="6" ${reportState.months == 6 ? "selected" : ""}>6 meses</option>
      <option value="12" ${reportState.months == 12 ? "selected" : ""}>12 meses</option>
      <option value="24" ${reportState.months == 24 ? "selected" : ""}>24 meses</option>
    </select>`;
  $$("#rep-mode button").forEach(b => b.addEventListener("click", () => {
    reportState.mode = b.dataset.mode;
    if (reportState.mode === "evolution" && reportState.categoryId === "all" && cats.length) reportState.categoryId = cats[0].id;
    renderReports();
  }));
  $("#rep-cat")?.addEventListener("change", () => { reportState.categoryId = $("#rep-cat").value; renderReports(); });
  $("#rep-months")?.addEventListener("change", () => { reportState.months = +$("#rep-months").value; renderReports(); });

  if (!cats.length) {
    $("#view").innerHTML = '<div class="panel"><div class="empty">Crie categorias para ver relatorios.</div></div>';
    return;
  }
  if (reportState.mode === "timeline") {
    await renderSpendingTimeline();
    return;
  }
  await renderCategoryEvolution();
}

async function renderCategoryEvolution() {
  const data = await api.get(`/reports/category-evolution?category_id=${reportState.categoryId}&months=${reportState.months}`);
  const s = data.summary || {};
  const changeCls = (s.change || 0) > 0 ? "neg" : (s.change || 0) < 0 ? "pos" : "";
  $("#view").innerHTML = `
    <div class="grid cards" style="margin-bottom:18px">
      <div class="card accent"><div class="label">${esc(data.category.group || "Categoria")}</div><div class="value">${esc(data.category.name)}</div></div>
      <div class="card"><div class="label">Total no periodo</div><div class="value num neg">${brl(s.total || 0)}</div></div>
      <div class="card"><div class="label">Media mensal</div><div class="value num">${brl(s.average || 0)}</div></div>
      <div class="card"><div class="label">Variacao vs mes anterior</div><div class="value num ${changeCls}">${brl(s.change || 0)}</div></div>
    </div>
    <div class="grid" style="grid-template-columns:1.5fr 1fr;gap:16px" id="reports-grid">
      <div class="panel">
        <div class="panel-head"><h3>Evolucao mensal</h3></div>
        <div class="chart-wrap"><canvas id="catChart" height="170"></canvas></div>
      </div>
      <div class="panel">
        <div class="panel-head"><h3>Maiores descricoes</h3></div>
        ${data.top_payees.length ? `<table><tbody>${data.top_payees.map(p => `<tr><td>${esc(p.payee)}</td><td class="right num neg">${brl(p.amount)}</td></tr>`).join("")}</tbody></table>` : '<div class="empty">Sem gastos nessa categoria.</div>'}
      </div>
    </div>
    <div class="panel" style="margin-top:16px">
      <div class="panel-head"><h3>Mes a mes</h3></div>
      <table><thead><tr><th>Mes</th><th class="right">Gasto</th></tr></thead>
      <tbody>${data.points.map(p => `<tr><td>${monthLabel(p.month)}</td><td class="right num neg">${brl(p.amount)}</td></tr>`).join("")}</tbody></table>
    </div>`;
  if (window.innerWidth < 820) $("#reports-grid").style.gridTemplateColumns = "1fr";
  if (state.chart) state.chart.destroy();
  state.chart = new Chart($("#catChart"), {
    type: "bar",
    data: {
      labels: data.points.map(p => p.month.slice(5) + "/" + p.month.slice(2, 4)),
      datasets: [{ label: data.category.name, data: data.points.map(p => p.amount), backgroundColor: "#6cb6f0", borderRadius: 6 }],
    },
    options: { plugins: { legend: { display: false } },
      scales: { x: { ticks: { color: "#98a1b2" }, grid: { display: false } },
        y: { ticks: { color: "#98a1b2", callback: v => "R$" + v }, grid: { color: "#2a2f3a" } } } },
  });
}

async function renderSpendingTimeline() {
  const data = await api.get(`/reports/spending-timeline?month=${state.month}&category_id=${reportState.categoryId}`);
  const remainingCls = data.remaining_goal >= 0 ? "pos" : "neg";
  const paceRows = reportState.categoryId === "all" ? data.category_pace : data.category_pace.filter(x => x.category_id == reportState.categoryId);
  const statusTag = s => s === "danger"
    ? '<span class="tag" style="background:rgba(246,119,111,.15);color:var(--red)">Reduzir</span>'
    : s === "warn"
      ? '<span class="tag" style="background:rgba(231,189,107,.15);color:var(--gold)">Atenção</span>'
      : '<span class="tag" style="background:rgba(87,217,138,.15);color:var(--green)">Ok</span>';
  $("#view").innerHTML = `
    <div class="rta-bar">
      <div><small>${esc(data.label)} em ${monthLabel(data.month)}</small><div class="amt num">${brl(data.projected_total)}</div></div>
      <div style="text-align:right;color:var(--muted);font-size:13px">
        Meta: <b class="num">${brl(data.goal)}</b><br>
        Sobra projetada: <b class="num ${remainingCls}">${brl(data.remaining_goal)}</b>
      </div>
    </div>
    <div class="grid cards" style="margin-bottom:18px">
      <div class="card"><div class="label">Gasto real</div><div class="value num neg">${brl(data.actual_total)}</div></div>
      <div class="card"><div class="label">Previsto ainda no mes</div><div class="value num neg">${brl(data.expected_total)}</div></div>
      <div class="card accent"><div class="label">Total projetado</div><div class="value num">${brl(data.projected_total)}</div></div>
      <div class="card"><div class="label">Meta do mes</div><div class="value num">${brl(data.goal)}</div></div>
    </div>
    <div class="panel">
      <div class="panel-head">
        <h3>Timeline do dinheiro gasto</h3>
        ${monthSwitcher()}
      </div>
      <div class="chart-wrap"><canvas id="timelineChart" height="180"></canvas></div>
    </div>
    <div class="panel" style="margin-top:16px">
      <div class="panel-head"><h3>Ritmo por categoria</h3><span class="tag">${data.remaining_days} dia(s) restantes</span></div>
      <table><thead><tr><th>Categoria</th><th>Status</th><th class="right">Real + previsto</th><th class="right">Pode gastar/dia</th><th class="hide-mobile">Leitura</th></tr></thead>
      <tbody>${paceRows.map(x => `<tr>
        <td>${esc(x.category)}<div style="color:var(--faint);font-size:12px">${esc(x.group)} · meta ${brl(x.goal)}</div></td>
        <td>${statusTag(x.status)}</td>
        <td class="right num ${x.projected > x.goal ? "neg" : ""}">${brl(x.projected)}</td>
        <td class="right num ${x.daily_safe <= 0 && data.remaining_days > 0 ? "neg" : ""}">${data.remaining_days > 0 ? brl(x.daily_safe) : "-"}</td>
        <td class="hide-mobile" style="color:var(--muted);font-size:13px">${esc(x.message)}</td>
      </tr>`).join("") || '<tr><td colspan="5" class="empty">Sem categorias com meta ou gasto neste mes.</td></tr>'}</tbody></table>
    </div>
    <div class="panel" style="margin-top:16px">
      <div class="panel-head"><h3>Dias com movimento</h3></div>
      <table><thead><tr><th>Dia</th><th class="right">Real</th><th class="right">Previsto</th><th class="right">Projetado acumulado</th></tr></thead>
      <tbody>${data.days.filter(d => d.daily_actual || d.daily_expected).map(d => `<tr>
        <td>${dateBR(d.date)}</td>
        <td class="right num neg">${d.daily_actual ? brl(d.daily_actual) : "-"}</td>
        <td class="right num neg">${d.daily_expected ? brl(d.daily_expected) : "-"}</td>
        <td class="right num">${brl(d.projected)}</td>
      </tr>`).join("") || '<tr><td colspan="4" class="empty">Sem gastos reais ou previstos neste mes.</td></tr>'}</tbody></table>
    </div>`;
  bindMonthSwitcher(renderReports);
  if (state.chart) state.chart.destroy();
  state.chart = new Chart($("#timelineChart"), {
    type: "line",
    data: {
      labels: data.days.map(d => d.day),
      datasets: [
        { label: "Real", data: data.days.map(d => d.actual), borderColor: "#f6776f", tension: .25, pointRadius: 0, borderWidth: 2 },
        { label: "Projetado com previstos", data: data.days.map(d => d.projected), borderColor: "#e7bd6b", backgroundColor: "rgba(231,189,107,.1)", fill: true, tension: .25, pointRadius: 0, borderWidth: 2 },
        { label: "Meta proporcional", data: data.days.map(d => d.goal_line), borderColor: "#57d98a", borderDash: [5, 5], tension: 0, pointRadius: 0, borderWidth: 1.5 },
      ],
    },
    options: {
      plugins: { legend: { labels: { color: "#98a1b2", font: { family: "Bricolage Grotesque" } } } },
      scales: { x: { ticks: { color: "#98a1b2" }, grid: { display: false } },
        y: { ticks: { color: "#98a1b2", callback: v => "R$" + v }, grid: { color: "#2a2f3a" } } },
    },
  });
}

/* ============ SAUDE FINANCEIRA ============ */
async function renderHealth() {
  $("#topbar-actions").innerHTML = monthSwitcher();
  bindMonthSwitcher(renderHealth);
  const h = await api.get("/health?month=" + state.month);
  const c = h.cards;
  const i = h.indicators;
  const pct = v => v === null || v === undefined ? "--" : `${v.toFixed(1)}%`;
  const monthsTxt = v => v === null || v === undefined ? "--" : `${v.toFixed(1)} meses`;
  const indicator = (title, value, hint, cls = "") => `
    <div class="health-item">
      <div><b>${title}</b><small>${hint}</small></div>
      <span class="num ${cls}">${value}</span>
    </div>`;
  $("#view").innerHTML = `
    <div class="grid cards" style="margin-bottom:18px">
      <div class="card accent"><div class="label">Saldo disponivel</div><div class="value num">${brl(c.cash_balance)}</div></div>
      <div class="card"><div class="label">Entradas do mes</div><div class="value num pos">${brl(c.month_income)}</div></div>
      <div class="card"><div class="label">Saidas do mes</div><div class="value num neg">${brl(c.month_expense)}</div></div>
      <div class="card"><div class="label">Divida em cartoes</div><div class="value num ${c.credit_debt > 0 ? "neg" : ""}">${brl(c.credit_debt)}</div></div>
    </div>
    <div class="grid" style="grid-template-columns:1.2fr .8fr;gap:16px" id="health-grid">
      <div class="panel">
        <div class="panel-head"><h3>Indicadores</h3></div>
        <div class="health-list">
          ${indicator("Taxa de poupanca", pct(i.savings_rate), "Quanto sobrou da renda neste mes", i.savings_rate >= 20 ? "pos" : i.savings_rate < 0 ? "neg" : "")}
          ${indicator("Reserva estimada", monthsTxt(i.emergency_months), "Saldo dividido pela media recente de gastos", i.emergency_months >= 6 ? "pos" : i.emergency_months < 3 ? "neg" : "")}
          ${indicator("Uso do limite", pct(i.debt_utilization), "Divida dos cartoes sobre limite cadastrado", i.debt_utilization > 50 ? "neg" : "")}
          ${indicator("Fixos sobre renda", pct(i.fixed_ratio), "Recorrentes previstos sobre renda media", i.fixed_ratio > 50 ? "neg" : "")}
        </div>
      </div>
      <div class="panel">
        <div class="panel-head"><h3>Leitura rapida</h3></div>
        <div class="note-list">${h.notes.map(n => `<div class="note">${esc(n)}</div>`).join("")}</div>
      </div>
    </div>
    <div class="grid" style="grid-template-columns:1fr 1fr;gap:16px;margin-top:16px" id="health-grid-2">
      <div class="panel"><div class="panel-head"><h3>Medias recentes</h3></div>
        <table><tbody>
          <tr><td>Entrada media</td><td class="right num pos">${brl(c.avg_income)}</td></tr>
          <tr><td>Gasto medio</td><td class="right num neg">${brl(c.avg_expense)}</td></tr>
          <tr><td>Pronto para atribuir</td><td class="right num ${clsAmt(c.ready_to_assign)}">${brl(c.ready_to_assign)}</td></tr>
          <tr><td>Disponivel no orcamento</td><td class="right num">${brl(c.budget_available)}</td></tr>
        </tbody></table></div>
      <div class="panel"><div class="panel-head"><h3>Categorias negativas</h3><span class="tag">${h.overbudget.length}</span></div>
        ${h.overbudget.length ? `<table><tbody>${h.overbudget.map(x => `<tr><td>${esc(x.name)}<div style="color:var(--faint);font-size:12px">${esc(x.group)}</div></td><td class="right num neg">${brl(x.available)}</td></tr>`).join("")}</tbody></table>` : '<div class="empty">Nenhuma categoria negativa.</div>'}
      </div>
    </div>`;
  if (window.innerWidth < 820) {
    $("#health-grid").style.gridTemplateColumns = "1fr";
    $("#health-grid-2").style.gridTemplateColumns = "1fr";
  }
}

/* ============ SIMULADOR ============ */
const simState = { kind: "purchase" };

async function renderSimulator() {
  $("#topbar-actions").innerHTML = `
    <div class="seg" id="sim-kind" style="min-width:260px">
      <button data-kind="purchase" class="${simState.kind === "purchase" ? "on-expense" : ""}">Compra</button>
      <button data-kind="goal" class="${simState.kind === "goal" ? "on-income" : ""}">Meta</button>
    </div>`;
  $$("#sim-kind button").forEach(b => b.addEventListener("click", () => { simState.kind = b.dataset.kind; renderSimulator(); }));
  $("#view").innerHTML = `
    <div class="grid" style="grid-template-columns:360px 1fr;gap:16px" id="sim-grid">
      <div class="panel">
        <div class="panel-head"><h3>${simState.kind === "purchase" ? "Compra parcelada" : "Plano de meta"}</h3></div>
        <div style="padding:18px;display:grid;gap:14px">
          ${simState.kind === "purchase" ? `
            <div class="field"><label>Valor total (R$)</label><input id="sim-amount" type="number" step="0.01" value="2400"></div>
            <div class="row2">
              <div class="field"><label>Parcelas</label><input id="sim-inst" type="number" min="1" max="48" value="12"></div>
              <div class="field"><label>Horizonte</label><select id="sim-months"><option value="6">6 meses</option><option value="12" selected>12 meses</option><option value="24">24 meses</option></select></div>
            </div>` : `
            <div class="field"><label>Valor da meta (R$)</label><input id="sim-goal" type="number" step="0.01" value="10000"></div>
            <div class="row2">
              <div class="field"><label>Aporte mensal (R$)</label><input id="sim-monthly" type="number" step="0.01" value="500"></div>
              <div class="field"><label>Horizonte</label><select id="sim-months"><option value="6">6 meses</option><option value="12" selected>12 meses</option><option value="24">24 meses</option><option value="36">36 meses</option></select></div>
            </div>`}
          <button class="btn btn-gold" id="sim-run">Simular</button>
        </div>
      </div>
      <div id="sim-result" class="panel"><div class="empty">Preencha os valores e rode a simulacao.</div></div>
    </div>`;
  if (window.innerWidth < 820) $("#sim-grid").style.gridTemplateColumns = "1fr";
  $("#sim-run").addEventListener("click", runSimulation);
  runSimulation();
}

async function runSimulation() {
  const months = +$("#sim-months").value;
  const body = { kind: simState.kind, months };
  if (simState.kind === "purchase") {
    body.amount = parseFloat(($("#sim-amount").value || "0").replace(",", ".")) || 0;
    body.installments = +$("#sim-inst").value || 1;
  } else {
    body.goal_amount = parseFloat(($("#sim-goal").value || "0").replace(",", ".")) || 0;
    body.monthly_amount = parseFloat(($("#sim-monthly").value || "0").replace(",", ".")) || 0;
  }
  const r = await api.post("/simulator", body);
  const s = r.summary;
  const cards = simState.kind === "purchase" ? `
    <div class="card"><div class="label">Parcela media</div><div class="value num neg">${brl(s.monthly)}</div></div>
    <div class="card"><div class="label">Impacto final</div><div class="value num neg">${brl(s.final_impact)}</div></div>
    <div class="card accent"><div class="label">Saldo projetado final</div><div class="value num">${brl(s.final_balance)}</div></div>` : `
    <div class="card"><div class="label">Guardado no periodo</div><div class="value num pos">${brl(s.saved_in_period)}</div></div>
    <div class="card"><div class="label">Meses necessarios</div><div class="value num">${s.months_needed || "--"}</div></div>
    <div class="card accent"><div class="label">Chega na meta</div><div class="value">${s.hit_month ? monthLabel(s.hit_month) : "Depois"}</div></div>`;
  $("#sim-result").innerHTML = `
    <div style="padding:16px">
      <div class="grid cards" style="margin-bottom:16px">${cards}</div>
      <div class="chart-wrap" style="padding:0"><canvas id="simChart" height="170"></canvas></div>
    </div>`;
  if (state.chart) state.chart.destroy();
  const simLabels = r.adjusted.map(p => p.label || p.month.slice(5) + "/" + p.month.slice(2, 4));
  const simDatasets = simState.kind === "purchase" ? [
    { label: "Base", data: r.base.map(p => p.balance), borderColor: "#6cb6f0", tension: .3, pointRadius: 2 },
    { label: "Simulado", data: r.adjusted.map(p => p.balance), borderColor: "#e7bd6b", backgroundColor: "rgba(231,189,107,.12)", fill: true, tension: .3, pointRadius: 3 },
  ] : [
    { label: "Guardado", data: r.adjusted.map(p => p.saved || 0), borderColor: "#57d98a", backgroundColor: "rgba(87,217,138,.12)", fill: true, tension: .3, pointRadius: 3 },
  ];
  state.chart = new Chart($("#simChart"), {
    type: "line",
    data: {
      labels: simLabels,
      datasets: simDatasets,
    },
    options: { plugins: { legend: { labels: { color: "#98a1b2", font: { family: "Bricolage Grotesque" } } } },
      scales: { x: { ticks: { color: "#98a1b2" }, grid: { display: false } },
        y: { ticks: { color: "#98a1b2", callback: v => "R$" + v }, grid: { color: "#2a2f3a" } } } },
  });
}

/* ============ RECORRENTES ============ */
const FREQ = { once: "Uma vez", weekly: "Semanal", biweekly: "Quinzenal", monthly: "Mensal", yearly: "Anual" };
async function renderScheduled() {
  $("#topbar-actions").innerHTML = `<button class="btn btn-gold" id="add-sch">+ Recorrente</button>`;
  $("#add-sch").addEventListener("click", () => scheduledModal());
  const items = await api.get("/scheduled");
  $("#view").innerHTML = `<div class="panel">${items.length ? `<table>
    <thead><tr><th>Próxima</th><th>Descrição</th><th class="hide-mobile">Frequência</th><th class="right">Valor</th><th class="right">Ações</th></tr></thead>
    <tbody>${items.map(s => `<tr>
      <td class="num">${dateBR(s.next_date)}</td>
      <td>${s.payee || s.category_name || "—"}<div style="color:var(--faint);font-size:12px">${s.category_name || ""}</div></td>
      <td class="hide-mobile"><span class="tag">${FREQ[s.frequency]}</span></td>
      <td class="right num ${clsAmt(s.amount)}">${brl(s.amount)}</td>
      <td class="right" style="white-space:nowrap">
        <button class="icon-btn" data-post="${s.id}" title="Lançar agora">✓</button>
        <button class="icon-btn" data-edit="${s.id}">✎</button>
        <button class="icon-btn" data-del="${s.id}">🗑</button></td>
    </tr>`).join("")}</tbody></table>` : '<div class="empty">Nenhum lançamento recorrente.<br>Cadastre salários, aluguel, assinaturas…</div>'}</div>`;

  $$("[data-post]").forEach(b => b.addEventListener("click", async () => { await api.post("/scheduled/" + b.dataset.post + "/post", {}); toast("Lançado!"); render(); }));
  $$("[data-edit]").forEach(b => b.addEventListener("click", () => scheduledModal(items.find(s => s.id == b.dataset.edit))));
  $$("[data-del]").forEach(b => b.addEventListener("click", async () => { if (confirm("Excluir recorrência?")) { await api.del("/scheduled/" + b.dataset.del); toast("Excluído"); render(); } }));
}

function scheduledModal(s = null) {
  if (!state.accounts.length) { toast("Crie uma conta primeiro."); route("accounts"); return; }
  const isEdit = !!s; const cats = flatCategories();
  const isExpense = s ? s.amount < 0 : true;
  openModal(`
    <div class="modal-head"><h3>${isEdit ? "Editar" : "Novo"} recorrente</h3></div>
    <div class="modal-body">
      <div class="seg" id="seg-type">
        <button type="button" data-type="expense" class="${isExpense ? "on-expense" : ""}">Saída</button>
        <button type="button" data-type="income" class="${!isExpense ? "on-income" : ""}">Entrada</button></div>
      <div class="row2">
        <div class="field"><label>Valor (R$)</label><input id="f-amount" type="number" step="0.01" value="${s ? Math.abs(s.amount) : ""}"></div>
        <div class="field"><label>Frequência</label><select id="f-freq">${Object.entries(FREQ).map(([k, v]) => `<option value="${k}" ${s && s.frequency === k ? "selected" : ""}>${v}</option>`).join("")}</select></div>
      </div>
      <div class="row2">
        <div class="field"><label>Próxima data</label><input id="f-date" type="date" value="${s ? s.next_date : todayISO()}"></div>
        <div class="field"><label>Conta</label><select id="f-account">${state.accounts.map(a => `<option value="${a.id}" ${s && s.account_id == a.id ? "selected" : ""}>${a.name}</option>`).join("")}</select></div>
      </div>
      <div class="field"><label>Categoria</label><select id="f-cat"><option value="">— Sem categoria (renda) —</option>${cats.map(c => `<option value="${c.id}" ${s && s.category_id == c.id ? "selected" : ""}>${c.group} › ${c.name}</option>`).join("")}</select></div>
      <div class="field"><label>Descrição</label><input id="f-payee" value="${s ? esc(s.payee) : ""}" placeholder="Ex.: Salário, Netflix"></div>
      <div class="modal-foot"><button class="btn" onclick="closeModal()">Cancelar</button><button class="btn btn-gold" id="save">Salvar</button></div>
    </div>`);
  let type = isExpense ? "expense" : "income";
  $$("#seg-type button").forEach(b => b.addEventListener("click", () => { type = b.dataset.type; $$("#seg-type button").forEach(x => { x.classList.remove("on-expense", "on-income"); if (x.dataset.type === type) x.classList.add(type === "expense" ? "on-expense" : "on-income"); }); }));
  $("#save").addEventListener("click", async () => {
    const val = parseFloat($("#f-amount").value.replace(",", ".")) || 0;
    if (!val) { toast("Informe um valor."); return; }
    const body = { account_id: +$("#f-account").value, category_id: $("#f-cat").value ? +$("#f-cat").value : null,
      amount: type === "expense" ? -Math.abs(val) : Math.abs(val), frequency: $("#f-freq").value,
      next_date: $("#f-date").value, payee: $("#f-payee").value };
    if (isEdit) await api.put("/scheduled/" + s.id, body); else await api.post("/scheduled", body);
    closeModal(); toast("Salvo!"); render();
  });
}

/* ============ CONTAS ============ */
async function renderAccounts() {
  $("#topbar-actions").innerHTML = `<button class="btn btn-gold" id="add-acc">+ Conta</button>`;
  $("#add-acc").addEventListener("click", () => accountModal());
  const TYPES = { checking: "Conta corrente", savings: "Poupança", credit: "Cartão de crédito", cash: "Dinheiro", investment: "Investimento" };
  $("#view").innerHTML = `<div class="panel"><table>
    <thead><tr><th>Conta</th><th class="hide-mobile">Tipo</th><th class="hide-mobile">No orçamento</th><th class="right">Saldo</th></tr></thead>
    <tbody>${state.accounts.map(a => `<tr data-id="${a.id}" class="acc-row" style="cursor:pointer">
      <td><b>${a.name}</b></td><td class="hide-mobile">${TYPES[a.type] || a.type}</td>
      <td class="hide-mobile">${a.on_budget ? "Sim" : "Não"}</td>
      <td class="right num ${clsAmt(a.balance)}">${brl(a.balance)}</td></tr>`).join("") || '<tr><td colspan="4" class="empty">Crie sua primeira conta.</td></tr>'}</tbody>
  </table></div>`;
  $$(".acc-row").forEach(r => r.addEventListener("click", () => accountModal(state.accounts.find(a => a.id == r.dataset.id))));
}

function accountModal(a = null, presetType = null) {
  const isEdit = !!a;
  const TYPES = { checking: "Conta corrente", savings: "Poupança", credit: "Cartão de crédito", cash: "Dinheiro", investment: "Investimento" };
  const curType = a ? a.type : (presetType || "checking");
  openModal(`
    <div class="modal-head"><h3>${isEdit ? "Editar" : "Nova"} conta</h3></div>
    <div class="modal-body">
      <div class="field"><label>Nome</label><input id="f-name" value="${a ? esc(a.name) : ""}" placeholder="Ex.: Nubank"></div>
      <div class="row2">
        <div class="field"><label>Tipo</label><select id="f-type">${Object.entries(TYPES).map(([k, v]) => `<option value="${k}" ${curType === k ? "selected" : ""}>${v}</option>`).join("")}</select></div>
        <div class="field"><label id="lbl-bal">Saldo inicial</label><input id="f-bal" type="number" step="0.01" value="${a ? a.starting_balance : 0}"></div>
      </div>
      <div id="credit-fields" style="display:none;flex-direction:column;gap:14px">
        <div class="row2">
          <div class="field"><label>Dia de fechamento</label><input id="f-close" type="number" min="1" max="31" value="${a && a.closing_day ? a.closing_day : 28}"></div>
          <div class="field"><label>Dia de vencimento</label><input id="f-due" type="number" min="1" max="31" value="${a && a.due_day ? a.due_day : 8}"></div>
        </div>
        <div class="field"><label>Limite (R$, opcional)</label><input id="f-limit" type="number" step="0.01" value="${a && a.credit_limit ? a.credit_limit : ""}" placeholder="Ex.: 5000"></div>
      </div>
      <div class="field" id="budget-field"><label><input type="checkbox" id="f-budget" ${!a || a.on_budget ? "checked" : ""}> Incluir no orçamento</label></div>
      <div class="modal-foot">${isEdit ? '<button class="btn btn-ghost" id="del" style="margin-right:auto;color:var(--red)">Excluir</button>' : ""}
        <button class="btn" onclick="closeModal()">Cancelar</button><button class="btn btn-gold" id="save">Salvar</button></div>
    </div>`);

  const typeSel = $("#f-type");
  const toggle = () => {
    const isCredit = typeSel.value === "credit";
    $("#credit-fields").style.display = isCredit ? "flex" : "none";
    $("#lbl-bal").textContent = isCredit ? "Dívida inicial (negativo)" : "Saldo inicial";
  };
  typeSel.addEventListener("change", toggle); toggle();

  $("#save").addEventListener("click", async () => {
    const isCredit = typeSel.value === "credit";
    const body = { name: $("#f-name").value || "Conta", type: typeSel.value,
      starting_balance: parseFloat($("#f-bal").value) || 0, on_budget: $("#f-budget").checked };
    if (isCredit) {
      body.closing_day = parseInt($("#f-close").value) || 28;
      body.due_day = parseInt($("#f-due").value) || 8;
      body.credit_limit = $("#f-limit").value ? parseFloat($("#f-limit").value) : null;
    }
    if (isEdit) await api.put("/accounts/" + a.id, body); else await api.post("/accounts", body);
    closeModal(); toast("Salvo!"); render();
  });
  if (isEdit) $("#del").addEventListener("click", async () => {
    if (!confirm("Excluir a conta e TODOS os lançamentos dela?")) return;
    await api.del("/accounts/" + a.id); closeModal(); toast("Excluído"); render();
  });
}

/* ============ PATRIMÔNIO LÍQUIDO ============ */
async function renderNetworth() {
  $("#topbar-actions").innerHTML = `<button class="btn btn-gold" id="add-nw">+ Item</button>`;
  $("#add-nw").addEventListener("click", () => nwItemModal());
  const data = await api.get("/networth?months=12");
  const b = data.breakdown;
  const cur = data.history.points[data.history.points.length - 1];
  const prev = data.history.points.length > 1 ? data.history.points[data.history.points.length - 2] : null;
  const delta = prev ? cur.net_worth - prev.net_worth : 0;
  const deltaTxt = prev ? `<span class="num ${delta >= 0 ? "pos" : "neg"}">${delta >= 0 ? "▲" : "▼"} ${brl(Math.abs(delta))}</span> vs. mês anterior` : "";

  $("#view").innerHTML = `
    <div class="grid cards" style="margin-bottom:18px">
      <div class="card accent"><div class="label">Patrimônio líquido</div><div class="value num">${brl(b.net_worth)}</div>
        <div style="color:var(--muted);font-size:12px;margin-top:6px">${deltaTxt}</div></div>
      <div class="card"><div class="label">Total em ativos</div><div class="value num pos">${brl(b.total_assets)}</div></div>
      <div class="card"><div class="label">Total em passivos</div><div class="value num neg">${brl(b.total_liabilities)}</div></div>
    </div>
    <div class="panel"><div class="panel-head"><h3>Evolução do patrimônio (12 meses)</h3></div>
      <div class="chart-wrap"><canvas id="nwChart" height="150"></canvas></div></div>
    <div class="grid" style="grid-template-columns:1fr 1fr;gap:16px;margin-top:16px" id="nw-grid">
      <div class="panel"><div class="panel-head"><h3>Ativos</h3></div><div id="nw-assets"></div></div>
      <div class="panel"><div class="panel-head"><h3>Passivos</h3></div><div id="nw-liab"></div></div>
    </div>
    <p style="color:var(--faint);font-size:12.5px;margin-top:12px">Contas (corrente, investimento, cartão) entram automaticamente pelo saldo. Adicione itens manuais como imóvel, carro ou financiamento — e atualize o valor de cada mês para ver a evolução real.</p>`;
  if (window.innerWidth < 820) $("#nw-grid").style.gridTemplateColumns = "1fr";

  renderNwList("#nw-assets", b.assets, "Nenhum ativo ainda.");
  renderNwList("#nw-liab", b.liabilities, "Nenhum passivo. 🎉");
  drawNw(data.history.points);
}

function renderNwList(sel, items, emptyMsg) {
  const el = $(sel);
  if (!items.length) { el.innerHTML = `<div class="empty">${emptyMsg}</div>`; return; }
  el.innerHTML = "<table><tbody>" + items.map(it => {
    const isItem = it.source === "item";
    const id = isItem ? it.id.replace("item-", "") : null;
    return `<tr ${isItem ? `class="nw-row" data-id="${id}" style="cursor:pointer"` : ""}>
      <td>${it.name}${isItem ? "" : ' <span class="tag" style="font-size:10px">auto</span>'}
        <div style="color:var(--faint);font-size:11.5px">${it.category}</div></td>
      <td class="right num">${brl(it.value)}</td></tr>`;
  }).join("") + "</tbody></table>";
  $$(sel + " .nw-row").forEach(r => r.addEventListener("click", () => nwItemDetail(+r.dataset.id)));
}

function drawNw(points) {
  if (state.chart) state.chart.destroy();
  const ctx = $("#nwChart"); if (!ctx) return;
  const labels = points.map(p => { const [y, m] = p.month.split("-"); return m + "/" + y.slice(2); });
  state.chart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "Patrimônio líquido", data: points.map(p => p.net_worth), borderColor: "#e7bd6b",
          backgroundColor: "rgba(231,189,107,.12)", fill: true, tension: .3, pointRadius: 3, pointBackgroundColor: "#e7bd6b", borderWidth: 2.5 },
        { label: "Ativos", data: points.map(p => p.assets), borderColor: "#57d98a", borderDash: [5, 4], fill: false, tension: .3, pointRadius: 0, borderWidth: 1.5 },
        { label: "Passivos", data: points.map(p => p.liabilities), borderColor: "#f6776f", borderDash: [5, 4], fill: false, tension: .3, pointRadius: 0, borderWidth: 1.5 },
      ],
    },
    options: {
      plugins: { legend: { labels: { color: "#98a1b2", font: { family: "Bricolage Grotesque" }, usePointStyle: true, boxWidth: 8 } } },
      scales: { x: { ticks: { color: "#98a1b2" }, grid: { display: false } },
        y: { ticks: { color: "#98a1b2", callback: v => "R$" + (Math.abs(v) >= 1000 ? (v / 1000).toFixed(0) + "k" : v) }, grid: { color: "#2a2f3a" } } },
    },
  });
}

function nwItemModal(it = null) {
  const isEdit = !!it;
  const kind = it ? it.kind : "asset";
  openModal(`
    <div class="modal-head"><h3>${isEdit ? "Editar" : "Novo"} item de patrimônio</h3></div>
    <div class="modal-body">
      <div class="seg" id="seg-kind">
        <button type="button" data-kind="asset" class="${kind === "asset" ? "on-income" : ""}">Ativo (tenho)</button>
        <button type="button" data-kind="liability" class="${kind === "liability" ? "on-expense" : ""}">Passivo (devo)</button></div>
      <div class="field"><label>Nome</label><input id="f-name" value="${it ? esc(it.name) : ""}" placeholder="Ex.: Apartamento, Carro, Financiamento"></div>
      <div class="field"><label>Categoria (opcional)</label><input id="f-cat" value="${it ? esc(it.category || "") : ""}" placeholder="Ex.: Imóveis, Veículos, Dívidas"></div>
      ${isEdit ? "" : `<div class="row2">
        <div class="field"><label>Valor atual (R$)</label><input id="f-val" type="number" step="0.01" placeholder="0,00"></div>
        <div class="field"><label>Mês de referência</label><input id="f-month" type="month" value="${todayISO().slice(0, 7)}"></div>
      </div>`}
      <div class="modal-foot">
        ${isEdit ? '<button class="btn btn-ghost" id="del" style="margin-right:auto;color:var(--red)">Excluir</button>' : ""}
        <button class="btn" onclick="closeModal()">Cancelar</button><button class="btn btn-gold" id="save">Salvar</button></div>
    </div>`);
  let k = kind;
  $$("#seg-kind button").forEach(btn => btn.addEventListener("click", () => {
    k = btn.dataset.kind;
    $$("#seg-kind button").forEach(x => { x.classList.remove("on-income", "on-expense"); if (x.dataset.kind === k) x.classList.add(k === "asset" ? "on-income" : "on-expense"); });
  }));
  $("#save").addEventListener("click", async () => {
    const body = { name: $("#f-name").value || "Item", kind: k, category: $("#f-cat").value };
    if (!isEdit) {
      if ($("#f-val").value) { body.value = parseFloat($("#f-val").value.replace(",", ".")); body.month = $("#f-month").value; }
    }
    if (isEdit) await api.put("/networth/items/" + it.id, body); else await api.post("/networth/items", body);
    closeModal(); toast("Salvo!"); renderNetworth();
  });
  if (isEdit) $("#del").addEventListener("click", async () => {
    if (!confirm("Excluir este item e todo o seu histórico?")) return;
    await api.del("/networth/items/" + it.id); closeModal(); toast("Excluído"); renderNetworth();
  });
}

async function nwItemDetail(id) {
  const items = await api.get("/networth/items");
  const it = items.find(x => x.id === id);
  if (!it) return;
  const snaps = [...it.snapshots].reverse();
  openModal(`
    <div class="modal-head"><h3>${esc(it.name)}</h3>
      <div style="color:var(--muted);font-size:13px;margin-top:2px">${it.kind === "asset" ? "Ativo" : "Passivo"}${it.category ? " · " + esc(it.category) : ""}</div></div>
    <div class="modal-body">
      <div style="display:flex;gap:8px;align-items:flex-end">
        <div class="field" style="flex:1"><label>Atualizar valor de um mês</label><input id="s-val" type="number" step="0.01" placeholder="Valor R$"></div>
        <div class="field"><label>Mês</label><input id="s-month" type="month" value="${todayISO().slice(0, 7)}"></div>
        <button class="btn btn-gold" id="s-add" style="margin-bottom:1px">Salvar</button>
      </div>
      <div class="panel" style="margin-top:4px">
        <div class="panel-head"><h3 style="font-size:13px">Histórico de valores</h3></div>
        ${snaps.length ? `<table><tbody>${snaps.map(s => `<tr>
          <td>${monthLabel(s.month)}</td>
          <td class="right num">${brl(s.value)}</td>
          <td class="right" style="width:40px"><button class="icon-btn" data-delsnap="${s.month}">🗑</button></td></tr>`).join("")}</tbody></table>`
        : '<div class="empty">Sem valores registrados ainda.</div>'}
      </div>
      <div class="modal-foot">
        <button class="btn btn-ghost" id="edit-item" style="margin-right:auto">Editar item</button>
        <button class="btn" onclick="closeModal()">Fechar</button></div>
    </div>`);
  $("#s-add").addEventListener("click", async () => {
    const v = $("#s-val").value; if (!v) { toast("Informe um valor."); return; }
    await api.post(`/networth/items/${id}/snapshot`, { month: $("#s-month").value, value: parseFloat(v.replace(",", ".")) });
    toast("Valor salvo!"); nwItemDetail(id);
  });
  $$("[data-delsnap]").forEach(btn => btn.addEventListener("click", async () => {
    await api.del(`/networth/items/${id}/snapshot/${btn.dataset.delsnap}`); toast("Removido"); nwItemDetail(id);
  }));
  $("#edit-item").addEventListener("click", () => nwItemModal(it));
}

/* ============ CARTÕES ============ */
const cardState = { id: null, month: null };

async function renderCards() {
  const cards = await api.get("/cards");
  if (!cards.length) {
    $("#view").innerHTML = `<div class="panel"><div class="empty">
      Nenhum cartão de crédito cadastrado.<br><br>
      <button class="btn btn-gold" id="new-card">+ Cadastrar cartão</button></div></div>
      <p style="color:var(--faint);font-size:12.5px;margin-top:12px">Ao criar a conta, escolha o tipo "Cartão de crédito" e informe os dias de fechamento e vencimento.</p>`;
    $("#new-card").addEventListener("click", () => accountModal(null, "credit"));
    return;
  }
  if (!cardState.id || !cards.find(c => c.id === cardState.id)) { cardState.id = cards[0].id; cardState.month = null; }
  const sel = cards.find(c => c.id === cardState.id);
  if (!cardState.month) cardState.month = sel.open_statement.month;

  const summary = `<div class="grid cards" style="margin-bottom:18px">` + cards.map(c => `
    <div class="card ${c.id === cardState.id ? "accent" : ""}" data-card="${c.id}" style="cursor:pointer">
      <div class="label">${c.name}</div>
      <div class="value num neg">${brl(c.debt)}</div>
      <div style="color:var(--muted);font-size:12px;margin-top:4px">
        ${c.available_limit != null ? "Limite livre: " + brl(c.available_limit) : "Fecha dia " + (c.closing_day || "?")}
        · vence dia ${c.due_day || "?"}</div>
    </div>`).join("") + `</div>`;

  $("#view").innerHTML = summary + `<div id="stmt"></div>`;
  $$("[data-card]").forEach(el => el.addEventListener("click", () => { cardState.id = +el.dataset.card; cardState.month = null; renderCards(); }));
  loadStatement();
}

async function loadStatement() {
  const st = await api.get(`/cards/${cardState.id}/statement?month=${cardState.month}`);
  const statusTag = st.is_paid
    ? '<span class="tag" style="background:rgba(87,217,138,.15);color:var(--green)">Paga</span>'
    : st.total <= 0 ? '<span class="tag">Sem compras</span>'
    : `<span class="tag" style="background:rgba(246,119,111,.15);color:var(--red)">Em aberto</span>`;
  const rows = st.transactions.length ? st.transactions.map(t => `<tr>
      <td class="num">${dateBR(t.date)}</td>
      <td>${t.payee || "—"}${t.installment_total > 1 ? ` <span class="tag" style="font-size:10px;background:rgba(108,182,240,.15);color:var(--blue)">${t.installment_num}/${t.installment_total}</span>` : ""}</td>
      <td class="hide-mobile">${t.category_name ? `<span class="tag">${t.category_name}</span>` : "—"}</td>
      <td class="right num ${clsAmt(t.amount)}">${brl(t.amount)}</td></tr>`).join("")
    : '<tr><td colspan="4" class="empty">Nenhuma compra neste ciclo.</td></tr>';

  $("#stmt").innerHTML = `
    <div class="panel">
      <div class="panel-head">
        <div class="month-switch"><button id="s-prev">‹</button>
          <span class="label">Fatura ${monthLabel(st.month)}</span><button id="s-next">›</button></div>
        ${st.remaining > 0.005 ? `<button class="btn btn-gold btn-sm" id="pay-btn">Pagar fatura</button>` : statusTag}
      </div>
      <div style="display:flex;gap:24px;flex-wrap:wrap;padding:16px 20px;border-bottom:1px solid var(--border)">
        <div><div style="color:var(--faint);font-size:11px;text-transform:uppercase;letter-spacing:.05em">Período</div>
          <div style="font-weight:600;font-size:13.5px;margin-top:3px">${dateBR(st.cycle_start)} a ${dateBR(st.cycle_end)}</div></div>
        <div><div style="color:var(--faint);font-size:11px;text-transform:uppercase;letter-spacing:.05em">Vencimento</div>
          <div style="font-weight:600;font-size:13.5px;margin-top:3px">${dateBR(st.due_date)}</div></div>
        <div><div style="color:var(--faint);font-size:11px;text-transform:uppercase;letter-spacing:.05em">Total da fatura</div>
          <div style="font-weight:700;font-size:16px;margin-top:2px" class="num">${brl(st.total)}</div></div>
        ${st.paid > 0.005 ? `<div><div style="color:var(--faint);font-size:11px;text-transform:uppercase;letter-spacing:.05em">Pago</div>
          <div style="font-weight:700;font-size:16px;margin-top:2px" class="num pos">${brl(st.paid)}</div></div>
          <div><div style="color:var(--faint);font-size:11px;text-transform:uppercase;letter-spacing:.05em">Falta</div>
          <div style="font-weight:700;font-size:16px;margin-top:2px" class="num ${st.remaining > 0 ? "neg" : ""}">${brl(st.remaining)}</div></div>` : ""}
      </div>
      <table><thead><tr><th>Data</th><th>Descrição</th><th class="hide-mobile">Categoria</th><th class="right">Valor</th></tr></thead>
      <tbody>${rows}</tbody></table>
    </div>
    <p style="color:var(--faint);font-size:12.5px;margin-top:12px">As compras já contam no seu orçamento na data em que acontecem. Pagar a fatura é uma transferência da conta para o cartão — não conta como novo gasto.</p>`;

  const shift = d => { const [y, m] = cardState.month.split("-").map(Number); const dt = new Date(y, m - 1 + d, 1); cardState.month = dt.toISOString().slice(0, 7); loadStatement(); };
  $("#s-prev").addEventListener("click", () => shift(-1));
  $("#s-next").addEventListener("click", () => shift(1));
  if ($("#pay-btn")) $("#pay-btn").addEventListener("click", () => payModal(st));
}

function payModal(st) {
  const sources = state.accounts.filter(a => a.type !== "credit" && !a.archived);
  if (!sources.length) { toast("Crie uma conta para pagar a partir dela."); return; }
  openModal(`
    <div class="modal-head"><h3>Pagar fatura ${monthLabel(st.month)}</h3></div>
    <div class="modal-body">
      <div class="field"><label>Pagar de qual conta?</label><select id="p-src">${sources.map(a => `<option value="${a.id}">${a.name} — ${brl(a.balance)}</option>`).join("")}</select></div>
      <div class="row2">
        <div class="field"><label>Valor (R$)</label><input id="p-amount" type="number" step="0.01" value="${st.remaining.toFixed(2)}"></div>
        <div class="field"><label>Data</label><input id="p-date" type="date" value="${todayISO()}"></div>
      </div>
      <div class="modal-foot"><button class="btn" onclick="closeModal()">Cancelar</button><button class="btn btn-gold" id="p-save">Confirmar pagamento</button></div>
    </div>`);
  $("#p-save").addEventListener("click", async () => {
    const amount = parseFloat($("#p-amount").value.replace(",", ".")) || 0;
    if (!amount) { toast("Informe um valor."); return; }
    await api.post(`/cards/${cardState.id}/pay`, {
      from_account_id: +$("#p-src").value, amount, date: $("#p-date").value, statement_month: st.month,
    });
    closeModal(); toast("Fatura paga!"); renderCards();
  });
}

/* ============ CATEGORIAS ============ */
async function renderCategories() {
  $("#topbar-actions").innerHTML = `<button class="btn btn-gold" id="add-grp">+ Grupo</button>`;
  $("#add-grp").addEventListener("click", async () => { const n = prompt("Nome do grupo:"); if (n) { await api.post("/category-groups", { name: n }); render(); } });
  $("#view").innerHTML = state.categories.map(g => `<div class="panel" style="margin-bottom:14px">
    <div class="panel-head"><h3>${g.name}</h3>
      <div><button class="btn btn-sm" data-addcat="${g.id}">+ Categoria</button>
        <button class="icon-btn" data-delgrp="${g.id}">🗑</button></div></div>
    <table><tbody>${g.categories.map(c => `<tr><td>${c.name}</td>
      <td class="right"><button class="icon-btn" data-editcat="${c.id}" data-name="${esc(c.name)}">✎</button>
      <button class="icon-btn" data-delcat="${c.id}">🗑</button></td></tr>`).join("") || '<tr><td class="empty">Sem categorias</td></tr>'}</tbody></table>
  </div>`).join("") || '<div class="empty">Crie seu primeiro grupo de categorias.</div>';

  $$("[data-addcat]").forEach(b => b.addEventListener("click", async () => { const n = prompt("Nome da categoria:"); if (n) { await api.post("/categories", { group_id: +b.dataset.addcat, name: n }); render(); } }));
  $$("[data-editcat]").forEach(b => b.addEventListener("click", async () => { const n = prompt("Novo nome:", b.dataset.name); if (n) { await api.put("/categories/" + b.dataset.editcat, { name: n }); render(); } }));
  $$("[data-delcat]").forEach(b => b.addEventListener("click", async () => { if (confirm("Excluir categoria?")) { await api.del("/categories/" + b.dataset.delcat); render(); } }));
  $$("[data-delgrp]").forEach(b => b.addEventListener("click", async () => { if (confirm("Excluir grupo e suas categorias?")) { await api.del("/category-groups/" + b.dataset.delgrp); render(); } }));
}

/* ============ IMPORTAR ============ */
function renderImport() {
  $("#view").innerHTML = `<div class="panel" style="max-width:560px">
    <div class="panel-head"><h3>Importar extrato (CSV ou OFX)</h3></div>
    <div style="padding:20px;display:flex;flex-direction:column;gap:14px">
      <div class="field"><label>Conta de destino</label><select id="imp-acc">${state.accounts.map(a => `<option value="${a.id}">${a.name}</option>`).join("")}</select></div>
      <div class="field"><label>Arquivo</label><input id="imp-file" type="file" accept=".csv,.ofx" class="btn" style="background:var(--surface-2);width:100%"></div>
      <button class="btn btn-gold" id="imp-preview">Pré-visualizar</button>
    </div></div>
    <div id="imp-result" style="margin-top:16px"></div>`;
  $("#imp-preview").addEventListener("click", async () => {
    const f = $("#imp-file").files[0]; if (!f) { toast("Escolha um arquivo."); return; }
    const fd = new FormData(); fd.append("file", f); fd.append("account_id", $("#imp-acc").value);
    $("#imp-result").innerHTML = '<div class="empty">Lendo arquivo…</div>';
    const r = await fetch("/api/import/preview", { method: "POST", body: fd }).then(x => x.json());
    if (r.error) { $("#imp-result").innerHTML = `<div class="panel"><div class="empty" style="color:var(--red)">${r.error}</div></div>`; return; }
    if (!r.items.length) { $("#imp-result").innerHTML = '<div class="panel"><div class="empty">Nenhuma transação encontrada no arquivo.</div></div>'; return; }
    const cats = flatCategories();
    const catOpts = '<option value="">—</option>' + cats.map(c => `<option value="${c.id}">${c.group} › ${c.name}</option>`).join("");
    window._impItems = r.items; window._impAcc = r.account_id;
    $("#imp-result").innerHTML = `<div class="panel">
      <div class="panel-head"><h3>${r.items.length} transações — revise e categorize</h3><button class="btn btn-gold btn-sm" id="imp-commit">Importar</button></div>
      <table><thead><tr><th>Data</th><th>Descrição</th><th class="right">Valor</th><th>Categoria</th></tr></thead>
      <tbody>${r.items.map((it, i) => `<tr style="${it.duplicate ? "opacity:.4" : ""}">
        <td class="num">${dateBR(it.date)}</td><td>${esc(it.payee)} ${it.duplicate ? '<span class="tag">duplicada</span>' : ""}</td>
        <td class="right num ${clsAmt(it.amount)}">${brl(it.amount)}</td>
        <td><select data-i="${i}" class="assign-input" style="width:auto;text-align:left" ${it.duplicate ? "disabled" : ""}>${catOpts}</select></td>
      </tr>`).join("")}</tbody></table></div>`;
    $("#imp-commit").addEventListener("click", async () => {
      const sels = {}; $$("[data-i]").forEach(s => sels[s.dataset.i] = s.value);
      const items = window._impItems.filter(it => !it.duplicate).map((it, idx) => {
        const realIdx = window._impItems.indexOf(it);
        return { ...it, category_id: sels[realIdx] ? +sels[realIdx] : null };
      });
      const res = await api.post("/import/commit", { account_id: window._impAcc, items });
      toast(`${res.added} importadas!`); route("transactions");
    });
  });
}

/* ---------- util ---------- */
function esc(s) { return (s || "").replace(/"/g, "&quot;").replace(/</g, "&lt;"); }
function monthSwitcher() {
  return `<div class="month-switch"><button id="m-prev">‹</button><span class="label" id="m-label">${monthLabel(state.month)}</span><button id="m-next">›</button></div>`;
}
function bindMonthSwitcher(cb) {
  const shift = d => { const [y, m] = state.month.split("-").map(Number); const dt = new Date(y, m - 1 + d, 1); state.month = dt.toISOString().slice(0, 7); cb(); };
  $("#m-prev")?.addEventListener("click", () => shift(-1));
  $("#m-next")?.addEventListener("click", () => shift(1));
}

window.closeModal = closeModal;
render();
