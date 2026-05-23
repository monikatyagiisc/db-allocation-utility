import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import KpiDetailDialog from '../components/KpiDetailDialog';
import SendEmailDialog, { type EmailMode } from '../components/SendEmailDialog';
import TypePieChart from '../components/TypePieChart';
import { getKPIs, type KpiCategory, type KPIs } from '../api';
import { useAuth } from '../AuthContext';

type KpiCardConfig = {
  category: KpiCategory;
  value: number | string | undefined;
  label: string;
  hint?: string;
  className?: string;
};

export default function Home() {
  const { user } = useAuth();
  const [kpis, setKpis] = useState<KPIs | null>(null);
  const [error, setError] = useState('');
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [kpiDialog, setKpiDialog] = useState<KpiCategory | null>(null);
  const [emailMode, setEmailMode] = useState<EmailMode | null>(null);
  const [emailMessage, setEmailMessage] = useState('');

  useEffect(() => {
    if (!user) return;
    getKPIs()
      .then(setKpis)
      .catch((e) => setError(e.message));
  }, [user]);

  const monthName = new Date().toLocaleString('default', { month: 'long', year: 'numeric' });
  const nextMonthDate = new Date();
  nextMonthDate.setMonth(nextMonthDate.getMonth() + 1);
  const nextMonthName = nextMonthDate.toLocaleString('default', {
    month: 'long',
    year: 'numeric',
  });

  const display = useMemo(() => {
    if (!kpis) return null;
    if (!selectedType) return kpis;
    const t = kpis.by_type.find((x) => x.database_type === selectedType);
    if (!t) return kpis;
    return {
      ...kpis,
      total_databases: t.count,
      expiring_this_month: t.expiring_this_month,
      expiring_next_month: t.expiring_next_month,
      prod_mirror_count: t.prod_mirror_count,
      can_be_released_count: t.can_be_released_count,
      blocked_count: t.blocked_count,
    };
  }, [kpis, selectedType]);

  const kpiCards: KpiCardConfig[] = display
    ? [
        {
          category: 'expiring_this_month',
          value: display.expiring_this_month,
          label: `Expiring in ${monthName}`,
          hint: 'Click to view list',
          className: 'kpi-warning',
        },
        {
          category: 'expiring_next_month',
          value: display.expiring_next_month,
          label: `Expiring in ${nextMonthName}`,
          hint: 'Click to view list',
          className: 'kpi-warning',
        },
        {
          category: 'prod_mirror',
          value: display.prod_mirror_count,
          label: 'Prod mirror',
          hint: 'Click to view list',
          className: 'kpi-accent',
        },
        {
          category: 'total',
          value: display.total_databases,
          label: 'Total databases',
          hint: 'Click to view list',
        },
        {
          category: 'can_be_released',
          value: display.can_be_released_count,
          label: 'Can be released',
          hint: 'Click to view list',
        },
        {
          category: 'blocked',
          value: display.blocked_count,
          label: 'Blocked status',
          hint: 'Click to view list',
        },
      ]
    : [];

  return (
    <div className="page">
      <KpiDetailDialog
        category={kpiDialog}
        databaseType={selectedType}
        onClose={() => setKpiDialog(null)}
        onEmailReport={(category, title) => {
          setKpiDialog(null);
          setEmailMode({
            type: 'digest',
            category,
            databaseType: selectedType ?? undefined,
            title,
          });
        }}
      />
      <SendEmailDialog
        open={emailMode !== null}
        mode={emailMode}
        onClose={() => setEmailMode(null)}
        onSent={setEmailMessage}
      />
      <section className="hero">
        <h1>Database allocation overview</h1>
        <p>
          Upload multi-sheet Excel files — each sheet name becomes the database <strong>Type</strong>.
          Click any KPI card to see the matching database list.
        </p>
        {!user && (
          <p className="hint">
            <Link to="/login">Log in</Link> to view KPIs and manage database records.
          </p>
        )}
      </section>

      {user && (
        <>
          {emailMessage && <div className="alert alert-success">{emailMessage}</div>}
          {error && <div className="alert alert-error">{error}</div>}
          {selectedType && (
            <p className="kpi-filter-note">
              Showing KPIs for type <strong>{selectedType}</strong> — click the chart or Clear filter to
              see all.
            </p>
          )}
          <div className={`kpi-grid${selectedType ? ' kpi-grid-filtered' : ''}`}>
            {kpiCards.map((card) => (
              <button
                key={card.category}
                type="button"
                className={`kpi-card kpi-card-clickable ${card.className ?? ''}`}
                onClick={() => setKpiDialog(card.category)}
                title="Click to view database list"
              >
                <span className="kpi-value">{card.value ?? '—'}</span>
                <span className="kpi-label">{card.label}</span>
                {card.hint && <span className="kpi-hint">{card.hint}</span>}
              </button>
            ))}
            <div className="kpi-card kpi-card-static">
              <span className="kpi-value">{kpis?.by_type?.length ?? '—'}</span>
              <span className="kpi-label">Database types</span>
              <span className="kpi-hint">Use pie chart to explore</span>
            </div>
          </div>

          {kpis?.by_type && (
            <TypePieChart
              data={kpis.by_type}
              selectedType={selectedType}
              onSelectType={setSelectedType}
            />
          )}

          <div className="actions-row">
            <Link
              to={
                selectedType
                  ? `/databases?type=${encodeURIComponent(selectedType)}`
                  : '/databases'
              }
              className="btn btn-primary"
            >
              Manage databases
            </Link>
          </div>
        </>
      )}
    </div>
  );
}
