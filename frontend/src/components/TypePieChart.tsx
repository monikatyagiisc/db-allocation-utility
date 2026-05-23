import { useMemo, useState } from 'react';
import type { TypeBreakdown } from '../api';

/** Soft translucent palette — pairs with glass UI in index.css */
const COLORS = [
  'rgba(125, 211, 252, 0.88)',
  'rgba(110, 231, 183, 0.88)',
  'rgba(252, 211, 77, 0.88)',
  'rgba(252, 165, 165, 0.88)',
  'rgba(196, 181, 253, 0.88)',
  'rgba(249, 168, 212, 0.88)',
  'rgba(103, 232, 249, 0.88)',
  'rgba(190, 242, 100, 0.88)',
];

const CX = 110;
const CY = 110;
const R_OUTER = 100;
const R_INNER = 58;

type Slice = TypeBreakdown & {
  pct: number;
  color: string;
  start: number;
  end: number;
  mid: number;
};

type Props = {
  data: TypeBreakdown[];
  selectedType: string | null;
  onSelectType: (type: string | null) => void;
};

function polar(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function donutPath(startAngle: number, endAngle: number) {
  const span = endAngle - startAngle;
  if (span >= 359.99) {
    return [
      `M ${CX} ${CY - R_OUTER}`,
      `A ${R_OUTER} ${R_OUTER} 0 1 1 ${CX - 0.01} ${CY - R_OUTER}`,
      `L ${CX - 0.01} ${CY - R_INNER}`,
      `A ${R_INNER} ${R_INNER} 0 1 0 ${CX} ${CY - R_INNER}`,
      'Z',
    ].join(' ');
  }
  const outerStart = polar(CX, CY, R_OUTER, startAngle);
  const outerEnd = polar(CX, CY, R_OUTER, endAngle);
  const innerEnd = polar(CX, CY, R_INNER, endAngle);
  const innerStart = polar(CX, CY, R_INNER, startAngle);
  const largeArc = span > 180 ? 1 : 0;
  return [
    `M ${outerStart.x} ${outerStart.y}`,
    `A ${R_OUTER} ${R_OUTER} 0 ${largeArc} 1 ${outerEnd.x} ${outerEnd.y}`,
    `L ${innerEnd.x} ${innerEnd.y}`,
    `A ${R_INNER} ${R_INNER} 0 ${largeArc} 0 ${innerStart.x} ${innerStart.y}`,
    'Z',
  ].join(' ');
}

function TooltipContent({ slice }: { slice: Slice }) {
  return (
    <>
      <strong>{slice.database_type}</strong>
      <ul>
        <li>Total databases: {slice.count}</li>
        <li>Share: {(slice.pct * 100).toFixed(1)}%</li>
        <li>Prod mirror: {slice.prod_mirror_count}</li>
        <li>Expiring this month: {slice.expiring_this_month}</li>
        <li>Expiring next month: {slice.expiring_next_month}</li>
        <li>Can be released: {slice.can_be_released_count}</li>
        <li>Blocked: {slice.blocked_count}</li>
      </ul>
    </>
  );
}

export default function TypePieChart({ data, selectedType, onSelectType }: Props) {
  const [hovered, setHovered] = useState<string | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  const total = useMemo(() => data.reduce((s, d) => s + d.count, 0), [data]);

  const slices: Slice[] = useMemo(() => {
    if (total === 0) return [];
    let angle = 0;
    return data.map((item, i) => {
      const pct = item.count / total;
      const slice: Slice = {
        ...item,
        pct,
        color: COLORS[i % COLORS.length],
        start: angle,
        end: angle + pct * 360,
        mid: angle + (pct * 360) / 2,
      };
      angle += pct * 360;
      return slice;
    });
  }, [data, total]);

  const focusType = hovered ?? selectedType;
  const active = slices.find((s) => s.database_type === focusType);

  const handleSliceClick = (type: string) => {
    onSelectType(selectedType === type ? null : type);
  };

  if (!data.length || total === 0) {
    return <p className="chart-empty">No database type data yet. Import a multi-sheet Excel file.</p>;
  }

  return (
    <div className="pie-chart-card">
      <h2>Databases by type</h2>
      <p className="pie-chart-subtitle">
        Hover a segment for details. Click to filter KPIs by type — click again to clear.
      </p>
      {selectedType && (
        <div className="pie-filter-banner">
          Filtering KPIs: <strong>{selectedType}</strong>
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => onSelectType(null)}>
            Clear filter
          </button>
        </div>
      )}
      <div className="pie-chart-layout">
        <div className="pie-chart-svg-wrap">
          <svg
            viewBox="0 0 220 220"
            className="pie-chart-svg"
            role="img"
            aria-label="Interactive pie chart of databases by type"
          >
            {slices.map((s) => {
              const isFocus = focusType === s.database_type;
              const isSelected = selectedType === s.database_type;
              const dimmed = focusType != null && !isFocus;
              const pop = isFocus ? 4 : 0;
              const popRad = ((s.mid - 90) * Math.PI) / 180;
              const dx = pop * Math.cos(popRad);
              const dy = pop * Math.sin(popRad);
              return (
                <path
                  key={s.database_type}
                  d={donutPath(s.start, s.end)}
                  fill={s.color}
                  stroke={isSelected ? 'rgba(255,255,255,0.9)' : isFocus ? 'rgba(255,255,255,0.5)' : 'rgba(255,255,255,0.08)'}
                  strokeWidth={isSelected ? 2.5 : isFocus ? 1.5 : 0.5}
                  opacity={dimmed ? 0.4 : 0.95}
                  transform={`translate(${dx} ${dy})`}
                  style={{ cursor: 'pointer', transition: 'opacity 0.15s, transform 0.15s' }}
                  onMouseEnter={(e) => {
                    setHovered(s.database_type);
                    setTooltipPos({ x: e.clientX, y: e.clientY });
                  }}
                  onMouseMove={(e) => setTooltipPos({ x: e.clientX, y: e.clientY })}
                  onMouseLeave={() => setHovered(null)}
                  onClick={() => handleSliceClick(s.database_type)}
                />
              );
            })}
            <circle cx={CX} cy={CY} r={R_INNER - 1} fill="var(--chart-hole)" pointerEvents="none" />
            <text
              x={CX}
              y={CY - 6}
              textAnchor="middle"
              className="pie-chart-total-svg"
              pointerEvents="none"
            >
              {selectedType
                ? slices.find((s) => s.database_type === selectedType)?.count ?? 0
                : total}
            </text>
            <text
              x={CX}
              y={CY + 14}
              textAnchor="middle"
              className="pie-chart-total-label-svg"
              pointerEvents="none"
            >
              {selectedType ? selectedType.slice(0, 12) : 'total'}
            </text>
          </svg>
          {hovered && active && (
            <div
              className="pie-tooltip-floating"
              style={{ left: tooltipPos.x + 14, top: tooltipPos.y + 14 }}
              role="tooltip"
            >
              <TooltipContent slice={active} />
            </div>
          )}
        </div>
        <ul className="pie-legend">
          {slices.map((s) => {
            const isFocus = focusType === s.database_type;
            const isSelected = selectedType === s.database_type;
            return (
              <li
                key={s.database_type}
                className={`pie-legend-item${isFocus ? ' active' : ''}${isSelected ? ' selected' : ''}`}
                onMouseEnter={() => setHovered(s.database_type)}
                onMouseLeave={() => setHovered(null)}
                onClick={() => handleSliceClick(s.database_type)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    handleSliceClick(s.database_type);
                  }
                }}
                tabIndex={0}
                role="button"
                aria-pressed={isSelected}
              >
                <span className="pie-swatch" style={{ background: s.color }} />
                <span className="pie-legend-label">
                  {s.database_type}{' '}
                  <strong>
                    {s.count} ({(s.pct * 100).toFixed(1)}%)
                  </strong>
                </span>
              </li>
            );
          })}
        </ul>
      </div>
      {selectedType && active && !hovered && (
        <div className="pie-tooltip" role="status">
          <TooltipContent slice={active} />
        </div>
      )}
    </div>
  );
}
