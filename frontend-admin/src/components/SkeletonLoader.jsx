import React from 'react';
import './SkeletonLoader.css';

export default function SkeletonLoader() {
  return (
    <div className="skeleton-wrapper">
      <div className="skeleton-header"></div>
      <div className="skeleton-grid">
        <div className="skeleton-card"></div>
        <div className="skeleton-card"></div>
        <div className="skeleton-card"></div>
      </div>
    </div>
  );
}
