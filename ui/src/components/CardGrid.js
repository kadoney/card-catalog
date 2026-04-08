import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import React, { useEffect } from 'react';
import './CardGrid.css';
export const CardGrid = React.forwardRef(({ cards, total, loading, selectedCardId, onSelectCard, animateRef }, ref) => {
    // Animate cards when they change
    useEffect(() => {
        if (!loading && cards.length > 0) {
            animateRef.current?.animateToNewPositions();
        }
    }, [cards, loading, animateRef]);
    if (loading && cards.length === 0) {
        return (_jsx("div", { ref: ref, className: "card-grid", children: _jsx("div", { className: "loading-message", children: "Loading\u2026" }) }));
    }
    if (cards.length === 0) {
        return (_jsx("div", { ref: ref, className: "card-grid", children: _jsx("div", { className: "no-results-message", children: "No cards match the current filters. Try adjusting your selection." }) }));
    }
    return (_jsxs("div", { ref: ref, className: "card-grid", children: [_jsx("div", { className: "grid-header", children: _jsxs("span", { className: "result-count", children: [total, " card", total !== 1 ? 's' : ''] }) }), _jsx("div", { className: "grid-content", children: cards.map((card) => {
                    const isSelected = card.id === selectedCardId;
                    const periodTags = card.period.slice(0, 2);
                    const formTag = card.form[0];
                    return (_jsxs("div", { "data-card-id": card.id, className: `card ${isSelected ? 'selected' : ''}`, onClick: () => onSelectCard(card.id), children: [_jsx("div", { className: "card-title", children: card.title }), card.authors.length > 0 && (_jsx("div", { className: "card-authors", children: card.authors.join(', ') })), card.year && _jsx("div", { className: "card-year", children: card.year }), _jsx("div", { className: "card-description", children: card.description }), (periodTags.length > 0 || formTag) && (_jsxs("div", { className: "card-tags", children: [periodTags.map((p) => (_jsx("span", { className: "tag tag-period", children: p }, p))), formTag && _jsx("span", { className: "tag tag-form", children: formTag })] }))] }, card.id));
                }) })] }));
});
CardGrid.displayName = 'CardGrid';
//# sourceMappingURL=CardGrid.js.map