# ORI Extended — Decision Support Companion

> **L'Étudiant × Albert School** — Case 1: Youth Experience: From Information to 360° Personalised Guidance

## Overview

ORI Extended transforms L'Étudiant's conversational AI from a simple Q&A tool into a **personalised orientation decision-support companion**. It features:

- 🎭 **4 Personas** — Lycéen·ne, Collégien·ne, Parent, Enseignant·e
- 🧭 **Guided Onboarding** — Progressive profiling adapted per persona
- 💬 **Smart Chat** — RAG-grounded responses from L'Étudiant editorial content
- ⚖️ **Comparison Engine** — Side-by-side formation comparison with profile weighting
- 🏆 **Gamification** — XP, badges, decision journey tracking
- 📊 **Monetization** — Smart Traffic Bridge, partner school disclosure
- 📦 **Embeddable Widget** — Single `<script>` tag deployment

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- GCP Service Account key (`albert-school-team-1.json`)

### 1. Backend

```bash
cd ori-companion/backend
pip install -r requirements.txt

# Set up credentials
cp ../../"API Keys and Data Dictionaries for GCP Access"/albert-school-team-1.json ./credentials/
export GOOGLE_APPLICATION_CREDENTIALS=./credentials/albert-school-team-1.json

# Start server
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Frontend

```bash
cd ori-companion/frontend
npm install
npm run dev
```

### 3. Open

Visit [http://localhost:3000](http://localhost:3000)

## Embedding on External Sites

```html
<script src="https://your-domain.com/ori-embed.js"
        data-api-url="https://your-api-domain.com"
        data-widget-url="https://your-widget-domain.com">
</script>
```

## Architecture

```
ori-companion/
├── backend/
│   ├── main.py              # FastAPI app (all endpoints)
│   ├── ori_client.py         # ORI Reasoning Engine client + fallback RAG
│   ├── session_manager.py    # Session, profile, gamification state
│   ├── comparison_engine.py  # Formation comparison logic
│   ├── prompts.py            # System prompts, personas, milestones
│   └── requirements.txt
├── frontend/
│   ├── index.html            # Demo host page (simulates letudiant.fr)
│   ├── src/
│   │   ├── main.js           # Complete widget application
│   │   ├── services/api.js   # Backend API client
│   │   └── styles/widget.css # L'Étudiant-branded styles
│   ├── vite.config.js
│   └── package.json
└── embed/
    └── ori-embed.js          # Single-file embed script
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/personas` | Available personas |
| POST | `/api/session/start` | Create session |
| POST | `/api/onboarding/answer` | Submit onboarding answer |
| POST | `/api/chat` | Chat with ORI |
| POST | `/api/compare` | Compare formations |
| POST | `/api/recommend` | Get recommendations |
| GET | `/api/profile/{id}` | Get profile |
| POST | `/api/bookmark` | Bookmark option |
| POST | `/api/track-click` | Track article click |

## Tech Stack

- **LLM**: ORI Reasoning Engine (Vertex AI / Mistral AI Medium 3)
- **Backend**: Python, FastAPI, Uvicorn
- **Frontend**: Vanilla JS, Vite, CSS
- **Hosting**: GCP (Vertex AI Reasoning Engine)
- **Widget**: Shadow DOM / iframe embeddable

## Team

Albert School — Group 1 — B3 & MSc 1 Business Deep Dive
