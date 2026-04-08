export declare function fetchVocab(): Promise<any>;
export interface FetchCardsOptions {
    period?: string[];
    form?: string[];
    region?: string[];
    topic?: string[];
    source_key?: string[];
    q?: string;
    limit?: number;
    offset?: number;
}
export declare function fetchCards(options: FetchCardsOptions): Promise<any>;
export declare function fetchCard(id: number): Promise<any>;
//# sourceMappingURL=api.d.ts.map