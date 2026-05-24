import { useState, useEffect } from 'react';
import { api } from '../utils/api';
import { useLiveQuotes } from '../hooks/useLiveQuotes';
import type { TickerScreenResult } from '../types';

const API = (import.meta as any).env?.VITE_API_URL || "";

interface Props { tickers: string[]; setTickers: (t: string[]) => void; }

const N = '#0a0f1e', NAVY = '#142340', GOLD = '#b8962f', GREEN = '#1d8c41', RED = '#b82424', LIGHT = '#1a2035';

// ─── Position réelle ──────────────────────────────────────────────────────────
interface Position {
  ticker: string;
  qty: number;
  avg_price: number;
  currency: string;
}

// ─── Auth token (localStorage) ───────────────────────────────────────────────
function getToken(): string | null {
  try { return localStorage.getItem("eth_jwt"); } catch { return null; }
}
function setToken(t: string) {
  try { localStorage.setItem("eth_jwt", t); } catch {}
}
function clearToken() {
  try { localStorage.removeItem("eth_jwt"); } catch {}
}


function IslamicBadgeMini({ passed }: { passed?: boolean | null }) {
  const c = passed === true  ? { bg:"#14532d", border:"#16a34a", color:"#4ade80", icon:"✓" }
          : passed === false ? { bg:"#450a0a", border:"#dc2626", color:"#f87171", icon:"x" }
          : { bg:"#1a1a1a", border:"#333", color:"#555", icon:"?" };
  return (
    <span title={passed === true ? "Conforme Finance Islamique" : passed === false ? "Non conforme" : "Donnees insuffisantes"}
      style={{ display:"inline-flex", alignItems:"center", justifyContent:"center",
        width:22, height:22, borderRadius:4,
        background:c.bg, color:c.color, border:"1px solid "+c.border,
        fontSize:12, fontWeight:700, cursor:"pointer" }}>
      {c.icon}
    </span>
  );
}

function BuffettPanel({ data, colSpan }: { data: any; colSpan: number }) {
  if (!data) return (
    <tr><td colSpan={colSpan} style={{ padding: "0.5rem 1rem", background: "#060b14" }}>
      <div style={{ fontSize: "0.7rem", color: "#555", padding: "0.5rem 1rem" }}>Chargement Buffett Score...</div>
    </td></tr>
  );
  const GOLD = "#b8962f";
  return (
    <tr>
      <td colSpan={colSpan} style={{ padding: 0, background: "#060b14" }}>
        <div style={{ margin: "0 1rem 0.75rem", border: "1px solid #2a1f0a", borderRadius: 8, overflow: "hidden" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0.6rem 1rem", background: "rgba(184,150,47,0.08)", borderBottom: "1px solid #2a1f0a" }}>
            <span style={{ fontSize: "0.63rem", letterSpacing: "2px", color: "#555", fontWeight: 700 }}>BUFFETT SCORE — QUALITE FONDAMENTALE</span>
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
              <span style={{ fontSize: "0.7rem", color: "#666" }}>{data.verdict}</span>
              <span style={{ fontSize: "1rem", fontWeight: 800, color: data.color, fontFamily: '"JetBrains Mono", monospace' }}>{data.score}<span style={{ fontSize: "0.6rem", color: "#555" }}>/100</span></span>
            </div>
          </div>
          <div style={{ height: 4, background: "#111" }}>
            <div style={{ height: "100%", width: data.score + "%", background: data.color, transition: "width 0.5s" }} />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)" }}>
            {(data.checks || []).map((chk: any, i: number) => {
              const pct = chk.pts / chk.max;
              return (
                <div key={chk.id} style={{ padding: "0.75rem 1rem", borderRight: i < 3 ? "1px solid #1e1a0a" : "none" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.4rem" }}>
                    <span style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: 16, height: 16, borderRadius: "50%", background: "rgba(184,150,47,0.15)", color: GOLD, fontSize: 9, fontWeight: 800, border: "1px solid #2a1f0a", flexShrink: 0 }}>{chk.icon}</span>
                    <span style={{ fontSize: "0.6rem", fontWeight: 700, color: "#999" }}>{chk.label}</span>
                  </div>
                  <div style={{ fontSize: "0.65rem", color: "#666", marginBottom: "0.4rem" }}>{chk.detail}</div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.2rem" }}>
                    <span style={{ fontSize: "0.8rem", fontWeight: 800, color: GOLD, fontFamily: '"JetBrains Mono", monospace' }}>{chk.pts}</span>
                    <span style={{ fontSize: "0.58rem", color: "#333" }}>/ {chk.max}</span>
                  </div>
                  <div style={{ height: 4, background: "#111", borderRadius: 2, overflow: "hidden" }}>
                    <div style={{ height: "100%", width: (pct * 100) + "%", background: pct > 0.7 ? "#16a34a" : pct > 0.4 ? "#ca8a04" : "#dc2626", borderRadius: 2, transition: "width 0.4s" }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </td>
    </tr>
  );
}

function IslamicFinancePanelPortfolio({ s, colSpan }: { s: any; colSpan: number }) {
  const checks = s.sharia?.checks || [];
  const overall = s.is_sharia;
  const CRITERIA = [
    { id:1, icon:"H", label:"ACTIVITE", threshold: null },
    { id:2, icon:"D", label:"DETTE PORTANT INTERETS", threshold: 0.33 },
    { id:3, icon:"L", label:"LIQUIDITES PORTANT INTERETS", threshold: 0.33 },
    { id:4, icon:"R", label:"REVENUS NON-PERMISSIBLES", threshold: 0.05 },
  ];
  return (
    <tr>
      <td colSpan={colSpan} style={{ padding:0, background:"#060b14" }}>
        <div style={{
          margin:"0 1rem 0.75rem",
          border:"1px solid "+(overall===true?"#14532d":overall===false?"#450a0a":"#1e2d4a"),
          borderRadius:8, overflow:"hidden",
        }}>
          <div style={{
            display:"flex", alignItems:"center", justifyContent:"space-between",
            padding:"0.6rem 1rem",
            background:overall===true?"rgba(20,83,45,0.25)":overall===false?"rgba(69,10,10,0.25)":"rgba(30,45,74,0.2)",
            borderBottom:"1px solid #1e2d4a",
          }}>
            <span style={{ fontSize:"0.63rem", letterSpacing:"2px", color:"#555", fontWeight:700 }}>
              FINANCE ISLAMIQUE - CONFORMITE AAOIFI
            </span>
            <span style={{ fontSize:"0.7rem", fontWeight:800,
              color:overall===true?"#4ade80":overall===false?"#f87171":"#555" }}>
              {overall===true?"CONFORME":overall===false?"NON CONFORME":"INDETERMINE"}
            </span>
          </div>
          <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)" }}>
            {CRITERIA.map((crit, i) => {
              const chk = checks.find((c: any) => c.name.startsWith(String(crit.id)+"."));
              const passed = chk?.passed;
              const val = chk?.value;
              const tc = passed===true?"#4ade80":passed===false?"#f87171":"#555";
              const bc = passed===true?"#16a34a":passed===false?"#dc2626":"#2a2a2a";
              const pct = val!=null && crit.threshold ? Math.min(val/crit.threshold,1.5) : null;
              return (
                <div key={crit.id} style={{ padding:"0.75rem 1rem", borderRight:i<3?"1px solid #1e2d4a":"none" }}>
                  <div style={{ display:"flex", alignItems:"center", gap:"0.4rem", marginBottom:"0.4rem" }}>
                    <span style={{
                      display:"inline-flex", alignItems:"center", justifyContent:"center",
                      width:16, height:16, borderRadius:"50%",
                      background:passed===true?"rgba(20,83,45,0.6)":passed===false?"rgba(69,10,10,0.6)":"#111",
                      color:tc, fontSize:9, fontWeight:800, border:"1px solid "+bc, flexShrink:0,
                    }}>{passed===true?"v":passed===false?"x":"?"}</span>
                    <span style={{ fontSize:"0.6rem", fontWeight:700, color:"#999" }}>{crit.label}</span>
                  </div>
                  {chk?.description && (
                    <div style={{ fontSize:"0.62rem", color:"#555", marginBottom:"0.4rem", lineHeight:1.4 }}>
                      {chk.description.length > 90 ? chk.description.slice(0,90)+"..." : chk.description}
                    </div>
                  )}
                  {val!=null && crit.threshold!=null && (
                    <>
                      <div style={{ display:"flex", justifyContent:"space-between", marginBottom:"0.2rem" }}>
                        <span style={{ fontSize:"0.8rem", fontWeight:800, color:tc, fontFamily:'"JetBrains Mono",monospace' }}>
                          {(val*100).toFixed(1)}%
                        </span>
                        <span style={{ fontSize:"0.58rem", color:"#333" }}>seuil {(crit.threshold*100).toFixed(0)}%</span>
                      </div>
                      <div style={{ height:4, background:"#111", borderRadius:2, overflow:"hidden" }}>
                        <div style={{ height:"100%", width:Math.min((pct||0)*100,100)+"%",
                          background:bc, borderRadius:2, transition:"width 0.4s" }}/>
                      </div>
                    </>
                  )}
                </div>
              );
            })}
          </div>
          {s.revenue_segments && Object.keys(s.revenue_segments).length > 0 && (
            <div style={{ padding:"0.5rem 1rem", borderTop:"1px solid #1e2d4a" }}>
              <div style={{ fontSize:"0.6rem", color:"#444", marginBottom:"0.3rem", letterSpacing:"1px" }}>SEGMENTS DE REVENUS</div>
              <div style={{ display:"flex", flexWrap:"wrap", gap:"0.4rem" }}>
                {Object.entries(s.revenue_segments).sort(([,a],[,b]) => (b as number)-(a as number)).map(([name, ratio]) => (
                  <span key={name} style={{ fontSize:"0.62rem", padding:"0.15rem 0.5rem", borderRadius:3,
                    background:"rgba(20,83,45,0.3)", color:"#4ade80", border:"1px solid #16a34a" }}>
                    {name} ({((ratio as number)*100).toFixed(0)}%)
                  </span>
                ))}
              </div>
            </div>
          )}
          <div style={{ padding:"0.35rem 1rem", borderTop:"1px solid #1e2d4a", display:"flex", justifyContent:"space-between" }}>
            <span style={{ fontSize:"0.58rem", color:"#252525" }}>AAOIFI - 4 criteres cumulatifs</span>
            <span style={{ fontSize:"0.58rem", color:"#252525" }}>Sources : ESEF - SEC EDGAR - MAJ hebdomadaire</span>
          </div>
        </div>
      </td>
    </tr>
  );
}

export default function TickerManager({ tickers, setTickers }: Props) {
  const [input, setInput]     = useState('');
  const [suggestions, setSuggestions] = useState<{ticker: string, name: string, sector: string}[]>([]);
  const [showSugg, setShowSugg]       = useState(false);
  const [suggLoad, setSuggLoad]       = useState(false);
  const [loading, setLoad]    = useState(false);
  const [screened, setScrn]   = useState<TickerScreenResult[]>([]);
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null);
  const [expandedBuffett, setExpandedBuffett] = useState<string | null>(null);
  const [buffettCache, setBuffettCache] = useState<Record<string, any>>({});
  const quotes                = useLiveQuotes(tickers);

  // Auth
  const [token, setTokenState]   = useState<string | null>(getToken());
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [showAuth, setShowAuth]   = useState(false);
  const [authMode, setAuthMode]   = useState<'login' | 'register'>('login');
  const [authEmail, setAuthEmail] = useState('');
  const [authPass, setAuthPass]   = useState('');
  const [authError, setAuthError] = useState('');
  const [authLoading, setAuthLoading] = useState(false);

  // Positions
  const [positions, setPositions] = useState<Map<string, Position>>(new Map());
  const [posLoading, setPosLoading] = useState(false);

  // ── Charger email depuis token ───────────────────────────────────────────
  useEffect(() => {
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        setUserEmail(payload.email);
      } catch { clearToken(); setTokenState(null); }
    }
  }, [token]);

  // ── Charger positions depuis la base si connecté ─────────────────────────
  useEffect(() => {
    if (!token) return;
    setPosLoading(true);
    fetch(`${API}/api/portfolio/positions`, {
      headers: { Authorization: `Bearer ${token}` }
    })
      .then(r => r.json())
      .then(data => {
        const map = new Map<string, Position>();
        const list = Array.isArray(data) ? data : [];
        list.forEach((p: any) => {
          map.set(p.ticker, { ticker: p.ticker, qty: parseFloat(p.qty), avg_price: parseFloat(p.avg_price), currency: p.currency });
        });
        setPositions(map);
      })
      .catch(console.error)
      .finally(() => setPosLoading(false));
  }, [token]);

  // ── Auth ──────────────────────────────────────────────────────────────────
  const handleAuth = async () => {
    setAuthLoading(true);
    setAuthError('');
    try {
      const endpoint = authMode === 'login' ? '/auth/login' : '/auth/register';
      const r = await fetch(`${API}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: authEmail, password: authPass }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || 'Erreur');
      setToken(data.access_token);
      setTokenState(data.access_token);
      setShowAuth(false);
      setAuthEmail(''); setAuthPass('');
    } catch (e: any) {
      setAuthError(e.message);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    clearToken();
    setTokenState(null);
    setUserEmail(null);
    setPositions(new Map());
  };

  // ── Sauvegarder position ──────────────────────────────────────────────────
  const savePosition = async (ticker: string, qty: number, avg_price: number) => {
    if (!token || qty <= 0 || avg_price <= 0) return;
    try {
      await fetch(`${API}/api/portfolio/positions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ ticker, qty, avg_price, currency: 'EUR' }),
      });
    } catch (e) { console.error(e); }
  };

  const updatePosition = (ticker: string, field: 'qty' | 'avg_price', value: number) => {
    setPositions(prev => {
      const next = new Map(prev);
      const existing = next.get(ticker) || { ticker, qty: 0, avg_price: 0, currency: 'EUR' };
      next.set(ticker, { ...existing, [field]: value });
      return next;
    });
  };

  // ── Tickers ───────────────────────────────────────────────────────────────
  const add = async () => {
    const newOnes = input.split(/[\s,]+/).map(t => t.trim().toUpperCase()).filter(t => t && !tickers.includes(t));
    if (!newOnes.length) return;
    setLoad(true);
    try {
      const all = [...tickers, ...newOnes];
      setTickers(all);
      const r = await api.screenTickers(all);
      setScrn(r.tickers);
    } catch(e) { console.error(e); }
    finally { setLoad(false); setInput(''); }
  };

  const searchTickers = async (q: string) => {
    setInput(q);
    if (q.length < 1) { setSuggestions([]); setShowSugg(false); return; }
    setSuggLoad(true);
    try {
      const r = await fetch(`${import.meta.env.VITE_API_URL}/api/tickers/search?q=${encodeURIComponent(q)}`);
      const data = await r.json();
      setSuggestions(data.results || []);
      setShowSugg(true);
    } catch(e) { setSuggestions([]); }
    finally { setSuggLoad(false); }
  };

  const selectTicker = async (ticker: string) => {
    setInput('');
    setSuggestions([]);
    setShowSugg(false);
    if (tickers.includes(ticker)) return;
    setLoad(true);
    try {
      const all = [...tickers, ticker];
      setTickers(all);
      const r = await fetch(`${import.meta.env.VITE_API_URL}/api/tickers/screen`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tickers: all }),
      });
      const data = await r.json();
      setScrn(data.tickers);
    } catch(e) { console.error(e); }
    finally { setLoad(false); }
  };

  const remove = (t: string) => {
    setTickers(tickers.filter(x => x !== t));
    setScrn(screened.filter(x => x.ticker !== t));
    setPositions(prev => { const next = new Map(prev); next.delete(t); return next; });
  };

  const fmt = (v?: number) => v && v > 0 ? v.toFixed(2) : '—';

  // ── Calculs P&L ───────────────────────────────────────────────────────────
  const totalPnl = tickers.reduce((sum, t) => {
    const pos = positions.get(t);
    const q = quotes[t];
    const last = q?.last && q.last > 0 ? q.last : 0;
    if (!pos || !last) return sum;
    return sum + (last - pos.avg_price) * pos.qty;
  }, 0);

  const totalValue = tickers.reduce((sum, t) => {
    const pos = positions.get(t);
    const q = quotes[t];
    const last = q?.last && q.last > 0 ? q.last : 0;
    if (!pos || !last) return sum;
    return sum + last * pos.qty;
  }, 0);

  const totalCost = tickers.reduce((sum, t) => {
    const pos = positions.get(t);
    if (!pos) return sum;
    return sum + pos.avg_price * pos.qty;
  }, 0);

  return (
    <div style={{ padding: '2rem', maxWidth: 1400, margin: '0 auto' }}>

      {/* ── Header ── */}
      <div style={{ marginBottom: '2rem', borderBottom: '1px solid #1a2035', paddingBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <div>
          <div style={{ fontSize: '0.65rem', letterSpacing: '3px', color: GOLD, marginBottom: 4 }}>SURVEILLANCE</div>
          <h2 style={{ margin: 0, fontSize: '1.8rem', fontFamily: '"Playfair Display", serif', color: '#e8e8e8', fontWeight: 400 }}>
            Univers d'investissement
          </h2>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          {/* Auth */}
          {token ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 11, color: '#22c55e', fontFamily: 'monospace' }}>● {userEmail}</span>
              <button onClick={handleLogout} style={{ background: 'none', border: '1px solid #2a3555', color: '#666', cursor: 'pointer', borderRadius: 4, padding: '4px 10px', fontSize: 11 }}>
                Déconnexion
              </button>
            </div>
          ) : (
            <button onClick={() => setShowAuth(true)} style={{
              background: 'rgba(184,150,47,0.15)', border: '1px solid rgba(184,150,47,0.4)',
              color: GOLD, cursor: 'pointer', borderRadius: 4, padding: '6px 14px', fontSize: 12, fontFamily: 'monospace',
            }}>
              🔒 Se connecter
            </button>
          )}
          <div style={{ position: 'relative' }}>
            <input value={input} onChange={e => searchTickers(e.target.value)}
              onBlur={() => setTimeout(() => setShowSugg(false), 150)}
              onFocus={() => input.length > 0 && setShowSugg(true)}
              placeholder="Rechercher un ticker…"
              autoComplete="new-password"
              autoCorrect="off"
              autoCapitalize="characters"
              spellCheck={false}
              name={`ticker-search-${Math.random()}`}
              style={{ width: 280, padding: '0.6rem 1rem', background: '#1a2035', border: '1px solid #2a3555', borderRadius: 4, color: '#e8e8e8', fontSize: '0.85rem' }}
            />
            {showSugg && suggestions.length > 0 && (
              <div style={{
                position: 'absolute', top: '100%', left: 0, width: 360,
                background: '#0d1528', border: '1px solid #2a3555', borderRadius: 4,
                zIndex: 1000, maxHeight: 280, overflowY: 'auto', marginTop: 2,
              }}>
                {suggestions.map(s => (
                  <div key={s.ticker} onMouseDown={() => selectTicker(s.ticker)}
                    style={{
                      padding: '8px 14px', cursor: 'pointer', display: 'flex',
                      justifyContent: 'space-between', alignItems: 'center',
                      borderBottom: '1px solid #1a2035',
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = '#1a2035')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                  >
                    <span style={{ fontFamily: 'monospace', fontWeight: 700, color: '#e8e8e8', fontSize: 13 }}>{s.ticker}</span>
                    <span style={{ color: '#666', fontSize: 11, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.name}</span>
                  </div>
                ))}
              </div>
            )}
            {suggLoad && (
              <div style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', color: '#666', fontSize: 12 }}>…</div>
            )}
          </div>
        </div>
      </div>

      {/* ── Auth modal ── */}
      {showAuth && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 1000,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }} onClick={() => setShowAuth(false)}>
          <div onClick={e => e.stopPropagation()} style={{
            background: '#0d1528', border: '1px solid #2a3555', borderRadius: 12,
            padding: '32px 40px', width: 380,
          }}>
            <h3 style={{ margin: '0 0 20px', color: '#e8e8e8', fontFamily: '"Playfair Display", serif', fontWeight: 400 }}>
              {authMode === 'login' ? 'Connexion' : 'Créer un compte'}
            </h3>
            <div style={{ display: 'flex', gap: 6, marginBottom: 20 }}>
              {(['login', 'register'] as const).map(m => (
                <button key={m} onClick={() => setAuthMode(m)} style={{
                  flex: 1, background: authMode === m ? GOLD : 'transparent',
                  color: authMode === m ? '#000' : '#666', border: `1px solid ${authMode === m ? GOLD : '#2a3555'}`,
                  borderRadius: 4, padding: '6px', fontSize: 12, cursor: 'pointer', fontWeight: authMode === m ? 700 : 400,
                }}>
                  {m === 'login' ? 'Connexion' : 'Inscription'}
                </button>
              ))}
            </div>
            <input type="email" placeholder="Email" value={authEmail} onChange={e => setAuthEmail(e.target.value)}
              style={{ width: '100%', marginBottom: 10, padding: '10px 14px', background: '#1a2035', border: '1px solid #2a3555', borderRadius: 4, color: '#e8e8e8', fontSize: 13, boxSizing: 'border-box' }}
            />
            <input type="password" placeholder="Mot de passe" value={authPass} onChange={e => setAuthPass(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleAuth()}
              style={{ width: '100%', marginBottom: 16, padding: '10px 14px', background: '#1a2035', border: '1px solid #2a3555', borderRadius: 4, color: '#e8e8e8', fontSize: 13, boxSizing: 'border-box' }}
            />
            {authError && <p style={{ color: RED, fontSize: 12, margin: '0 0 12px', fontFamily: 'monospace' }}>{authError}</p>}
            <button onClick={handleAuth} disabled={authLoading} style={{
              width: '100%', padding: '10px', background: GOLD, color: '#000',
              border: 'none', borderRadius: 4, cursor: 'pointer', fontWeight: 700, fontSize: 14,
            }}>
              {authLoading ? '…' : authMode === 'login' ? 'Se connecter' : "S'inscrire"}
            </button>
          </div>
        </div>
      )}

      {/* ── Stats bar ── */}
      {tickers.length > 0 && (
        <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
          {[
            { label: 'TITRES',   value: tickers.length },
            { label: 'ESGS', value: screened.filter(s => s.is_ethical).length },
            { label: 'FIN. ISL.',   value: screened.filter(s => s.is_sharia).length },
            { label: 'EXCLUS',   value: screened.filter(s => !s.is_ethical).length },
          ].map(stat => (
            <div key={stat.label} style={{ flex: 1, padding: '1rem 1.5rem', background: '#1a2035', borderRadius: 6, border: '1px solid #2a3555' }}>
              <div style={{ fontSize: '0.6rem', letterSpacing: '2px', color: '#666', marginBottom: 4 }}>{stat.label}</div>
              <div style={{ fontSize: '1.8rem', fontWeight: 700, color: GOLD, fontFamily: '"JetBrains Mono", monospace' }}>{stat.value}</div>
            </div>
          ))}
          {totalValue > 0 && (
            <>
              <div style={{ flex: 1, padding: '1rem 1.5rem', background: '#1a2035', borderRadius: 6, border: '1px solid #2a3555' }}>
                <div style={{ fontSize: '0.6rem', letterSpacing: '2px', color: '#666', marginBottom: 4 }}>VALEUR</div>
                <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#e8e8e8', fontFamily: '"JetBrains Mono", monospace' }}>{totalValue.toFixed(0)}€</div>
              </div>
              <div style={{ flex: 1, padding: '1rem 1.5rem', background: '#1a2035', borderRadius: 6, border: `1px solid ${totalPnl >= 0 ? '#1d8c41' : '#b82424'}` }}>
                <div style={{ fontSize: '0.6rem', letterSpacing: '2px', color: '#666', marginBottom: 4 }}>P&L</div>
                <div style={{ fontSize: '1.4rem', fontWeight: 700, color: totalPnl >= 0 ? GREEN : RED, fontFamily: '"JetBrains Mono", monospace' }}>
                  {totalPnl >= 0 ? '+' : ''}{totalPnl.toFixed(0)}€
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* ── Table surveillance ── */}
      <div style={{ background: '#111827', borderRadius: 8, overflow: 'hidden', border: '1px solid #1e2d4a', marginBottom: '1.5rem' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
          <thead>
            <tr style={{ background: '#0d1528' }}>
              {['TICKER', 'NOM', 'DERNIER', 'BID', 'ASK', 'VOLUME', 'VAR. %', 'ESG', 'FIN. ISL.', ''].map(h => (
                <th key={h} style={{ padding: '0.75rem 1rem', textAlign: 'left', fontSize: '0.65rem', letterSpacing: '2px', color: '#666', fontWeight: 600, borderBottom: '1px solid #1e2d4a' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tickers.map((t, i) => {
              const q = quotes[t];
              const s = screened.find(x => x.ticker === t);
              const last = q?.last && q.last > 0 ? q.last : undefined;
              const chg = q?.change_pct && q.last > 0 ? q.change_pct : undefined;
              return (
                <>
                <tr key={t} onClick={() => setExpandedTicker(expandedTicker === t ? null : t)} style={{ borderBottom: '1px solid #1a2035', background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)', cursor: 'pointer' }}>
                  <td style={{ padding: '0.85rem 1rem' }}>
                    <span style={{ fontFamily: '"JetBrains Mono", monospace', fontWeight: 600, color: '#e8e8e8', fontSize: '0.85rem' }}>{t}</span>
                  </td>
                  <td style={{ padding: '0.85rem 1rem', color: '#aaa', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {s?.name && s.name !== t ? s.name : <span style={{ color: '#444' }}>—</span>}
                  </td>
                  <td style={{ padding: '0.85rem 1rem', fontFamily: '"JetBrains Mono", monospace', fontWeight: 600, color: last ? '#e8e8e8' : '#444' }}>{fmt(last)}</td>
                  <td style={{ padding: '0.85rem 1rem', fontFamily: '"JetBrains Mono", monospace', color: '#888' }}>{fmt(q?.bid)}</td>
                  <td style={{ padding: '0.85rem 1rem', fontFamily: '"JetBrains Mono", monospace', color: '#888' }}>{fmt(q?.ask)}</td>
                  <td style={{ padding: '0.85rem 1rem', color: '#888' }}>{q?.volume && q.volume > 0 ? q.volume.toLocaleString('fr-FR') : '—'}</td>
                  <td style={{ padding: '0.85rem 1rem' }}>
                    {chg !== undefined ? (
                      <span style={{ color: chg >= 0 ? GREEN : RED, fontWeight: 700, fontFamily: '"JetBrains Mono", monospace', padding: '0.2rem 0.5rem', background: chg >= 0 ? 'rgba(29,140,65,0.1)' : 'rgba(184,36,36,0.1)', borderRadius: 3 }}>
                        {chg >= 0 ? '+' : ''}{chg.toFixed(2)}%
                      </span>
                    ) : <span style={{ color: '#444' }}>—</span>}
                  </td>
                  <td style={{ padding: '0.85rem 1rem' }}><Badge passed={s?.is_ethical} /></td>
                  <td style={{ padding: '0.85rem 1rem' }}><IslamicBadgeMini passed={s?.is_sharia} /></td>
                  <td style={{ padding: '0.85rem 1rem', display: 'flex', gap: '0.3rem', alignItems: 'center' }}>
                    <button onClick={(e) => { e.stopPropagation(); const next = expandedBuffett === t ? null : t; setExpandedBuffett(next); if (next && !buffettCache[t]) { fetch(`${import.meta.env.VITE_API_URL ?? ""}/api/tickers/${t}/buffett`).then(r => r.json()).then(d => setBuffettCache(prev => ({ ...prev, [t]: d }))); } }} title="Buffett Score" style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 28, height: 28, borderRadius: 4, background: expandedBuffett === t ? '#b8962f' : 'rgba(184,150,47,0.12)', border: '1.5px solid ' + (expandedBuffett === t ? '#b8962f' : '#4a3a10'), color: expandedBuffett === t ? '#000' : '#b8962f', cursor: 'pointer', fontSize: '0.72rem', fontWeight: 800, letterSpacing: 0 }}>B</button>
                    <button onClick={(e) => { e.stopPropagation(); remove(t); }} style={{ background: 'none', border: '1px solid #2a3555', color: '#666', cursor: 'pointer', borderRadius: 3, padding: '0.2rem 0.5rem', fontSize: '0.7rem' }}>✕</button>
                  </td>
                </tr>
                {expandedTicker === t && s && (
                  <IslamicFinancePanelPortfolio s={s} colSpan={10} />
                )}
                {expandedBuffett === t && (
                  <BuffettPanel data={buffettCache[t]} colSpan={10} />
                )}
                </>
              );
            })}
          </tbody>
        </table>
        {!tickers.length && (
          <div style={{ padding: '4rem', textAlign: 'center', color: '#444' }}>
            <div style={{ fontSize: '2rem', marginBottom: '1rem', opacity: 0.3 }}>◎</div>
            <div style={{ fontSize: '0.85rem', letterSpacing: '1px' }}>Aucun titre. Saisissez des tickers ci-dessus.</div>
          </div>
        )}
      </div>

      {/* ── Section positions réelles ── */}
      {tickers.length > 0 && (
        <div style={{ background: '#111827', borderRadius: 8, overflow: 'hidden', border: '1px solid #1e2d4a' }}>
          <div style={{ padding: '0.75rem 1rem', background: '#0d1528', borderBottom: '1px solid #1e2d4a', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.65rem', letterSpacing: '2px', color: GOLD, fontWeight: 600 }}>POSITIONS RÉELLES</span>
            {!token && (
              <span style={{ fontSize: 11, color: '#666', fontFamily: 'monospace' }}>
                Connectez-vous pour sauvegarder en base
              </span>
            )}
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
            <thead>
              <tr style={{ background: '#0d1528' }}>
                {['TICKER', 'QTÉ', 'PRU', 'VALEUR', 'P&L', 'P&L %', ''].map(h => (
                  <th key={h} style={{ padding: '0.75rem 1rem', textAlign: 'left', fontSize: '0.65rem', letterSpacing: '2px', color: '#666', fontWeight: 600, borderBottom: '1px solid #1e2d4a' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tickers.map((t, i) => {
                const q = quotes[t];
                const last = q?.last && q.last > 0 ? q.last : 0;
                const pos = positions.get(t);
                const qty = pos?.qty || 0;
                const pru = pos?.avg_price || 0;
                const value = last * qty;
                const pnl = (last - pru) * qty;
                const pnlPct = pru > 0 ? ((last - pru) / pru * 100) : 0;

                return (
                  <tr key={t} style={{ borderBottom: '1px solid #1a2035', background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)' }}>
                    <td style={{ padding: '0.75rem 1rem', fontFamily: '"JetBrains Mono", monospace', fontWeight: 600, color: '#e8e8e8' }}>{t}</td>
                    <td style={{ padding: '0.5rem 1rem' }}>
                      <input type="number" placeholder="0" value={qty || ''} min={0}
                        onChange={e => updatePosition(t, 'qty', parseFloat(e.target.value) || 0)}
                        onBlur={() => savePosition(t, qty, pru)}
                        style={{ width: 70, background: '#1a2035', border: '1px solid #2a3555', borderRadius: 4, padding: '4px 8px', color: '#e8e8e8', fontSize: 12, fontFamily: 'monospace' }}
                      />
                    </td>
                    <td style={{ padding: '0.5rem 1rem' }}>
                      <input type="number" placeholder="0.00" value={pru || ''} min={0} step={0.01}
                        onChange={e => updatePosition(t, 'avg_price', parseFloat(e.target.value) || 0)}
                        onBlur={() => savePosition(t, qty, pru)}
                        style={{ width: 80, background: '#1a2035', border: '1px solid #2a3555', borderRadius: 4, padding: '4px 8px', color: '#e8e8e8', fontSize: 12, fontFamily: 'monospace' }}
                      />
                    </td>
                    <td style={{ padding: '0.75rem 1rem', fontFamily: '"JetBrains Mono", monospace', color: value > 0 ? '#e8e8e8' : '#444' }}>
                      {value > 0 ? value.toFixed(2) + '€' : '—'}
                    </td>
                    <td style={{ padding: '0.75rem 1rem', fontFamily: '"JetBrains Mono", monospace', fontWeight: 700, color: pnl >= 0 ? GREEN : RED }}>
                      {qty > 0 && pru > 0 ? (pnl >= 0 ? '+' : '') + pnl.toFixed(2) + '€' : '—'}
                    </td>
                    <td style={{ padding: '0.75rem 1rem' }}>
                      {qty > 0 && pru > 0 ? (
                        <span style={{
                          color: pnlPct >= 0 ? GREEN : RED, fontWeight: 700,
                          fontFamily: '"JetBrains Mono", monospace',
                          padding: '0.2rem 0.5rem',
                          background: pnlPct >= 0 ? 'rgba(29,140,65,0.1)' : 'rgba(184,36,36,0.1)',
                          borderRadius: 3, fontSize: 12,
                        }}>{pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%</span>
                      ) : <span style={{ color: '#444' }}>—</span>}
                    </td>
                    <td style={{ padding: '0.75rem 1rem', fontSize: 10, color: '#444', fontFamily: 'monospace' }}>
                      {token && qty > 0 ? '✓ sauvegardé' : ''}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Badge({ passed }: { passed?: boolean }) {
  if (passed === undefined) return <span style={{ color: '#444', fontSize: '0.7rem' }}>…</span>;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      width: 22, height: 22, borderRadius: 4,
      background: passed ? 'rgba(29,140,65,0.15)' : 'rgba(184,36,36,0.15)',
      border: `1px solid ${passed ? '#1d8c41' : '#b82424'}`,
      color: passed ? '#1d8c41' : '#b82424',
      fontSize: '0.75rem', fontWeight: 700,
    }}>{passed ? '✓' : '✗'}</span>
  );
}
