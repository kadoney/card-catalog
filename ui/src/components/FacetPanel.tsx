import React from 'react';
import { VocabTerm, Filters, FacetCounts } from '../hooks/useCardStore';
import './FacetPanel.css';

interface FacetPanelProps {
  vocab: Record<string, VocabTerm[]>;
  facets: FacetCounts;
  filters: Filters;
  onToggleFilter: (dimension: string, value: string) => void;
  onClearFilters: () => void;
}

const DIMENSION_LABELS: Record<string, string> = {
  period: 'Period',
  form: 'Form',
  region: 'Region',
  topic: 'Topic',
  source_key: 'Source',
};

const DIMENSION_ORDER = ['source_key', 'period', 'form', 'region', 'topic'];

export const FacetPanel: React.FC<FacetPanelProps> = ({
  vocab,
  facets,
  filters,
  onToggleFilter,
  onClearFilters,
}) => {
  const hasActiveFilters = Object.values(filters).some((s) => s.size > 0);

  return (
    <aside className="facet-panel">
      {hasActiveFilters && (
        <button className="clear-all-btn" onClick={onClearFilters}>
          Clear all filters
        </button>
      )}

      {DIMENSION_ORDER.map((dim) => {
        const terms = vocab[dim] ?? [];
        const counts = facets[dim] ?? [];
        const countMap = new Map(counts.map((c) => [c.value, c.count]));

        if (!terms.length) return null;

        return (
          <div key={dim} className="facet-section">
            <h3 className="facet-title">{DIMENSION_LABELS[dim]}</h3>
            <div className="facet-values">
              {terms.map((term) => {
                const count = countMap.get(term.value) ?? 0;
                const isActive = filters[dim]?.has(term.value) ?? false;
                const isDimmed = count === 0;

                return (
                  <label
                    key={term.value}
                    className={`facet-item ${isActive ? 'active' : ''} ${isDimmed ? 'dimmed' : ''}`}
                    title={term.notes || ''}
                  >
                    <input
                      type="checkbox"
                      checked={isActive}
                      onChange={() => onToggleFilter(dim, term.value)}
                      disabled={isDimmed && !isActive}
                    />
                    <span className="label-text">
                      {term.label}
                      <span className="count"> ({count})</span>
                    </span>
                  </label>
                );
              })}
            </div>
          </div>
        );
      })}
    </aside>
  );
};
