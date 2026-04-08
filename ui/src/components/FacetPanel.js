import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import './FacetPanel.css';
const DIMENSION_LABELS = {
    period: 'Period',
    form: 'Form',
    region: 'Region',
    topic: 'Topic',
    source_key: 'Source',
};
const DIMENSION_ORDER = ['source_key', 'period', 'form', 'region', 'topic'];
export const FacetPanel = ({ vocab, facets, filters, onToggleFilter, onClearFilters, }) => {
    const hasActiveFilters = Object.values(filters).some((s) => s.size > 0);
    return (_jsxs("aside", { className: "facet-panel", children: [hasActiveFilters && (_jsx("button", { className: "clear-all-btn", onClick: onClearFilters, children: "Clear all filters" })), DIMENSION_ORDER.map((dim) => {
                const terms = vocab[dim] ?? [];
                const counts = facets[dim] ?? [];
                const countMap = new Map(counts.map((c) => [c.value, c.count]));
                if (!terms.length)
                    return null;
                return (_jsxs("div", { className: "facet-section", children: [_jsx("h3", { className: "facet-title", children: DIMENSION_LABELS[dim] }), _jsx("div", { className: "facet-values", children: terms.map((term) => {
                                const count = countMap.get(term.value) ?? 0;
                                const isActive = filters[dim]?.has(term.value) ?? false;
                                const isDimmed = count === 0;
                                return (_jsxs("label", { className: `facet-item ${isActive ? 'active' : ''} ${isDimmed ? 'dimmed' : ''}`, title: term.notes || '', children: [_jsx("input", { type: "checkbox", checked: isActive, onChange: () => onToggleFilter(dim, term.value), disabled: isDimmed && !isActive }), _jsxs("span", { className: "label-text", children: [term.label, _jsxs("span", { className: "count", children: [" (", count, ")"] })] })] }, term.value));
                            }) })] }, dim));
            })] }));
};
//# sourceMappingURL=FacetPanel.js.map