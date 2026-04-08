import React, { useEffect, useState } from 'react';
import { Card } from '../hooks/useCardStore';
import { fetchCard } from '../api';
import './CardDetail.css';

interface CardDetailProps {
  cardId: number | null;
  onClose: () => void;
}

export const CardDetail: React.FC<CardDetailProps> = ({ cardId, onClose }) => {
  const [card, setCard] = useState<Card | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load card');
      } finally {
        setLoading(false);
      }
    };

    loadCard();
  }, [cardId]);

  if (!cardId) return null;

  return (
    <div className="card-detail-panel">
      <button className="detail-close-btn" onClick={onClose}>
        ← Back
      </button>

      {loading && <div className="detail-loading">Loading…</div>}
      {error && <div className="detail-error">{error}</div>}

      {card && (
        <div className="detail-content">
          <h2 className="detail-title">{card.title}</h2>

          {card.authors.length > 0 && (
            <div className="detail-authors">{card.authors.join(', ')}</div>
          )}

          {(card.source || card.year) && (
            <div className="detail-source">
              {[card.source, card.year].filter(Boolean).join(', ')}
            </div>
          )}

          {card.description && (
            <div className="detail-description">{card.description}</div>
          )}

          {(card.period.length > 0 ||
            card.form.length > 0 ||
            card.region.length > 0 ||
            card.topic.length > 0) && (
            <div className="detail-facets">
              {card.period.length > 0 && (
                <div className="facet-row">
                  <span className="facet-label">Period:</span>
                  <div className="facet-values">
                    {card.period.map((p) => (
                      <span key={p} className="facet-tag">
                        {p}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {card.form.length > 0 && (
                <div className="facet-row">
                  <span className="facet-label">Form:</span>
                  <div className="facet-values">
                    {card.form.map((f) => (
                      <span key={f} className="facet-tag">
                        {f}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {card.region.length > 0 && (
                <div className="facet-row">
                  <span className="facet-label">Region:</span>
                  <div className="facet-values">
                    {card.region.map((r) => (
                      <span key={r} className="facet-tag">
                        {r}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {card.topic.length > 0 && (
                <div className="facet-row">
                  <span className="facet-label">Topic:</span>
                  <div className="facet-values">
                    {card.topic.map((t) => (
                      <span key={t} className="facet-tag">
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {card.makers.length > 0 && (
            <div className="detail-makers">
              <strong>Craftsmen:</strong> {card.makers.join(', ')}
            </div>
          )}

          {(card.view_url || card.download_url) && (
            <div className="detail-links">
              {card.view_url && (
                <a
                  href={card.view_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-primary"
                >
                  Read Article ↗
                </a>
              )}
              {card.download_url && (
                <a
                  href={card.download_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-secondary"
                >
                  Download PDF
                </a>
              )}
            </div>
          )}

          {card.contributor_name && (
            <div className="detail-contributor">Contributed by {card.contributor_name}</div>
          )}
        </div>
      )}
    </div>
  );
};
