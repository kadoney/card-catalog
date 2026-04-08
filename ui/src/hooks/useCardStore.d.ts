export interface Card {
    id: number;
    title: string;
    authors: string[];
    year: number | null;
    source: string | null;
    source_key: string | null;
    description: string;
    period: string[];
    form: string[];
    region: string[];
    topic: string[];
    makers: string[];
    is_free: boolean;
    view_url: string | null;
    download_url: string | null;
    contributor_name: string | null;
}
export interface VocabTerm {
    value: string;
    label: string;
    notes: string | null;
}
export interface Filters {
    [dimension: string]: Set<string>;
}
export interface FacetCounts {
    [dimension: string]: Array<{
        value: string;
        count: number;
    }>;
}
export declare const useCardStore: () => {
    cards: Card[];
    total: number;
    vocab: Record<string, VocabTerm[]>;
    facets: FacetCounts;
    filters: Filters;
    searchQ: string;
    selectedCardId: number | null;
    loading: boolean;
    setSearchQ: import("react").Dispatch<import("react").SetStateAction<string>>;
    selectCard: import("react").Dispatch<import("react").SetStateAction<number | null>>;
    toggleFilter: (dimension: string, value: string) => void;
    clearFilters: () => void;
    setFilters: import("react").Dispatch<import("react").SetStateAction<Filters>>;
};
//# sourceMappingURL=useCardStore.d.ts.map