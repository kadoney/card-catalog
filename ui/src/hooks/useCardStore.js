import { useEffect, useState } from 'react';
import { fetchCards, fetchVocab } from '../api';
export const useCardStore = () => {
    const [cards, setCards] = useState([]);
    const [total, setTotal] = useState(0);
    const [vocab, setVocab] = useState({});
    const [facets, setFacets] = useState({});
    const [filters, setFilters] = useState({
        period: new Set(),
        form: new Set(),
        region: new Set(),
        topic: new Set(),
        source_key: new Set(),
    });
    const [searchQ, setSearchQ] = useState('');
    const [selectedCardId, setSelectedCardId] = useState(null);
    const [loading, setLoading] = useState(false);
    // Load vocab on mount
    useEffect(() => {
        const loadVocab = async () => {
            try {
                const data = await fetchVocab();
                setVocab(data);
            }
            catch (err) {
                console.error('Failed to load vocab:', err);
            }
        };
        loadVocab();
    }, []);
    // Load cards whenever filters or search changes
    useEffect(() => {
        const loadCards = async () => {
            setLoading(true);
            try {
                const data = await fetchCards({
                    period: Array.from(filters.period),
                    form: Array.from(filters.form),
                    region: Array.from(filters.region),
                    topic: Array.from(filters.topic),
                    source_key: Array.from(filters.source_key),
                    q: searchQ,
                });
                setCards(data.cards);
                setTotal(data.total);
                setFacets(data.facets);
                setSelectedCardId(null); // Clear selection on filter change
            }
            catch (err) {
                console.error('Failed to load cards:', err);
            }
            finally {
                setLoading(false);
            }
        };
        loadCards();
    }, [filters, searchQ]);
    const toggleFilter = (dimension, value) => {
        setFilters((prev) => {
            const updated = { ...prev };
            if (!updated[dimension])
                updated[dimension] = new Set();
            if (updated[dimension].has(value)) {
                updated[dimension].delete(value);
            }
            else {
                updated[dimension].add(value);
            }
            return updated;
        });
    };
    const clearFilters = () => {
        setFilters({
            period: new Set(),
            form: new Set(),
            region: new Set(),
            topic: new Set(),
            source_key: new Set(),
        });
        setSearchQ('');
    };
    return {
        cards,
        total,
        vocab,
        facets,
        filters,
        searchQ,
        selectedCardId,
        loading,
        setSearchQ,
        selectCard: setSelectedCardId,
        toggleFilter,
        clearFilters,
        setFilters,
    };
};
//# sourceMappingURL=useCardStore.js.map