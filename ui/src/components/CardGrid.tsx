import React, { useEffect } from 'react';
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

export const CardGrid = React.forwardRef<HTMLDivElement, CardGridProps>(
  ({ cards, total, loading, selectedCardId, onSelectCard, animateRef }, ref) => {
    // Animate cards when they change
    useEffect(() => {
      if (!loading && cards.length > 0) {
        animateRef.current?.animateToNewPositions();
      }
    }, [cards, loading, animateRef]);

    if (loading && cards.length === 0) {
      return (
        <div ref={ref} className="card-grid">
          <div className="loading-message">Loading…</div>
        </div>
      );
    }

    if (cards.length === 0) {
      return (
        <div ref={ref} className="card-grid">
          <div className="no-results-message">
            No cards match the current filters. Try adjusting your selection.
          </div>
        </div>
      );
    }

    return (
      <div ref={ref} className="card-grid">
        <div className="grid-header">
          <span className="result-count">
            {total} card{total !== 1 ? 's' : ''}
          </span>
        </div>

        <div className="grid-content">
          {cards.map((card) => {
            const isSelected = card.id === selectedCardId;
            const periodTags = card.period.slice(0, 2);
            const formTag = card.form[0];

            return (
              <div
                key={card.id}
                data-card-id={card.id}
                className={`card ${isSelected ? 'selected' : ''}`}
                onClick={() => onSelectCard(card.id)}
              >
                <div className="card-title">{card.title}</div>
                {card.authors.length > 0 && (
                  <div className="card-authors">{card.authors.join(', ')}</div>
                )}
                {card.year && <div className="card-year">{card.year}</div>}
                <div className="card-description">{card.description}</div>
                {(periodTags.length > 0 || formTag) && (
                  <div className="card-tags">
                    {periodTags.map((p) => (
                      <span key={p} className="tag tag-period">
                        {p}
                      </span>
                    ))}
                    {formTag && <span className="tag tag-form">{formTag}</span>}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  }
);

CardGrid.displayName = 'CardGrid';
