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
export declare const FacetPanel: React.FC<FacetPanelProps>;
export {};
//# sourceMappingURL=FacetPanel.d.ts.map