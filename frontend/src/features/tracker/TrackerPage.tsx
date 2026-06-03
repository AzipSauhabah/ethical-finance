import { useState, useEffect, useCallback } from "react";

const GOLD = "#b8962f";
const NAVY = "#0d1628";
const NAVY2 = "#111e35";
const BORDER = "#1e2d4a";
const GREEN = "#16a34a";
const RED = "#dc2626";
const API = (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_API_URL) ?? "";

// ── Types ─────────────────────────────────────────────────────────────────────
interface Portfolio { id: number; name: string; type: string; currency: string; broker: string; }
interface Transaction { id: number; ticker: string; date: string; type: string; qty: number; price: number; fees: number; currency: string; notes: string; }
interface Holding { qty: number; avg_price: number; last_price: number; unrealized_pnl: number; unrealized_pct: number; market_value: number; total_invested: number; realized_pnl: number; dividends_received: number; }
interface Analytics { holdings: Record<string, Holding>; total_invested: number; current_value: number; unrealized_pnl: number; realized_pnl: number; mwr: number; n_positions: number; dividends_total: number; }

const TX_TYPES = ["BUY","SELL","DIVIDEND","SPLIT","FEE","DEPOSIT","WITHDRAWAL"];
const PORT_TYPES = ["CTO","PEA","PEA-PME","AV","CRYPTO","OTHER"];

// ── Auth ──────────────────────────────────────────────────────────────────────
function AuthPanel({ onLogin }: { onLogin: (token: string, email: string) => void }) {
  const [mode, setMode] = useState<"login"|"register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit() {
    setLoading(true); setError("");
    const url = mode === "login" ? `${API}/auth/login` : `${API}/auth/register`;
    try {
      const r = await fetch(url, { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({email, password}) });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || "Auth error");
      onLogin(d.access_token, email);
    } catch (e: any) {
      setError(e.message);
    }
    setLoading(false);
  }

  return (
    <div style={{ minHeight:"100vh", background: NAVY, display:"flex", alignItems:"center", justifyContent:"center" }}>
      <div style={{ background: NAVY2, border:`1px solid ${BORDER}`, borderRadius:8, padding:"2rem", width:360 }}>
        <div style={{ marginBottom:"1.5rem" }}>
          <div style={{ fontSize:"0.6rem", letterSpacing:"3px", color: GOLD, fontWeight:700, marginBottom:"0.3rem" }}>PORTFOLIO TRACKER</div>
          <h2 style={{ fontSize:"1.4rem", fontWeight:800, color:"#fff", margin:0 }}>
            {mode === "login" ? "Sign In" : "Create Account"}
          </h2>
        </div>
        <div style={{ display:"flex", flexDirection:"column", gap:"0.75rem" }}>
          <input placeholder="Email" value={email} onChange={e=>setEmail(e.target.value)}
            style={{ background:"#0d1628", border:`1px solid ${BORDER}`, borderRadius:4, padding:"0.6rem 0.8rem", color:"#e2e8f0", fontSize:"0.85rem", outline:"none" }} />
          <input placeholder="Password" type="password" value={password} onChange={e=>setPassword(e.target.value)}
            onKeyDown={e=>e.key==="Enter"&&submit()}
            style={{ background:"#0d1628", border:`1px solid ${BORDER}`, borderRadius:4, padding:"0.6rem 0.8rem", color:"#e2e8f0", fontSize:"0.85rem", outline:"none" }} />
          {error && <div style={{ fontSize:"0.72rem", color:"#f87171" }}>{error}</div>}
          <button onClick={submit} disabled={loading} style={{ background: GOLD, color:"#000", border:"none", borderRadius:4, padding:"0.65rem", fontWeight:800, fontSize:"0.85rem", cursor:"pointer" }}>
            {loading ? "..." : mode === "login" ? "Sign In" : "Register"}
          </button>
          <div style={{ fontSize:"0.72rem", color:"#64748b", textAlign:"center", cursor:"pointer" }}
            onClick={()=>setMode(mode==="login"?"register":"login")}>
            {mode==="login" ? "No account? Register" : "Already have an account? Sign in"}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Portfolio selector ────────────────────────────────────────────────────────
function PortfolioSelector({ token, selected, onSelect }: { token:string; selected:Portfolio|null; onSelect:(p:Portfolio)=>void }) {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name:"", type:"CTO", currency:"EUR", broker:"" });

  const load = useCallback(() => {
    fetch(`${API}/api/tracker/portfolios`, { headers:{"Authorization":`Bearer ${token}`} })
      .then(r=>r.json()).then(d=>setPortfolios(d.portfolios||[]));
  }, [token]);

  useEffect(() => { load(); }, [load]);

  async function deletePortfolio(id: number, name: string) {
    if (!confirm(`Delete portfolio "${name}"?`)) return;
    await fetch(`${API}/api/tracker/portfolios/${id}`, {
      method:"DELETE", headers:{"Authorization":`Bearer ${token}`}
    });
    load();
  }

  async function create() {
    if (!form.name.trim()) return;
    await fetch(`${API}/api/tracker/portfolios`, {
      method:"POST", headers:{"Content-Type":"application/json","Authorization":`Bearer ${token}`},
      body: JSON.stringify(form)
    });
    setCreating(false);
    setForm({name:"",type:"CTO",currency:"EUR",broker:""});
    load();
  }

  return (
    <div style={{ display:"flex", gap:"0.5rem", alignItems:"center", flexWrap:"wrap" }}>
      {portfolios.map(p => (
        <button key={p.id} onClick={()=>onSelect(p)} style={{
          background: selected?.id===p.id ? `rgba(184,150,47,0.15)` : "transparent",
          border: `1px solid ${selected?.id===p.id ? GOLD : BORDER}`,
          color: selected?.id===p.id ? GOLD : "#94a3b8",
          borderRadius:4, padding:"0.3rem 0.75rem", fontSize:"0.75rem", cursor:"pointer", fontWeight:600
        }}>
          {p.type} — {p.name}
          <span onClick={e=>{e.stopPropagation();deletePortfolio(p.id,p.name);}} style={{ marginLeft:"0.3rem", opacity:0.5, fontSize:"0.65rem" }}>✕</span>
        </button>
      ))}
      {creating ? (
        <div style={{ display:"flex", gap:"0.4rem", alignItems:"center" }}>
          <input placeholder="Name" value={form.name} onChange={e=>setForm({...form,name:e.target.value})}
            style={{ background:"#0d1628", border:`1px solid ${BORDER}`, borderRadius:4, padding:"0.3rem 0.5rem", color:"#e2e8f0", fontSize:"0.75rem", width:120, outline:"none" }} />
          <select value={form.type} onChange={e=>setForm({...form,type:e.target.value})}
            style={{ background:"#0d1628", border:`1px solid ${BORDER}`, borderRadius:4, padding:"0.3rem", color:"#e2e8f0", fontSize:"0.75rem", outline:"none" }}>
            {PORT_TYPES.map(t=><option key={t}>{t}</option>)}
          </select>
          <>
          <input placeholder="Broker" value={form.broker} onChange={e=>setForm({...form,broker:e.target.value})} list="broker-suggestions"
            style={{ background:"#0d1628", border:`1px solid ${BORDER}`, borderRadius:4, padding:"0.3rem 0.5rem", color:"#e2e8f0", fontSize:"0.75rem", width:100, outline:"none" }} />
          <datalist id="broker-suggestions">
            {["Fortuneo","Degiro","Boursorama","Saxo","Interactive Brokers","BNP Paribas","Revolut"].map(b=><option key={b} value={b}/>)}
          </datalist>
          </>
          <button onClick={create} style={{ background: GREEN, color:"#fff", border:"none", borderRadius:4, padding:"0.3rem 0.6rem", fontSize:"0.72rem", cursor:"pointer", fontWeight:700 }}>✓</button>
          <button onClick={()=>setCreating(false)} style={{ background:"transparent", border:`1px solid ${BORDER}`, color:"#94a3b8", borderRadius:4, padding:"0.3rem 0.5rem", fontSize:"0.72rem", cursor:"pointer" }}>✕</button>
        </div>
      ) : (
        <button onClick={()=>setCreating(true)} style={{ background:"transparent", border:`1px solid ${BORDER}`, color:"#94a3b8", borderRadius:4, padding:"0.3rem 0.75rem", fontSize:"0.72rem", cursor:"pointer" }}>
          + New Portfolio
        </button>
      )}
    </div>
  );
}

// ── Transaction form ──────────────────────────────────────────────────────────
function TxForm({ token, portfolioId, onAdded }: { token:string; portfolioId:number; onAdded:()=>void }) {
  const [form, setForm] = useState({ ticker:"", date: new Date().toISOString().split("T")[0], type:"BUY", qty:"", price:"", fees:"0", currency:"USD", notes:"" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [tickerSuggestions, setTickerSuggestions] = useState<string[]>([]);

  async function searchTickers(q: string) {
    if (q.length < 1) { setTickerSuggestions([]); return; }
    try {
      const r = await fetch(`${API}/api/tickers/search?q=${q}&limit=8`);
      const d = await r.json();
      setTickerSuggestions((d.results||[]).map((t: any) => t.ticker));
    } catch { setTickerSuggestions([]); }
  }

  async function submit() {
    setError("");
    if (!form.ticker.trim()) { setError("Ticker required"); return; }
    if (!form.qty || +form.qty <= 0) { setError("Quantity must be > 0"); return; }
    if (!form.price || +form.price <= 0) { setError("Price must be > 0"); return; }
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/tracker/portfolios/${portfolioId}/transactions`, {
        method:"POST",
        headers:{"Content-Type":"application/json","Authorization":`Bearer ${token}`},
        body: JSON.stringify({...form, qty:+form.qty, price:+form.price, fees:+form.fees})
      });
      if (!r.ok) throw new Error("Server error");
      setSuccess(`✓ ${form.type} ${form.qty} ${form.ticker} @ ${form.price} added`);
      setForm({ticker:"",date:new Date().toISOString().split("T")[0],type:"BUY",qty:"",price:"",fees:"0",currency:"USD",notes:""});
      setTimeout(()=>setSuccess(""), 3000);
      onAdded();
    } catch(e: any) { setError(e.message); }
    setLoading(false);
  }

  const inp = { background:"#0d1628", border:`1px solid ${BORDER}`, borderRadius:4, padding:"0.5rem 0.6rem", color:"#e2e8f0", fontSize:"0.82rem", outline:"none", width:"100%" } as const;
  const lbl = { fontSize:"0.58rem", letterSpacing:"1.5px", color:"#94a3b8", fontWeight:700, marginBottom:"0.25rem", display:"block" } as const;

  return (
    <div style={{ background: NAVY2, border:`1px solid ${BORDER}`, borderRadius:8, padding:"1rem 1.25rem" }}>
      <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:"0.75rem" }}>
        <span style={{ fontSize:"0.6rem", letterSpacing:"2px", color: GOLD, fontWeight:700 }}>ADD TRANSACTION</span>
        {success && <span style={{ fontSize:"0.72rem", color:"#4ade80" }}>{success}</span>}
        {error && <span style={{ fontSize:"0.72rem", color:"#f87171" }}>{error}</span>}
      </div>
      <div style={{ display:"grid", gridTemplateColumns:"1.2fr 1fr 0.8fr 0.8fr 0.8fr 0.6fr 0.6fr 1.5fr auto", gap:"0.6rem", alignItems:"end" }}>
        <div>
          <label style={lbl}>TICKER</label>
          <input value={form.ticker}
            onChange={e=>{ setForm({...form,ticker:e.target.value.toUpperCase()}); searchTickers(e.target.value); }}
            placeholder="AAPL, NVDA, MC.PA..." style={inp}
            list="ticker-suggestions"
            onKeyDown={e=>e.key==="Enter"&&submit()} />
          <datalist id="ticker-suggestions">
            {tickerSuggestions.map(t=><option key={t} value={t}/>)}
          </datalist>
        </div>
        <div>
          <label style={lbl}>DATE</label>
          <input type="date" value={form.date} onChange={e=>setForm({...form,date:e.target.value})} style={inp} />
        </div>
        <div>
          <label style={lbl}>TYPE</label>
          <select value={form.type} onChange={e=>setForm({...form,type:e.target.value})} style={inp}>
            {TX_TYPES.map(t=><option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div>
          <label style={lbl}>QUANTITY</label>
          <input type="number" min="0" step="any" value={form.qty}
            onChange={e=>setForm({...form,qty:e.target.value})} placeholder="10" style={inp} />
        </div>
        <div>
          <label style={lbl}>UNIT PRICE</label>
          <input type="number" min="0" step="any" value={form.price}
            onChange={e=>setForm({...form,price:e.target.value})} placeholder="150.00" style={inp} />
        </div>
        <div>
          <label style={lbl}>FEES</label>
          <input type="number" min="0" step="any" value={form.fees}
            onChange={e=>setForm({...form,fees:e.target.value})} placeholder="0" style={inp} />
        </div>
        <div>
          <label style={lbl}>CCY</label>
          <select value={form.currency} onChange={e=>setForm({...form,currency:e.target.value})} style={inp}>
            {["USD","EUR","GBP","CHF","JPY","CAD"].map(c=><option key={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label style={lbl}>NOTES</label>
          <input value={form.notes} onChange={e=>setForm({...form,notes:e.target.value})}
            placeholder="Optional..." style={inp} />
        </div>
        <div style={{ paddingBottom:1 }}>
          <label style={{...lbl, opacity:0}}>ADD</label>
          <button onClick={submit} disabled={loading} style={{
            background: loading ? "#333" : GOLD, color:"#000", border:"none", borderRadius:4,
            padding:"0.5rem 1rem", fontWeight:800, fontSize:"0.82rem", cursor:"pointer", width:"100%",
            whiteSpace:"nowrap"
          }}>
            {loading ? "..." : "ADD ▶"}
          </button>
        </div>
      </div>
      {/* Résumé ordre */}
      {form.ticker && form.qty && form.price && (
        <div style={{ marginTop:"0.5rem", fontSize:"0.72rem", color:"#94a3b8", fontFamily:'"JetBrains Mono",monospace' }}>
          Preview: {form.type} {form.qty}× {form.ticker} @ {form.price} {form.currency}
          {" "} = <span style={{ color: form.type==="BUY"?"#4ade80":"#f87171", fontWeight:700 }}>
            {form.type==="BUY"?"-":"+"}
            {((+form.qty*(+form.price))+(+form.fees)).toFixed(2)} {form.currency}
          </span>
          {+form.fees > 0 && <span style={{ color:"#f87171" }}> (incl. {form.fees} fees)</span>}
        </div>
      )}
    </div>
  );
}

// ── Holdings table ────────────────────────────────────────────────────────────
function HoldingsTable({ analytics }: { analytics: Analytics | null }) {
  if (!analytics) return null;
  const holdings = analytics.holdings || {};
  const total_invested = analytics.total_invested || 0;
  const current_value = analytics.current_value || 0;
  const unrealized_pnl = analytics.unrealized_pnl || 0;
  const realized_pnl = analytics.realized_pnl || 0;
  const mwr = analytics.mwr || 0;
  const total_pnl = unrealized_pnl + realized_pnl;
  const total_pct = total_invested > 0 ? (total_pnl / total_invested) * 100 : 0;

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:"1rem" }}>
      {/* Summary cards */}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(5,1fr)", gap:"0.5rem" }}>
        {[
          { label:"INVESTED", value:`€${total_invested.toLocaleString("fr-FR",{maximumFractionDigits:0})}`, color:"#94a3b8" },
          { label:"MARKET VALUE", value:`€${current_value.toLocaleString("fr-FR",{maximumFractionDigits:0})}`, color:"#e2e8f0" },
          { label:"UNREALIZED P&L", value:`${unrealized_pnl>=0?"+":""}€${unrealized_pnl.toLocaleString("fr-FR",{maximumFractionDigits:0})}`, color: unrealized_pnl>=0?"#4ade80":"#f87171" },
          { label:"REALIZED P&L", value:`${realized_pnl>=0?"+":""}€${realized_pnl.toLocaleString("fr-FR",{maximumFractionDigits:0})}`, color: realized_pnl>=0?"#4ade80":"#f87171" },
          { label:"MWR", value:`${mwr>=0?"+":""}${mwr}%`, color: mwr>=0?"#4ade80":"#f87171" },
          { label:"DIVIDENDS", value:`+€${((analytics as any).dividends_total||0).toFixed(0)}`, color:"#4ade80" },
        ].map(c=>(
          <div key={c.label} style={{ background: NAVY2, border:`1px solid ${BORDER}`, borderRadius:6, padding:"0.6rem 0.8rem" }}>
            <div style={{ fontSize:"0.55rem", letterSpacing:"2px", color:"#94a3b8", marginBottom:"0.2rem" }}>{c.label}</div>
            <div style={{ fontSize:"1rem", fontWeight:800, color:c.color, fontFamily:'"JetBrains Mono",monospace' }}>{c.value}</div>
          </div>
        ))}
      </div>

      {/* Holdings table */}
      <div style={{ background: NAVY2, border:`1px solid ${BORDER}`, borderRadius:6, overflow:"hidden" }}>
        <table style={{ width:"100%", borderCollapse:"collapse", fontSize:"0.78rem" }}>
          <thead>
            <tr style={{ background:"#0d1528", borderBottom:`1px solid ${BORDER}` }}>
              {["TICKER","QTY","AVG PRICE","LAST PRICE","MARKET VALUE","UNREAL. P&L","UNREAL. %","DIVID.","WEIGHT"].map(h=>(
                <th key={h} style={{ padding:"0.6rem 0.8rem", textAlign:"left", fontSize:"0.6rem", letterSpacing:"1.5px", color:"#94a3b8", fontWeight:700 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Object.entries(holdings).map(([ticker, h], i) => {
              const weight = current_value > 0 ? (h.market_value / current_value * 100) : 0;
              return (
                <tr key={ticker} style={{ borderBottom:`1px solid ${BORDER}`, background: i%2===0?"transparent":"rgba(255,255,255,0.01)" }}>
                  <td style={{ padding:"0.6rem 0.8rem", fontFamily:'"JetBrains Mono",monospace', fontWeight:700, color: GOLD }}>{ticker}</td>
                  <td style={{ padding:"0.6rem 0.8rem", fontFamily:'"JetBrains Mono",monospace', color:"#e2e8f0" }}>{h.qty.toFixed(4)}</td>
                  <td style={{ padding:"0.6rem 0.8rem", fontFamily:'"JetBrains Mono",monospace', color:"#94a3b8" }}>{h.avg_price.toFixed(2)}</td>
                  <td style={{ padding:"0.6rem 0.8rem", fontFamily:'"JetBrains Mono",monospace', color:"#e2e8f0" }}>{h.last_price.toFixed(2)}</td>
                  <td style={{ padding:"0.6rem 0.8rem", fontFamily:'"JetBrains Mono",monospace', color:"#e2e8f0" }}>{h.market_value.toLocaleString("fr-FR",{maximumFractionDigits:0})}</td>
                  <td style={{ padding:"0.6rem 0.8rem", fontFamily:'"JetBrains Mono",monospace', color: h.unrealized_pnl>=0?"#4ade80":"#f87171" }}>
                    {h.unrealized_pnl>=0?"+":""}{h.unrealized_pnl.toFixed(0)}
                  </td>
                  <td style={{ padding:"0.6rem 0.8rem", fontFamily:'"JetBrains Mono",monospace', color: h.unrealized_pct>=0?"#4ade80":"#f87171" }}>
                    {h.unrealized_pct>=0?"+":""}{h.unrealized_pct.toFixed(2)}%
                  </td>
                  <td style={{ padding:"0.6rem 0.8rem", fontFamily:'"JetBrains Mono",monospace', color:"#4ade80", fontSize:"0.72rem" }}>
                    {h.dividends_received > 0 ? `+${h.dividends_received.toFixed(0)}` : "—"}
                  </td>
                  <td style={{ padding:"0.6rem 0.8rem" }}>
                    <div style={{ display:"flex", alignItems:"center", gap:"0.4rem" }}>
                      <div style={{ flex:1, height:4, background:"#0d1628", borderRadius:2 }}>
                        <div style={{ height:"100%", width:`${Math.min(weight,100)}%`, background: GOLD, borderRadius:2 }} />
                      </div>
                      <span style={{ fontSize:"0.65rem", color:"#94a3b8", fontFamily:'"JetBrains Mono",monospace', width:35 }}>{weight.toFixed(1)}%</span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Transactions log ──────────────────────────────────────────────────────────
function TxLog({ token, portfolioId, refresh }: { token:string; portfolioId:number; refresh:number }) {
  const [txs, setTxs] = useState<Transaction[]>([]);

  useEffect(() => {
    fetch(`${API}/api/tracker/portfolios/${portfolioId}/transactions`, {
      headers:{"Authorization":`Bearer ${token}`}
    }).then(r=>r.json()).then(d=>setTxs(d.transactions||[]));
  }, [portfolioId, token, refresh]);

  async function deleteTx(id: number) {
    await fetch(`${API}/api/tracker/portfolios/${portfolioId}/transactions/${id}`, {
      method:"DELETE", headers:{"Authorization":`Bearer ${token}`}
    });
    setTxs(prev=>prev.filter(t=>t.id!==id));
  }

  return (
    <div style={{ background: NAVY2, border:`1px solid ${BORDER}`, borderRadius:6, overflow:"hidden" }}>
      <div style={{ padding:"0.6rem 1rem", background:"#0d1528", borderBottom:`1px solid ${BORDER}` }}>
        <span style={{ fontSize:"0.6rem", letterSpacing:"2px", color:"#94a3b8", fontWeight:700 }}>TRANSACTION LOG — {txs.length} entries</span>
      </div>
      <div style={{ maxHeight:300, overflowY:"auto" }}>
        <table style={{ width:"100%", borderCollapse:"collapse", fontSize:"0.75rem" }}>
          <thead>
            <tr style={{ background:"#0d1528" }}>
              {["DATE","TICKER","TYPE","QTY","PRICE","FEES","CCY","NOTES",""].map(h=>(
                <th key={h} style={{ padding:"0.5rem 0.7rem", textAlign:"left", fontSize:"0.58rem", letterSpacing:"1.5px", color:"#94a3b8", fontWeight:700, borderBottom:`1px solid ${BORDER}` }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {txs.map((tx,i)=>(
              <tr key={tx.id} style={{ borderBottom:`1px solid ${BORDER}`, background:i%2===0?"transparent":"rgba(255,255,255,0.01)" }}>
                <td style={{ padding:"0.4rem 0.7rem", fontFamily:'"JetBrains Mono",monospace', color:"#94a3b8" }}>{tx.date}</td>
                <td style={{ padding:"0.4rem 0.7rem", fontFamily:'"JetBrains Mono",monospace', fontWeight:700, color: GOLD }}>{tx.ticker}</td>
                <td style={{ padding:"0.4rem 0.7rem" }}>
                  <span style={{ fontSize:"0.65rem", fontWeight:700, padding:"0.1rem 0.4rem", borderRadius:3,
                    background: tx.type==="BUY"?"rgba(22,163,74,0.2)":tx.type==="SELL"?"rgba(220,38,38,0.2)":"rgba(184,150,47,0.15)",
                    color: tx.type==="BUY"?"#4ade80":tx.type==="SELL"?"#f87171": GOLD
                  }}>{tx.type}</span>
                </td>
                <td style={{ padding:"0.4rem 0.7rem", fontFamily:'"JetBrains Mono",monospace', color:"#e2e8f0" }}>{tx.qty}</td>
                <td style={{ padding:"0.4rem 0.7rem", fontFamily:'"JetBrains Mono",monospace', color:"#e2e8f0" }}>{tx.price}</td>
                <td style={{ padding:"0.4rem 0.7rem", fontFamily:'"JetBrains Mono",monospace', color:"#94a3b8" }}>{tx.fees}</td>
                <td style={{ padding:"0.4rem 0.7rem", color:"#94a3b8" }}>{tx.currency}</td>
                <td style={{ padding:"0.4rem 0.7rem", color:"#94a3b8", fontSize:"0.7rem" }}>{tx.notes}</td>
                <td style={{ padding:"0.4rem 0.7rem" }}>
                  <button onClick={()=>deleteTx(tx.id)} style={{ background:"none", border:`1px solid ${BORDER}`, color:"#94a3b8", borderRadius:3, padding:"0.1rem 0.4rem", fontSize:"0.65rem", cursor:"pointer" }}>✕</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Main TrackerPage ──────────────────────────────────────────────────────────
export default function TrackerPage() {
  const [token, setToken] = useState<string|null>(() => localStorage.getItem("tracker_token"));
  const [email, setEmail] = useState<string>(() => localStorage.getItem("tracker_email") || "");
  const [selectedPortfolio, setSelectedPortfolio] = useState<Portfolio|null>(null);
  const [analytics, setAnalytics] = useState<Analytics|null>(null);
  const [activeTab, setActiveTab] = useState<"holdings"|"transactions"|"analytics">("holdings");
  const [refreshTx, setRefreshTx] = useState(0);

  function handleLogin(t: string, e: string) {
    setToken(t); setEmail(e);
    localStorage.setItem("tracker_token", t);
    localStorage.setItem("tracker_email", e);
  }

  function logout() {
    setToken(null); setEmail("");
    localStorage.removeItem("tracker_token");
    localStorage.removeItem("tracker_email");
    setSelectedPortfolio(null); setAnalytics(null);
  }

  useEffect(() => {
    if (!token || !selectedPortfolio) return;
    fetch(`${API}/api/tracker/portfolios/${selectedPortfolio.id}/analytics`, {
      headers:{"Authorization":`Bearer ${token}`}
    }).then(r=>r.json()).then(d=>setAnalytics(d)).catch(()=>{});
  }, [token, selectedPortfolio, refreshTx]);

  if (!token) return <AuthPanel onLogin={handleLogin} />;

  return (
    <div style={{ fontFamily:'"Syne",sans-serif', padding:"1.5rem 2rem", color:"#e2e8f0", minHeight:"100vh", background: NAVY }}>
      {/* Header */}
      <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:"1.5rem" }}>
        <div>
          <div style={{ fontSize:"0.6rem", letterSpacing:"3px", color: GOLD, fontWeight:700, marginBottom:"0.2rem" }}>PORTFOLIO TRACKER</div>
          <h1 style={{ fontSize:"1.5rem", fontWeight:800, margin:0, color:"#fff" }}>My Portfolios</h1>
          <div style={{ fontSize:"0.72rem", color:"#94a3b8", marginTop:"0.2rem" }}>{email}</div>
        </div>
        <button onClick={logout} style={{ background:"transparent", border:`1px solid ${BORDER}`, color:"#94a3b8", borderRadius:4, padding:"0.4rem 0.8rem", fontSize:"0.72rem", cursor:"pointer" }}>
          Sign Out
        </button>
      </div>

      {/* Portfolio selector */}
      <div style={{ marginBottom:"1.25rem" }}>
        <PortfolioSelector token={token} selected={selectedPortfolio} onSelect={p=>{setSelectedPortfolio(p);setAnalytics(null);}} />
      </div>

      {!selectedPortfolio ? (
        <div style={{ textAlign:"center", padding:"4rem", color:"#94a3b8" }}>
          <div style={{ fontSize:"2rem", marginBottom:"1rem", opacity:0.3 }}>◎</div>
          <div style={{ fontSize:"0.85rem" }}>Select or create a portfolio to get started</div>
        </div>
      ) : (
        <>
          {/* Transaction form */}
          <div style={{ marginBottom:"1rem" }}>
            <TxForm token={token} portfolioId={selectedPortfolio.id} onAdded={()=>setRefreshTx(r=>r+1)} />
          </div>

          {/* Tabs */}
          <div style={{ display:"flex", gap:0, borderBottom:`1px solid ${BORDER}`, marginBottom:"1rem" }}>
            {[["holdings","Holdings"],["transactions","Transactions"],["analytics","Analytics"]].map(([id,label])=>(
              <button key={id} onClick={()=>setActiveTab(id as typeof activeTab)} style={{
                padding:"0.5rem 1.2rem", fontSize:"0.72rem", fontWeight:600, letterSpacing:"1px",
                color: activeTab===id ? GOLD : "#94a3b8",
                background:"none", border:"none", cursor:"pointer",
                borderBottom: activeTab===id ? `2px solid ${GOLD}` : "2px solid transparent",
              }}>{label.toUpperCase()}</button>
            ))}
          </div>

          {activeTab==="holdings" && <HoldingsTable analytics={analytics} />}
          {activeTab==="transactions" && <TxLog token={token} portfolioId={selectedPortfolio.id} refresh={refreshTx} />}
          {activeTab==="analytics" && analytics && (
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"1rem" }}>
              <div style={{ background: NAVY2, border:`1px solid ${BORDER}`, borderRadius:6, padding:"1rem" }}>
                <div style={{ fontSize:"0.6rem", letterSpacing:"2px", color:"#94a3b8", fontWeight:700, marginBottom:"0.75rem" }}>PERFORMANCE</div>
                {[
                  { label:"Money-Weighted Return", value:`${analytics.mwr>=0?"+":""}${analytics.mwr}%`, color: analytics.mwr>=0?"#4ade80":"#f87171" },
                  { label:"Total P&L", value:`${(analytics.unrealized_pnl+analytics.realized_pnl)>=0?"+":""}€${(analytics.unrealized_pnl+analytics.realized_pnl).toFixed(0)}`, color:(analytics.unrealized_pnl+analytics.realized_pnl)>=0?"#4ade80":"#f87171" },
                  { label:"Unrealized P&L", value:`${analytics.unrealized_pnl>=0?"+":""}€${analytics.unrealized_pnl.toFixed(0)}`, color: analytics.unrealized_pnl>=0?"#4ade80":"#f87171" },
                  { label:"Realized P&L", value:`${analytics.realized_pnl>=0?"+":""}€${analytics.realized_pnl.toFixed(0)}`, color: analytics.realized_pnl>=0?"#4ade80":"#f87171" },
                  { label:"Positions", value:`${analytics.n_positions}`, color:"#94a3b8" },
                ].map(item=>(
                  <div key={item.label} style={{ display:"flex", justifyContent:"space-between", padding:"0.4rem 0", borderBottom:`1px solid ${BORDER}` }}>
                    <span style={{ fontSize:"0.75rem", color:"#94a3b8" }}>{item.label}</span>
                    <span style={{ fontSize:"0.85rem", fontWeight:700, color:item.color, fontFamily:'"JetBrains Mono",monospace' }}>{item.value}</span>
                  </div>
                ))}
              </div>
              <div style={{ background: NAVY2, border:`1px solid ${BORDER}`, borderRadius:6, padding:"1rem" }}>
                <div style={{ fontSize:"0.6rem", letterSpacing:"2px", color:"#94a3b8", fontWeight:700, marginBottom:"0.75rem" }}>ALLOCATION</div>
                {Object.entries(analytics.holdings).map(([ticker, h]) => {
                  const weight = analytics.current_value > 0 ? h.market_value/analytics.current_value*100 : 0;
                  return (
                    <div key={ticker} style={{ marginBottom:"0.5rem" }}>
                      <div style={{ display:"flex", justifyContent:"space-between", marginBottom:"0.15rem" }}>
                        <span style={{ fontSize:"0.72rem", color: GOLD, fontWeight:700 }}>{ticker}</span>
                        <span style={{ fontSize:"0.72rem", color:"#94a3b8" }}>{weight.toFixed(1)}%</span>
                      </div>
                      <div style={{ height:4, background:"#0d1628", borderRadius:2 }}>
                        <div style={{ height:"100%", width:`${Math.min(weight,100)}%`, background: GOLD, borderRadius:2 }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
