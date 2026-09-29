import React from 'react';

/**
 * CloudOps Official Brand Mark — Exact User Logo Image
 */
export default function CloudOpsMark({ size = 36, className = '' }) {
  return (
    <img
      src="/cloudops-logo.png"
      alt="CloudOps Logo"
      style={{ width: size, height: 'auto', maxHeight: size }}
      className={`shrink-0 object-contain mix-blend-multiply ${className}`}
    />
  );
}
