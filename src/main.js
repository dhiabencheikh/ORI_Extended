/**
 * ORI Extended — Main Widget Application
 * L'Étudiant Decision Support Companion
 */
import { api } from './services/api.js';

// ─────────────────────────────────────────────────────────────
// State
// ─────────────────────────────────────────────────────────────
const state = {
  isOpen: false,
  isExpanded: false,
  view: 'persona',  // persona | onboarding | chat | profile | comparison
  sessionId: null,
  persona: null,
  personaLabel: '',
  profile: {},
  onboardingQuestions: [],
  onboardingStep: 0,
  onboardingAnswers: {},
  messages: [],
  isLoading: false,
  gamification: { xp: 0, badges: [], journey_stage: 'discover' },
  decisionState: null,
  journeyStages: [
    { id: 'discover', label: 'Découvrir', icon: '🌱' },
    { id: 'explore', label: 'Explorer', icon: '🔍' },
    { id: 'compare', label: 'Comparer', icon: '⚖️' },
    { id: 'decide', label: 'Décider', icon: '🎯' },
    { id: 'act', label: 'Agir', icon: '🚀' },
  ],
};

// ─────────────────────────────────────────────────────────────
// SVG Icons
// ─────────────────────────────────────────────────────────────
const ICONS = {
  chat: '<svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.17L4 17.17V4h16v12z"/><path d="M7 9h2v2H7zm4 0h2v2h-2zm4 0h2v2h-2z"/></svg>',
  close: '<svg viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>',
  send: '<svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>',
  profile: '<svg viewBox="0 0 24 24"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>',
  back: '<svg viewBox="0 0 24 24"><path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/></svg>',
};

// ─────────────────────────────────────────────────────────────
// Render Engine
// ─────────────────────────────────────────────────────────────
const root = document.getElementById('ori-widget-root');

function render() {
  root.innerHTML = `
    ${renderTrigger()}
    ${state.isOpen ? renderPanel() : ''}
  `;
  attachEvents();
}

function renderTrigger() {
  return `
    <button class="ori-trigger ${state.isOpen ? 'active' : ''}" id="ori-toggle" 
            aria-label="Ouvrir ORI">
      ${state.isOpen ? ICONS.close : ICONS.chat}
    </button>
  `;
}

function renderPanel() {
  return `
    <div class="ori-panel open ${state.isExpanded ? 'ori-expanded' : ''}" id="ori-widget-container">
      ${renderHeader()}
      ${state.view !== 'persona' ? renderJourneyBar() : ''}
      ${state.view !== 'persona' && state.view !== 'onboarding' ? renderXPBar() : ''}
      ${renderBody()}
    </div>
  `;
}

function renderHeader() {
  const showBack = state.view === 'profile' || state.view === 'comparison';
  return `
    <div class="ori-header">
      <div class="ori-header-left">
        ${showBack ? `<button class="ori-header-btn" id="ori-back">${ICONS.back}</button>` : ''}
        <div class="ori-avatar">ORI</div>
        <div class="ori-header-info">
          <h2>ORI</h2>
          <p>${state.personaLabel || "Compagnon d'orientation"} · L'Étudiant</p>
        </div>
      </div>
      <div class="ori-header-actions">
        <button class="ori-header-btn" id="ori-expand-btn" title="Agrandir">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>
        </button>
        <button class="ori-header-btn" id="ori-profile-btn" title="Mon profil">
          ${ICONS.profile}
        </button>
      </div>
    </div>
  `;
}

function renderJourneyBar() {
  const stages = state.journeyStages;
  const currentIdx = stages.findIndex(s => s.id === state.gamification.journey_stage);
  return `
    <div class="ori-journey-bar">
      ${stages.map((s, i) => `
        ${i > 0 ? '<div class="ori-journey-line"></div>' : ''}
        <div class="ori-journey-step ${i === currentIdx ? 'active' : ''} ${i < currentIdx ? 'completed' : ''}">
          <div class="ori-journey-dot ${i === currentIdx ? 'active' : ''} ${i < currentIdx ? 'completed' : ''}">${s.icon}</div>
          <div class="ori-journey-label">${s.label}</div>
        </div>
      `).join('')}
    </div>
  `;
}

function renderXPBar() {
  const xp = state.gamification.xp || 0;
  const maxXP = 300;
  const pct = Math.min((xp / maxXP) * 100, 100);
  return `
    <div class="ori-xp-bar">
      <div class="ori-xp-track">
        <div class="ori-xp-fill" style="width: ${pct}%"></div>
      </div>
      <div class="ori-xp-label">${xp} XP</div>
    </div>
  `;
}

function renderBody() {
  switch (state.view) {
    case 'persona': return renderPersonaScreen();
    case 'onboarding': return renderOnboarding();
    case 'chat': return renderChat();
    case 'profile': return renderProfile();
    case 'comparison': return renderComparison();
    default: return renderChat();
  }
}

// ─── Persona Selection ───
function renderPersonaScreen() {
  const personas = [
    { id: 'lyceen', emoji: '🎓', label: 'Lycéen·ne', desc: 'Orientation post-bac' },
    { id: 'collegien', emoji: '🎒', label: 'Collégien·ne', desc: 'Découverte des voies' },
    { id: 'parent', emoji: '👨‍👩‍👧', label: 'Parent', desc: 'Accompagner mon enfant' },
    { id: 'enseignant', emoji: '🧑‍🏫', label: 'Enseignant·e', desc: 'Guider mes élèves' },
  ];
  return `
    <div class="ori-persona-screen">
      <h3>Bienvenue sur ORI 👋</h3>
      <p>Je suis votre compagnon d'orientation intelligent, alimenté par le contenu éditorial de L'Étudiant.</p>
      <p><strong>Qui êtes-vous ?</strong></p>
      <div class="ori-persona-grid">
        ${personas.map(p => `
          <div class="ori-persona-card" data-persona="${p.id}">
            <span class="emoji">${p.emoji}</span>
            <div class="label">${p.label}</div>
            <div class="desc">${p.desc}</div>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

// ─── Onboarding ───
function renderOnboarding() {
  const q = state.onboardingQuestions[state.onboardingStep];
  if (!q) return '<div class="ori-onboarding"><p>Chargement...</p></div>';

  const isMulti = q.type === 'multi_select';
  const selected = state.onboardingAnswers[q.id] || (isMulti ? [] : '');

  return `
    <div class="ori-onboarding">
      <div class="ori-onboarding-top">
        <div class="ori-onboarding-progress">
          ${state.onboardingQuestions.map((_, i) => `
            <div class="dot ${i < state.onboardingStep ? 'done' : ''} ${i === state.onboardingStep ? 'active' : ''}"></div>
          `).join('')}
        </div>
        <h3>${q.question}</h3>
        ${isMulti ? '<p style="font-size:12px;color:#9ca3af;">Plusieurs choix possibles</p>' : ''}
      </div>
      <div class="ori-onboarding-choices">
        ${q.options.map(opt => {
          const isSelected = isMulti ? selected.includes(opt) : selected === opt;
          return `
            <button class="ori-choice-btn ${isMulti ? 'multi' : ''} ${isSelected ? 'selected' : ''}"
                    data-question="${q.id}" data-value="${opt}" data-multi="${isMulti}">
              ${opt}
            </button>
          `;
        }).join('')}
      </div>
      <div class="ori-onboarding-bottom">
        <button class="ori-onboarding-next" id="ori-next-btn"
                ${(!selected || (isMulti && selected.length === 0)) ? 'disabled' : ''}>
          ${state.onboardingStep < state.onboardingQuestions.length - 1 ? 'Continuer →' : 'Terminer ✓'}
        </button>
      </div>
    </div>
  `;
}

// ─── Chat ───
function renderPhaseIndicator() {
  const ds = state.decisionState;
  if (!ds) return '';
  const phases = [
    { id: 'CADRAGE', label: 'Cadrage', icon: '📋' },
    { id: 'AFFINEMENT', label: 'Affinement', icon: '🔍' },
    { id: 'RESSERREMENT', label: 'Resserrement', icon: '🎯' },
    { id: 'DECISION', label: 'Décision', icon: '🏆' },
  ];
  const currentIdx = phases.findIndex(p => p.id === ds.phase);
  return `
    <div class="ori-phase-bar">
      <div class="ori-phase-steps">
        ${phases.map((p, i) => `
          <div class="ori-phase-step ${i < currentIdx ? 'done' : ''} ${i === currentIdx ? 'active' : ''}">
            <span class="ori-phase-icon">${p.icon}</span>
            <span class="ori-phase-label">${p.label}</span>
          </div>
        `).join('<div class="ori-phase-connector"></div>')}
      </div>
      <div class="ori-phase-progress-track">
        <div class="ori-phase-progress-fill" style="width:${ds.progress_pct || 0}%"></div>
      </div>
    </div>
  `;
}

function renderChat() {
  return `
    ${renderPhaseIndicator()}
    <div class="ori-messages" id="ori-messages">
      ${state.messages.map(m => renderMessage(m)).join('')}
      ${state.isLoading ? renderTyping() : ''}
      ${!state.isLoading ? renderSuggestedReplies() : ''}
    </div>
    ${renderQuickActions()}
    <div class="ori-input-bar">
      <input class="ori-input" id="ori-input" type="text" 
             placeholder="Pose ta question à ORI..." 
             ${state.isLoading ? 'disabled' : ''} />
      <button class="ori-send-btn" id="ori-send" ${state.isLoading ? 'disabled' : ''}>
        ${ICONS.send}
      </button>
    </div>
  `;
}

function renderSuggestedReplies() {
  const ds = state.decisionState;
  if (!ds || !ds.suggested_replies || ds.suggested_replies.length === 0 || state.isLoading) return '';
  return `
    <div class="ori-suggested-replies">
      ${ds.suggested_replies.map(r => `
        <button class="ori-reply-btn ${r.value === '' ? 'ori-reply-free' : ''}" 
                data-reply-value="${r.value}">${r.label}</button>
      `).join('')}
    </div>
  `;
}

function renderMessage(msg) {
  const isBot = msg.role === 'assistant';
  const content = msg.is_raw_html ? msg.content : formatMarkdown(msg.content);
  return `
    <div class="ori-msg ${isBot ? 'ori-msg-bot' : 'ori-msg-user'}">
      <div class="ori-msg-bubble">${content}</div>
    </div>
  `;
}

function renderTyping() {
  return `
    <div class="ori-msg ori-msg-bot">
      <div class="ori-msg-bubble">
        <div class="ori-typing"><span></span><span></span><span></span></div>
      </div>
    </div>
  `;
}

function renderQuickActions() {
  const actions = getQuickActions();
  if (actions.length === 0) return '';
  return `
    <div class="ori-quick-actions">
      ${actions.map(a => `
        <button class="ori-quick-btn" data-action="${a.action}" data-value="${a.value || ''}">${a.label}</button>
      `).join('')}
    </div>
  `;
}

function getQuickActions() {
  if (state.messages.length === 0) return [];
  const p = state.persona;
  if (p === 'lyceen') return [
    { label: '🔍 Formations pour moi', action: 'chat', value: 'Quelles formations correspondent à mon profil ?' },
    { label: '⚖️ Comparer 2 écoles', action: 'compare' },
    { label: '🏠 Logement', action: 'chat', value: 'Comment trouver un logement étudiant ?' },
    { label: '💰 Bourses & aides', action: 'chat', value: 'Quelles aides financières existent pour les étudiants ?' },
    { label: '📋 Parcoursup', action: 'chat', value: 'Comment fonctionne Parcoursup ?' },
    { label: '🔄 Alternance', action: 'chat', value: 'Comment fonctionne l alternance ?' },
  ];
  if (p === 'collegien') return [
    { label: '🌟 Métiers', action: 'chat', value: 'Quels métiers existent dans les domaines qui me plaisent ?' },
    { label: '🛤️ Les voies', action: 'chat', value: 'Quelle est la différence entre voie générale, techno et pro ?' },
    { label: '🎮 Quiz orientation', action: 'chat', value: 'Fais-moi un mini quiz pour découvrir ce qui pourrait me plaire' },
  ];
  if (p === 'parent') return [
    { label: '📚 Formations', action: 'chat', value: 'Quelles formations recommandez-vous pour mon enfant ?' },
    { label: '💰 Coûts & bourses', action: 'chat', value: 'Combien coûtent les études et quelles aides existent ?' },
    { label: '🏠 Logement', action: 'chat', value: 'Comment trouver un logement étudiant ?' },
    { label: '⚖️ Comparer', action: 'compare' },
    { label: '📋 Parcoursup', action: 'chat', value: 'Comment accompagner mon enfant sur Parcoursup ?' },
  ];
  if (p === 'enseignant') return [
    { label: '🔍 Rechercher formations', action: 'chat', value: 'Je cherche des formations adaptées pour un élève' },
    { label: '⚖️ Comparer', action: 'compare' },
    { label: '📊 Statistiques', action: 'chat', value: 'Quels sont les taux d insertion des principales filières ?' },
    { label: '📋 Ressources', action: 'chat', value: 'Quelles ressources L Étudiant pour préparer une séance d orientation ?' },
  ];
  return [
    { label: '🔍 Explorer', action: 'chat', value: 'Aide-moi à explorer mes options' },
    { label: '⚖️ Comparer', action: 'compare' },
  ];
}

// ─── Profile View ───
function renderProfile() {
  const g = state.gamification;
  const profile = state.profile || {};
  return `
    <div class="ori-profile-panel">
      <div class="ori-profile-section">
        <h4>Mon Profil</h4>
        ${Object.entries(profile).map(([k, v]) => `
          <div style="margin-bottom:6px;">
            <span style="font-size:12px;color:#9ca3af;text-transform:capitalize;">${k.replace(/_/g, ' ')}</span>
            <div>${Array.isArray(v) ? v.map(i => `<span class="ori-profile-tag">${i}</span>`).join('') : `<span class="ori-profile-tag">${v}</span>`}</div>
          </div>
        `).join('')}
      </div>
      <div class="ori-profile-section">
        <h4>Mes Badges (${g.badges?.length || 0})</h4>
        <div class="ori-profile-badges">
          ${(g.badges || []).map(b => `
            <div class="ori-profile-badge">
              <span class="emoji">${b.badge}</span>
              <span>${b.title}</span>
            </div>
          `).join('') || '<p style="font-size:12px;color:#9ca3af;">Aucun badge pour le moment</p>'}
        </div>
      </div>
      <div class="ori-profile-section">
        <h4>Progression : ${g.xp || 0} XP</h4>
        <div class="ori-xp-track" style="height:8px;">
          <div class="ori-xp-fill" style="width:${Math.min(((g.xp||0)/300)*100, 100)}%"></div>
        </div>
      </div>
    </div>
  `;
}

// ─── Comparison View ───
function renderComparison() {
  return `
    <div class="ori-onboarding">
      <h3>⚖️ Comparer des formations</h3>
      <p style="font-size:13px;color:#6b7280;">Choisis 2 formations à comparer</p>
      <input class="ori-input" id="ori-cmp-1" placeholder="Formation 1 (ex: INSA Lyon)" style="margin-bottom:8px;width:100%;" />
      <input class="ori-input" id="ori-cmp-2" placeholder="Formation 2 (ex: Télécom Paris)" style="margin-bottom:8px;width:100%;" />
      <input class="ori-input" id="ori-cmp-3" placeholder="Formation 3 (optionnel)" style="margin-bottom:8px;width:100%;" />
      <button class="ori-onboarding-next" id="ori-cmp-go">Comparer →</button>
    </div>
  `;
}

// ─────────────────────────────────────────────────────────────
// Event Handling
// ─────────────────────────────────────────────────────────────
function attachEvents() {
  // Toggle widget
  document.getElementById('ori-toggle')?.addEventListener('click', () => {
    state.isOpen = !state.isOpen;
    render();
  });

  // Persona selection
  document.querySelectorAll('.ori-persona-card').forEach(el => {
    el.addEventListener('click', () => selectPersona(el.dataset.persona));
  });

  // Onboarding choices
  document.querySelectorAll('.ori-choice-btn').forEach(el => {
    el.addEventListener('click', () => handleOnboardingChoice(el));
  });

  // Next button
  document.getElementById('ori-next-btn')?.addEventListener('click', handleOnboardingNext);

  // Chat send
  document.getElementById('ori-send')?.addEventListener('click', handleSend);
  document.getElementById('ori-input')?.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  });

  // Quick actions
  document.querySelectorAll('.ori-quick-btn').forEach(el => {
    el.addEventListener('click', () => handleQuickAction(el.dataset.action, el.dataset.value));
  });

  // Suggested reply buttons
  document.querySelectorAll('.ori-reply-btn').forEach(el => {
    el.addEventListener('click', () => {
      const val = el.dataset.replyValue;
      if (val === '') {
        // Free text option — focus input
        document.getElementById('ori-input')?.focus();
      } else {
        sendMessage(val);
      }
    });
  });

  // Profile button
  document.getElementById('ori-profile-btn')?.addEventListener('click', () => {
    state.view = state.view === 'profile' ? 'chat' : 'profile';
    render();
  });

  // Expand toggle
  document.getElementById('ori-expand-btn')?.addEventListener('click', () => {
    state.isExpanded = !state.isExpanded;
    const container = document.getElementById('ori-widget-container');
    if (container) container.classList.toggle('ori-expanded', state.isExpanded);
  });

  // Back button
  document.getElementById('ori-back')?.addEventListener('click', () => {
    state.view = 'chat';
    render();
  });

  // Compare button
  document.getElementById('ori-cmp-go')?.addEventListener('click', handleCompare);

  // Auto-scroll messages
  const msgs = document.getElementById('ori-messages');
  if (msgs) msgs.scrollTop = msgs.scrollHeight;

  // Focus input
  if (state.view === 'chat' && !state.isLoading) {
    document.getElementById('ori-input')?.focus();
  }
}

// ─── Persona Selection ───
async function selectPersona(personaId) {
  try {
    const data = await api.startSession(personaId);
    state.sessionId = data.session_id;
    state.persona = personaId;
    state.personaLabel = data.persona_label;
    state.onboardingQuestions = data.onboarding_questions;
    state.onboardingStep = 0;
    state.onboardingAnswers = {};
    state.gamification = data.gamification || state.gamification;
    state.view = 'onboarding';
    render();
  } catch (e) {
    console.error('Failed to start session:', e);
  }
}

// ─── Onboarding ───
function handleOnboardingChoice(el) {
  const qId = el.dataset.question;
  const value = el.dataset.value;
  const isMulti = el.dataset.multi === 'true';

  if (isMulti) {
    const current = state.onboardingAnswers[qId] || [];
    if (current.includes(value)) {
      state.onboardingAnswers[qId] = current.filter(v => v !== value);
    } else {
      state.onboardingAnswers[qId] = [...current, value];
    }
  } else {
    state.onboardingAnswers[qId] = value;
  }
  render();
}

async function handleOnboardingNext() {
  const q = state.onboardingQuestions[state.onboardingStep];
  const answer = state.onboardingAnswers[q.id];

  try {
    const data = await api.onboardingAnswer(state.sessionId, q.id, answer);

    if (data.is_complete) {
      // Onboarding done — switch to chat with welcome message
      state.profile = {};
      for (const [k, v] of Object.entries(state.onboardingAnswers)) {
        state.profile[k] = v;
      }
      state.messages = [{
        role: 'assistant',
        content: data.welcome_message || 'Bienvenue ! Comment puis-je t\'aider ?',
      }];
      state.gamification = data.gamification || state.gamification;
      if (data.decision_state) state.decisionState = data.decision_state;
      state.view = 'chat';
    } else {
      state.onboardingStep = data.step;
    }
    render();
  } catch (e) {
    console.error('Onboarding error:', e);
    // Offline fallback: advance locally
    if (state.onboardingStep < state.onboardingQuestions.length - 1) {
      state.onboardingStep++;
    } else {
      state.profile = { ...state.onboardingAnswers };
      state.messages = [{ role: 'assistant', content: generateLocalWelcome() }];
      state.view = 'chat';
    }
    render();
  }
}

function generateLocalWelcome() {
  const p = state.onboardingAnswers;
  const interests = Array.isArray(p.interests) ? p.interests.join(', ') : (p.interests || '');
  if (state.persona === 'lyceen') {
    return `Merci ! Voilà ce que j'ai compris :\n\n📚 **Niveau** : ${p.level || '?'}\n💡 **Intérêts** : ${interests || '?'}\n🧭 **Étape** : ${p.stage || '?'}\n\nJe suis prêt à t'aider ! Pose-moi n'importe quelle question sur l'orientation, la vie étudiante, le logement, les bourses… 🚀`;
  }
  return `Merci pour ces informations ! Je suis prêt à vous aider. Posez-moi vos questions ! 😊`;
}

// ─── Chat ───
async function handleSend() {
  const input = document.getElementById('ori-input');
  const msg = input?.value?.trim();
  if (!msg || state.isLoading) return;
  sendMessage(msg);
}

function handleQuickAction(action, value) {
  if (action === 'compare') {
    state.view = 'comparison';
    render();
  } else if (action === 'chat' && value) {
    // Directly send the message without needing the input element
    sendMessage(value);
  }
}

async function sendMessage(msg) {
  if (!msg || state.isLoading) return;
  state.messages.push({ role: 'user', content: msg });
  state.isLoading = true;
  render();
  try {
    const data = await api.chat(state.sessionId, msg);
    state.messages.push({ role: 'assistant', content: data.response });
    if (data.decision_state) state.decisionState = data.decision_state;
    if (data.gamification) state.gamification = data.gamification;
    if (data.new_badges?.length > 0) {
      setTimeout(() => showBadgeNotif(data.new_badges[0]), 300);
    }
  } catch (e) {
    console.error('Chat error:', e);
    state.messages.push({ role: 'assistant', content: "Désolé, je rencontre un problème technique. Réessaie dans un instant ! 🔧" });
  }
  state.isLoading = false;
  render();
}

// ─── Comparison ───
async function handleCompare() {
  const opt1 = document.getElementById('ori-cmp-1')?.value?.trim();
  const opt2 = document.getElementById('ori-cmp-2')?.value?.trim();
  const opt3 = document.getElementById('ori-cmp-3')?.value?.trim() || null;

  if (!opt1 || !opt2) return;

  state.isLoading = true;
  state.view = 'chat';
  state.messages.push({ role: 'user', content: `Compare ${opt1} et ${opt2}${opt3 ? ` et ${opt3}` : ''}` });
  render();

  try {
    const data = await api.compare(state.sessionId, opt1, opt2, opt3);
    const cmp = data.comparison;
    state.gamification = data.gamification || state.gamification;

    // Format comparison as rich HTML UI
    const options = cmp.options;
    const colCount = options.length;
    
    // Grid template for 2 options: 1fr 1fr 1fr (criterion, opt1, opt2)
    // Grid template for 3 options: 1fr 1fr 1fr 1fr
    const gridStyle = `grid-template-columns: 120px repeat(${colCount}, 1fr);`;

    let html = `<div class="ori-comparison" style="margin-top: 8px;">`;
    
    // Header
    html += `<div class="ori-comparison-header" style="${gridStyle}">`;
    html += `<div>Critères</div>`;
    options.forEach((opt, idx) => {
      // Find URL if available to fetch favicon
      let optUrl = '';
      if (cmp.traffic_links && cmp.traffic_links[idx]) {
        optUrl = cmp.traffic_links[idx].url;
      }
      let faviconHtml = optUrl ? `<img src="https://www.google.com/s2/favicons?domain=${new URL(optUrl).hostname}&sz=32" style="width:16px;height:16px;vertical-align:middle;margin-right:4px;border-radius:50%;">` : '🏫 ';
      html += `<div>${faviconHtml}${opt}</div>`;
    });
    html += `</div>`;

    // Rows
    for (const c of cmp.criteria) {
      // Check if this row has a "best_for_profile" match
      const highlightClass = c.best_for_profile && c.best_for_profile !== "null" ? "highlight" : "";
      
      html += `<div class="ori-comparison-row ${highlightClass}" style="${gridStyle}">`;
      html += `<div class="criterion">${c.name}</div>`;
      
      options.forEach(opt => {
        let val = c.values[opt] || "—";
        // If this is the best value, make it bold and add a star
        const isBest = c.best_for_profile && c.best_for_profile.includes(opt);
        if (isBest) {
          val = `<strong>⭐ ${val}</strong>`;
        }
        html += `<div class="value">${val}</div>`;
      });
      
      html += `</div>`;
    }

    // Recommendation
    if (cmp.recommendation && cmp.recommendation.choice) {
      html += `<div class="ori-comparison-rec">`;
      html += `<strong>🏆 Recommandation ORI : ${cmp.recommendation.choice}</strong><br>`;
      html += `<span style="font-size:12px;">${cmp.recommendation.reason}</span>`;
      html += `</div>`;
    }

    html += `</div>`;

    // Traffic links below the table
    if (cmp.traffic_links?.length) {
      html += `<div style="margin-top: 8px; display: flex; flex-direction: column; gap: 4px;">`;
      html += cmp.traffic_links.map(l => `📎 <a href="${l.url}" target="_blank" rel="noopener" class="ori-link" onclick="window.__oriTrackClick && window.__oriTrackClick('${l.url}')">${l.label}</a>`).join('');
      html += `</div>`;
    }

    // We inject the HTML directly as a raw message without markdown processing
    state.messages.push({ role: 'assistant', content: html, is_raw_html: true });
  } catch (e) {
    console.error('Compare error:', e);
    state.messages.push({ role: 'assistant', content: "Désolé, je n'ai pas pu comparer ces formations. Réessaie ! 🔧" });
  }

  state.isLoading = false;
  render();
}

// ─── Badge Notification ───
function showBadgeNotif(badge) {
  const panel = document.querySelector('.ori-panel');
  if (!panel) return;
  const notif = document.createElement('div');
  notif.className = 'ori-badge-notif';
  notif.innerHTML = `${badge.badge} ${badge.title} — +${badge.xp || ''}XP`;
  panel.style.position = 'relative';
  panel.appendChild(notif);
  setTimeout(() => notif.remove(), 3200);
}

// ─── Markdown-ish Formatting ───
function formatMarkdown(text) {
  if (!text) return '';
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\[(.+?)\]\((.+?)\)/g, (_, label, url) => {
      return `<a href="${url}" target="_blank" rel="noopener" class="ori-link" onclick="window.__oriTrackClick && window.__oriTrackClick('${url}')">${label}</a>`;
    })
    .replace(/\n/g, '<br/>');
}

// Track article clicks for monetization
window.__oriTrackClick = (url) => {
  if (state.sessionId) {
    api.trackClick(state.sessionId, url).catch(() => {});
  }
};

// ─── Init ───
render();
