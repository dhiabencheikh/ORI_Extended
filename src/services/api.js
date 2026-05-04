/**
 * ORI API Client — communicates with the FastAPI backend.
 */
const API_BASE = '/api';

export async function fetchJSON(endpoint, options = {}) {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export const api = {
  health: () => fetchJSON('/health'),
  getPersonas: () => fetchJSON('/personas'),
  getJourneyStages: () => fetchJSON('/journey-stages'),

  startSession: (persona) =>
    fetchJSON('/session/start', { method: 'POST', body: JSON.stringify({ persona }) }),

  onboardingAnswer: (session_id, question_id, answer) =>
    fetchJSON('/onboarding/answer', {
      method: 'POST',
      body: JSON.stringify({ session_id, question_id, answer }),
    }),

  chat: (session_id, message) =>
    fetchJSON('/chat', { method: 'POST', body: JSON.stringify({ session_id, message }) }),

  compare: (session_id, option1, option2, option3 = null) =>
    fetchJSON('/compare', {
      method: 'POST',
      body: JSON.stringify({ session_id, option1, option2, option3 }),
    }),

  recommend: (session_id, message) =>
    fetchJSON('/recommend', { method: 'POST', body: JSON.stringify({ session_id, message }) }),

  getProfile: (session_id) => fetchJSON(`/profile/${session_id}`),

  bookmark: (session_id, option) =>
    fetchJSON('/bookmark', { method: 'POST', body: JSON.stringify({ session_id, option }) }),

  trackClick: (session_id, url) =>
    fetchJSON('/track-click', { method: 'POST', body: JSON.stringify({ session_id, url }) }),
};
