import React, { useEffect, useRef, useState } from 'react';
import { FacetPanel } from './components/FacetPanel';
import { CardGrid } from './components/CardGrid';
import { CardDetail } from './components/CardDetail';
import { useCardStore } from './hooks/useCardStore';
import { useFLIPAnimation } from './hooks/useFLIPAnimation';
import './App.css';

export const App: React.FC = () => {
  const {
    cards,
    total,
    facets,
    vocab,
    filters,
    searchQ,
    selectedCardId,
    loading,
    setFilters,
    setSearchQ,
    selectCard,
    clearFilters,
    toggleFilter,
  } = useCardStore();

  const gridRef = useRef<HTMLDivElement | null>(null);
  const animateRef = useFLIPAnimation(gridRef as React.RefObject<HTMLDivElement>);

  const handleFilterChange = async (dim: string, value: string) => {
    // Snapshot positions before filter change
    animateRef.current?.capturePositions();
    toggleFilter(dim, value);
  };

  const handleSearchChange = (q: string) => {
    animateRef.current?.capturePositions();
    setSearchQ(q);
  };

  const handleClearFilters = () => {
    animateRef.current?.capturePositions();
    clearFilters();
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="header-content">
          <div>
            <h1 className="header-title">SAPFM Card Catalog</h1>
            <p className="header-subtitle">Reference Library — American Period Furniture</p>
          </div>
          <div className="header-search">
            <input
              type="search"
              placeholder="Search titles, descriptions, makers…"
              value={searchQ}
              onChange={(e) => handleSearchChange(e.target.value)}
              className="search-input"
            />
          </div>
        </div>
      </header>

      <div className="layout-container">
        <FacetPanel
          vocab={vocab}
          facets={facets}
          filters={filters}
          onToggleFilter={handleFilterChange}
          onClearFilters={handleClearFilters}
        />

        <div className="main-panel">
          <CardGrid
            ref={gridRef}
            cards={cards}
            total={total}
            loading={loading}
            selectedCardId={selectedCardId}
            onSelectCard={selectCard}
            animateRef={animateRef}
          />
        </div>

        <CardDetail
          cardId={selectedCardId}
          onClose={() => selectCard(null)}
        />
      </div>
    </div>
  );
};
