import React from 'react';
import { Card } from '../hooks/useCardStore';
import './CardGrid.css';
interface CardGridProps {
    cards: Card[];
    total: number;
    loading: boolean;
    selectedCardId: number | null;
    onSelectCard: (id: number | null) => void;
    animateRef: React.MutableRefObject<{
        capturePositions: () => void;
        animateToNewPositions: () => Promise<void>;
    }>;
}
export declare const CardGrid: React.ForwardRefExoticComponent<CardGridProps & React.RefAttributes<HTMLDivElement>>;
export {};
//# sourceMappingURL=CardGrid.d.ts.map