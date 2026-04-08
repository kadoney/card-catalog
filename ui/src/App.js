import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useRef } from 'react';
import { FacetPanel } from './components/FacetPanel';
import { CardGrid } from './components/CardGrid';
import { CardDetail } from './components/CardDetail';
import { useCardStore } from './hooks/useCardStore';
import { useFLIPAnimation } from './hooks/useFLIPAnimation';
import './App.css';
export const App = () => {
    const { cards, total, facets, vocab, filters, searchQ, selectedCardId, loading, setFilters, setSearchQ, selectCard, clearFilters, toggleFilter, } = useCardStore();
    const gridRef = useRef(null);
    const animateRef = useFLIPAnimation(gridRef);
    const handleFilterChange = async (dim, value) => {
        // Snapshot positions before filter change
        animateRef.current?.capturePositions();
        toggleFilter(dim, value);
    };
    const handleSearchChange = (q) => {
        animateRef.current?.capturePositions();
        setSearchQ(q);
    };
    const handleClearFilters = () => {
        animateRef.current?.capturePositions();
        clearFilters();
    };
    return (_jsxs("div", { className: "app-container", children: [_jsx("header", { className: "app-header", children: _jsxs("div", { className: "header-content", children: [_jsxs("div", { children: [_jsx("h1", { className: "header-title", children: "SAPFM Card Catalog" }), _jsx("p", { className: "header-subtitle", children: "Reference Library \u2014 American Period Furniture" })] }), _jsx("div", { className: "header-search", children: _jsx("input", { type: "search", placeholder: "Search titles, descriptions, makers\u2026", value: searchQ, onChange: (e) => handleSearchChange(e.target.value), className: "search-input" }) })] }) }), _jsxs("div", { className: "layout-container", children: [_jsx(FacetPanel, { vocab: vocab, facets: facets, filters: filters, onToggleFilter: handleFilterChange, onClearFilters: handleClearFilters }), _jsx("div", { className: "main-panel", children: _jsx(CardGrid, { ref: gridRef, cards: cards, total: total, loading: loading, selectedCardId: selectedCardId, onSelectCard: selectCard, animateRef: animateRef }) }), _jsx(CardDetail, { cardId: selectedCardId, onClose: () => selectCard(null) })] })] }));
};
//# sourceMappingURL=App.js.map