import React from 'react';
import CloudOpsMark from './CloudOpsMark';

/**
 * CloudOpsLogo — used in HeaderNav and anywhere else that needs
 * the full brand mark + wordmark combination.
 *
 * Props:
 *   className  – applied to the outer wrapper (for sizing/layout tweaks)
 *   showText   – render the "CloudOps / AI Cloud Platform" wordmark
 *   markSize   – pixel size passed to CloudOpsMark (default 36)
 */
export default function CloudOpsLogo({ className = '', showText = true, markSize = 34 }) {
  return (
    <div className={`flex items-center space-x-3 group select-none ${className}`}>
      {/* Distinctive brand mark */}
      <div className="transition-transform duration-200 group-hover:scale-105 shrink-0">
        <CloudOpsMark size={markSize} />
      </div>

      {/* Wordmark */}
      {showText && (
        <div className="leading-none">
          <span className="block font-extrabold tracking-tight text-[17px] text-[#0F172A] leading-none">
            CloudOps
          </span>
          <span className="block text-[10px] font-semibold text-[#0284C7] mt-1 tracking-wide uppercase">
            AI Cloud Platform
          </span>
        </div>
      )}
    </div>
  );
}
