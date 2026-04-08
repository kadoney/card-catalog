import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from 'react';
import { fetchCard } from '../api';
import './CardDetail.css';
export const CardDetail = ({ cardId, onClose }) => {
    const [card, setCard] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    useEffect(() => {
        if (!cardId) {
            setCard(null);
            return;
        }
        const loadCard = async () => {
            setLoading(true);
            setError(null);
            try {
                const data = await fetchCard(cardId);
                setCard(data.card);
            }
            catch (err) {
                setError(err instanceof Error ? err.message : 'Failed to load card');
            }
            finally {
                setLoading(false);
            }
        };
        loadCard();
    }, [cardId]);
    if (!cardId)
        return null;
    return (_jsxs("div", { className: "card-detail-panel", children: [_jsx("button", { className: "detail-close-btn", onClick: onClose, children: "\u2190 Back" }), loading && _jsx("div", { className: "detail-loading", children: "Loading\u2026" }), error && _jsx("div", { className: "detail-error", children: error }), card && (_jsxs("div", { className: "detail-content", children: [_jsx("h2", { className: "detail-title", children: card.title }), card.authors.length > 0 && (_jsx("div", { className: "detail-authors", children: card.authors.join(', ') })), (card.source || card.year) && (_jsx("div", { className: "detail-source", children: [card.source, card.year].filter(Boolean).join(', ') })), card.description && (_jsx("div", { className: "detail-description", children: card.description })), (card.period.length > 0 ||
                        card.form.length > 0 ||
                        card.region.length > 0 ||
                        card.topic.length > 0) && (_jsxs("div", { className: "detail-facets", children: [card.period.length > 0 && (_jsxs("div", { className: "facet-row", children: [_jsx("span", { className: "facet-label", children: "Period:" }), _jsx("div", { className: "facet-values", children: card.period.map((p) => (_jsx("span", { className: "facet-tag", children: p }, p))) })] })), card.form.length > 0 && (_jsxs("div", { className: "facet-row", children: [_jsx("span", { className: "facet-label", children: "Form:" }), _jsx("div", { className: "facet-values", children: card.form.map((f) => (_jsx("span", { className: "facet-tag", children: f }, f))) })] })), card.region.length > 0 && (_jsxs("div", { className: "facet-row", children: [_jsx("span", { className: "facet-label", children: "Region:" }), _jsx("div", { className: "facet-values", children: card.region.map((r) => (_jsx("span", { className: "facet-tag", children: r }, r))) })] })), card.topic.length > 0 && (_jsxs("div", { className: "facet-row", children: [_jsx("span", { className: "facet-label", children: "Topic:" }), _jsx("div", { className: "facet-values", children: card.topic.map((t) => (_jsx("span", { className: "facet-tag", children: t }, t))) })] }))] })), card.makers.length > 0 && (_jsxs("div", { className: "detail-makers", children: [_jsx("strong", { children: "Craftsmen:" }), " ", card.makers.join(', ')] })), (card.view_url || card.download_url) && (_jsxs("div", { className: "detail-links", children: [card.view_url && (_jsx("a", { href: card.view_url, target: "_blank", rel: "noopener noreferrer", className: "btn btn-primary", children: "Read Article \u2197" })), card.download_url && (_jsx("a", { href: card.download_url, target: "_blank", rel: "noopener noreferrer", className: "btn btn-secondary", children: "Download PDF" }))] })), card.contributor_name && (_jsxs("div", { className: "detail-contributor", children: ["Contributed by ", card.contributor_name] }))] }))] }));
};
//# sourceMappingURL=CardDetail.js.map