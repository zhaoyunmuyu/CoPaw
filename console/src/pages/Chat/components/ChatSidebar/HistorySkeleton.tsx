import React from 'react';

interface HistorySkeletonProps {
  count?: number;
}

export function HistorySkeleton({ count = 8 }: HistorySkeletonProps) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="chat-sidebar-history-skeleton-item">
          <div className="chat-sidebar-history-skeleton-title" />
          <div className="chat-sidebar-history-skeleton-time" />
        </div>
      ))}
    </>
  );
}