/**
 * ORI Extended — Embeddable Widget Script
 * 
 * Usage:
 *   <script src="https://your-domain.com/ori-embed.js" 
 *           data-api-url="https://your-api.com"
 *           data-position="bottom-right"></script>
 */
(function () {
  'use strict';

  const script = document.currentScript;
  const API_URL = script?.getAttribute('data-api-url') || 'http://localhost:8000';
  const POSITION = script?.getAttribute('data-position') || 'bottom-right';
  const WIDGET_URL = script?.getAttribute('data-widget-url') || 'http://localhost:3000';

  // Create iframe container
  const container = document.createElement('div');
  container.id = 'ori-widget-embed';
  container.style.cssText = `
    position: fixed;
    ${POSITION.includes('right') ? 'right: 0' : 'left: 0'};
    bottom: 0;
    width: 440px;
    height: 100vh;
    z-index: 99999;
    pointer-events: none;
  `;

  const iframe = document.createElement('iframe');
  iframe.src = WIDGET_URL;
  iframe.style.cssText = `
    width: 100%;
    height: 100%;
    border: none;
    background: transparent;
    pointer-events: all;
  `;
  iframe.setAttribute('title', 'ORI - Compagnon d\'orientation L\'Étudiant');
  iframe.setAttribute('allow', 'microphone');

  container.appendChild(iframe);
  document.body.appendChild(container);
})();
