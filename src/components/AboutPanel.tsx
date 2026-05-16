// Landing / About page: project pitch, tech stack, methodology transparency.
// © 2024 Sauhabah

export default function AboutPanel() {
  return (
    <div style={{ padding: '1rem 1rem 3rem', maxWidth: 900, margin: '0 auto', lineHeight: 1.6 }}>
      <h1 style={{ color: '#142340', marginBottom: '0.25rem' }}>
        Ethical Finance Platform
      </h1>
      <p style={{ color: '#b8962f', fontWeight: 600, marginTop: 0, marginBottom: '1.5rem' }}>
        Backtest, optimisation et reporting institutionnel pour portefeuilles éthiques
      </p>

      <section>
        <h2 style={h2}>Ce que fait cette plateforme</h2>
        <p>
          Une suite complète d'outils quantitatifs permettant de construire un portefeuille
          d'investissement <strong>éthique</strong>, de <strong>backtester</strong> plus de 10 stratégies
          quantitatives sur 20 ans d'historique, de produire des <strong>rapports PDF
          de niveau institutionnel</strong> (style Goldman Sachs), et de générer
          quotidiennement des <strong>signaux d'achat/vente</strong> pour rééquilibrer
          efficacement le portefeuille.
        </p>
        <p>
          Le screening éthique exclut automatiquement les secteurs sensibles (armement,
          tabac, jeux, énergies fossiles) et applique des filtres financiers (ratios
          de dette/capitalisation et revenus issus d'intérêts) pour garantir la
          conformité à des principes d'investissement responsable.
        </p>
      </section>

      <section>
        <h2 style={h2}>Stack technique &amp; outils FinTech / AI</h2>
        <ul>
          <li><strong>Backend</strong> : Python 3.11, FastAPI, asyncio, programmation fonctionnelle (générateurs paresseux, lambdas, modules)</li>
          <li><strong>Données de marché</strong> : yfinance → Stooq → fallback GBM synthétique</li>
          <li><strong>Quant</strong> : NumPy, Pandas, SciPy ; 25+ métriques (Sharpe, Sortino, Calmar, VaR, CVaR, Omega, Treynor, Information Ratio…)</li>
          <li><strong>Machine Learning</strong> : scikit-learn (Random Forest, Gradient Boosting) pour signaux ML</li>
          <li><strong>Monte Carlo</strong> : simulations GBM vectorisées (10 000 chemins) avec calibration bayésienne (scikit-optimize)</li>
          <li><strong>Tests statistiques</strong> : Jobson-Korkie, bootstrap, t-test sur l'alpha de Jensen, White's Reality Check</li>
          <li><strong>Backtest engine</strong> : event-driven, date par date (path-dependent), positions entières, FX EUR/USD, frais réels par courtier, taxes françaises (PFU, TTF)</li>
          <li><strong>Reporting</strong> : ReportLab pour génération de PDF multi-pages</li>
          <li><strong>Cache</strong> : in-memory LRU + Vercel KV (Redis) pour persistance cross-invocation</li>
          <li><strong>Frontend</strong> : React 18, Vite, TypeScript, Recharts ; SSE pour quotes temps réel</li>
          <li><strong>Déploiement</strong> : Vercel (serverless functions + static SPA)</li>
        </ul>
      </section>

      <section>
        <h2 style={h2}>Méthodologie</h2>
        <ol>
          <li><strong>Path-dependent backtesting</strong> : la simulation rejoue date par date l'évolution du marché, calculant la NAV, les frais, le slippage et les taxes à chaque transaction.</li>
          <li><strong>Coûts réels intégrés</strong> : chaque courtier (Degiro, Fortuneo, Bourse Direct, Interactive Brokers) a sa propre grille tarifaire — fixe + pourcentage + minimum/maximum.</li>
          <li><strong>Significativité statistique</strong> : chaque résultat est testé par Jobson-Korkie et bootstrap pour distinguer la chance de la compétence (p-value &lt; 0.05).</li>
          <li><strong>Stress tests</strong> : performance reconstruite sur GFC 2008, COVID 2020, Bear Market 2022, crise EU 2011 et dot-com 2000.</li>
          <li><strong>Calibration ML / DL</strong> : Bayesian optimisation des hyperparamètres de stratégie via scikit-optimize.</li>
        </ol>
      </section>

      <section>
        <h2 style={h2}>Disclaimer officiel</h2>
        <p style={{ fontSize: '0.85rem', color: '#555', background: '#f8f8fb', padding: '1rem', borderRadius: 4 }}>
          Ce document est fourni à titre informatif uniquement et ne constitue pas un conseil
          en investissement. Les performances passées ne préjugent pas des performances
          futures. Tout investissement comporte un risque de perte en capital.
          Sauhabah Ethical Finance Platform n'est pas agréée par l'AMF.
          L'utilisateur reste seul responsable de ses décisions d'investissement.
        </p>
      </section>

      <p style={{ fontSize: '0.75rem', color: '#888', marginTop: '2rem', textAlign: 'center' }}>
        © 2024 Sauhabah — Ethical Finance Platform. Tous droits réservés.
      </p>
    </div>
  );
}

const h2: React.CSSProperties = {
  color: '#142340', borderBottom: '2px solid #b8962f',
  paddingBottom: '0.25rem', marginTop: '1.5rem',
};
