import { useCallback, useRef } from 'react';
export const useFLIPAnimation = (gridRef) => {
    const positionsRef = useRef({});
    const animatingRef = useRef(false);
    const capturePositions = useCallback(() => {
        if (!gridRef.current)
            return;
        const positions = {};
        const cards = gridRef.current.querySelectorAll('[data-card-id]');
        cards.forEach((el) => {
            const cardId = parseInt(el.dataset.cardId || '0');
            const rect = el.getBoundingClientRect();
            positions[cardId] = {
                x: rect.left,
                y: rect.top,
                width: rect.width,
                height: rect.height,
            };
        });
        positionsRef.current = positions;
    }, [gridRef]);
    const animateToNewPositions = useCallback(async () => {
        if (!gridRef.current || animatingRef.current)
            return;
        animatingRef.current = true;
        const oldPositions = positionsRef.current;
        const cards = gridRef.current.querySelectorAll('[data-card-id]');
        // Fade out cards that are leaving
        const oldIds = new Set(Object.keys(oldPositions).map(Number));
        const newIds = new Set();
        cards.forEach((el) => {
            const cardId = parseInt(el.dataset.cardId || '0');
            newIds.add(cardId);
        });
        oldIds.forEach((id) => {
            if (!newIds.has(id)) {
                const el = gridRef.current?.querySelector(`[data-card-id="${id}"]`);
                if (el) {
                    el.classList.add('card-leaving');
                }
            }
        });
        // Wait for fade out
        await new Promise((resolve) => setTimeout(resolve, 200));
        // Now compute new positions and animate
        cards.forEach((el) => {
            const cardEl = el;
            const cardId = parseInt(cardEl.dataset.cardId || '0');
            const newRect = cardEl.getBoundingClientRect();
            const oldPos = oldPositions[cardId];
            if (!oldPos) {
                // Card is entering
                cardEl.classList.add('card-entering');
                return;
            }
            const dx = oldPos.x - newRect.left;
            const dy = oldPos.y - newRect.top;
            if (dx === 0 && dy === 0)
                return; // No movement needed
            // Set initial position
            cardEl.style.transform = `translate(${dx}px, ${dy}px)`;
            cardEl.style.transition = 'none';
            // Trigger animation
            requestAnimationFrame(() => {
                cardEl.style.transition = 'transform 350ms cubic-bezier(0.4, 0, 0.2, 1)';
                cardEl.style.transform = '';
            });
        });
        // Cleanup animation classes after completion
        await new Promise((resolve) => setTimeout(resolve, 350));
        cards.forEach((el) => {
            const cardEl = el;
            cardEl.classList.remove('card-leaving', 'card-entering');
            cardEl.style.transition = '';
            cardEl.style.transform = '';
        });
        animatingRef.current = false;
    }, [gridRef]);
    return useRef({
        capturePositions,
        animateToNewPositions: async () => {
            await animateToNewPositions();
        },
    });
};
//# sourceMappingURL=useFLIPAnimation.js.map