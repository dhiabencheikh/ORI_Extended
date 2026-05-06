"""
ORI Extended v3 — Deterministic Decision Engine.
The Decision Engine drives the conversation. GPT-4o executes.
"""

import os
import json
import logging
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from session_manager import SessionManager
from ori_client import ORIClient
from agent_ori import AgentORI
from decision_engine import DecisionEngine
from comparison_engine import build_comparison
from prompts import PERSONA_PROMPTS, DECISION_JOURNEY_STAGES, GAMIFICATION_MILESTONES

# ─────────────────────────────────────────────────────────────
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

session_manager = SessionManager()
ori_client = ORIClient()
agent = AgentORI(ori_client)
decision_engine = DecisionEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ORI Extended v3 (Decision Engine) starting up...")
    logger.info(f"  ORI RAG Engine : {'✅' if ori_client.is_available else '⚠️ FALLBACK'}")
    logger.info(f"  Agent ORI      : {'✅' if agent.is_available else '⚠️ DISABLED'}")
    yield
    logger.info("ORI Extended v3 shutting down.")


app = FastAPI(title="ORI Extended v3", version="3.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


# ── Models ──
class StartSessionRequest(BaseModel):
    persona: str = "lyceen"

class ChatRequest(BaseModel):
    session_id: str
    message: str

class OnboardingAnswerRequest(BaseModel):
    session_id: str
    question_id: str
    answer: str | list

class CompareRequest(BaseModel):
    session_id: str
    option1: str
    option2: str
    option3: Optional[str] = None

class BookmarkRequest(BaseModel):
    session_id: str
    option: dict

class ArticleClickRequest(BaseModel):
    session_id: str
    url: str


# ── Endpoints ──

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "3.0.0", "ori_engine": ori_client.is_available, "agent_active": agent.is_available}

@app.get("/api/personas")
async def get_personas():
    personas = {}
    for key, data in PERSONA_PROMPTS.items():
        personas[key] = {"id": key, "label": data["label"], "onboarding_questions": data["onboarding_questions"]}
    return {"personas": personas}

@app.get("/api/journey-stages")
async def get_journey_stages():
    return {"stages": DECISION_JOURNEY_STAGES}


@app.post("/api/session/start")
async def start_session(request: StartSessionRequest):
    if request.persona not in PERSONA_PROMPTS:
        raise HTTPException(status_code=400, detail=f"Unknown persona: {request.persona}")
    session = session_manager.create_session(request.persona)
    session["openai_thread_id"] = agent.create_thread()
    persona_data = PERSONA_PROMPTS[request.persona]
    return {
        "session_id": session["session_id"],
        "persona": request.persona,
        "persona_label": persona_data["label"],
        "onboarding_questions": persona_data["onboarding_questions"],
        "gamification": session_manager.get_gamification_state(session["session_id"]),
    }


@app.post("/api/onboarding/answer")
async def onboarding_answer(request: OnboardingAnswerRequest):
    session = session_manager.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session_manager.update_profile(request.session_id, request.question_id, request.answer)
    new_step = session_manager.advance_onboarding_step(request.session_id)

    persona_data = PERSONA_PROMPTS.get(session["persona"], {})
    total_questions = len(persona_data.get("onboarding_questions", []))
    is_complete = new_step >= total_questions

    result = {"step": new_step, "total_steps": total_questions, "is_complete": is_complete}

    if is_complete:
        session_manager.set_onboarding_complete(request.session_id)
        profile = session["profile"]
        persona = session["persona"]

        # ── Initialize Decision Engine with onboarding data ──
        decision_engine.process_onboarding(request.session_id, profile, persona)
        state_snapshot = decision_engine.get_audit_snapshot(request.session_id)

        # Generate welcome
        from response_enhancer import ResponseEnhancer
        enh = ResponseEnhancer()
        pending = enh.get_deepening_questions(profile, persona)
        welcome = await agent.generate_guided_welcome(profile, persona, pending, session["openai_thread_id"])

        session_manager.add_message(request.session_id, "assistant", welcome, metadata={"type": "welcome"})
        result["welcome_message"] = welcome
        result["gamification"] = session_manager.get_gamification_state(request.session_id)
        result["decision_state"] = state_snapshot

    return result


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    v3 Chat Pipeline:
    1. Decision Engine determines phase, strategy, and generates instructions
    2. Agent GPT-4o executes those instructions (with RAG tool access)
    3. Decision Engine extracts structured info and updates state
    4. Transition check
    """
    session = session_manager.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session_manager.add_message(request.session_id, "user", request.message)

    # ── Step 1: Decision Engine generates instructions ──
    engine_instructions = decision_engine.generate_agent_instructions(request.session_id, request.message)
    logger.info(f"[DecisionEngine] Phase={decision_engine.get_state(request.session_id)['phase']}, Instructions generated.")

    # ── Step 2: Agent executes ──
    if agent.is_available and session.get("openai_thread_id"):
        result = await agent.chat(
            thread_id=session["openai_thread_id"],
            user_message=request.message,
            engine_instructions=engine_instructions,
            persona=session["persona"],
        )
        response_text = result["response"]
        source = result["source"]
    else:
        ori_response = await ori_client.query(message=request.message, thread_id=session["ori_thread_id"], profile=session["profile"])
        response_text = ori_response["response"]
        source = "ori_fallback"

    # ── Step 3: Extract structured info and update state ──
    extraction = await agent.extract_structured_info(request.message, response_text)
    decision_engine.update_state_from_extraction(request.session_id, extraction)

    # ── Store message ──
    state_snapshot = decision_engine.get_audit_snapshot(request.session_id)
    session_manager.add_message(
        request.session_id, "assistant", response_text,
        metadata={"source": source, "phase": state_snapshot["phase"], "agentic": agent.is_available},
    )

    # Gamification
    intent = _classify_intent(request.message)
    session_manager.track_topic(request.session_id, intent)
    gamification = session_manager.get_gamification_state(request.session_id)
    new_badges = [b for b in session["badges"] if b not in (session.get("_last_badges") or [])]
    session["_last_badges"] = session["badges"].copy()

    return {
        "response": response_text,
        "source": source,
        "decision_state": state_snapshot,
        "gamification": gamification,
        "new_badges": new_badges,
        "journey_stage": session["journey_stage"],
    }


@app.post("/api/compare")
async def compare(request: CompareRequest):
    session = session_manager.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    options = [request.option1, request.option2]
    if request.option3:
        options.append(request.option3)
    comparison = await build_comparison(option1=request.option1, option2=request.option2, option3=request.option3, profile=session["profile"], agent=agent)
    session_manager.add_comparison(request.session_id, options)
    return {"comparison": comparison, "gamification": session_manager.get_gamification_state(request.session_id)}


@app.post("/api/bookmark")
async def bookmark(request: BookmarkRequest):
    session = session_manager.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session_manager.bookmark_option(request.session_id, request.option)
    return {"bookmarked": True, "total": len(session["bookmarked_options"])}


@app.post("/api/track-click")
async def track_click(request: ArticleClickRequest):
    session_manager.track_article_click(request.session_id, request.url)
    return {"tracked": True}


@app.get("/api/profile/{session_id}")
async def get_profile(session_id: str):
    summary = session_manager.get_profile_summary(session_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Session not found")
    return summary


@app.get("/api/decision-state/{session_id}")
async def get_decision_state(session_id: str):
    """Audit endpoint — returns the full decision state for debugging."""
    state = decision_engine.get_state(session_id)
    return {
        "phase": state["phase"],
        "strategy": state["strategy"],
        "confirmed": state["confirmed"],
        "inferred": state["inferred"],
        "missing": state["missing"],
        "constraints_covered": state["constraints_covered"],
        "hard_filters": state["hard_filters"],
        "options_pool": state["options_pool"],
        "shortlist": state["shortlist"],
        "turn_count": state["turn_count"],
        "turn_log": state["turn_log"][-10:],
    }


# ── Helpers ──

def _classify_intent(message: str) -> str:
    msg = message.lower()
    if any(w in msg for w in ["compare", "versus", "vs", "différence", "plutôt", "ou bien"]):
        return "comparison"
    elif any(w in msg for w in ["logement", "résidence", "loyer", "appart"]):
        return "logement"
    elif any(w in msg for w in ["bourse", "aide", "financement", "coût", "prix"]):
        return "bourses"
    elif any(w in msg for w in ["parcoursup", "vœux", "dossier", "candidature"]):
        return "parcoursup"
    elif any(w in msg for w in ["stage", "emploi", "job", "alternance"]):
        return "alternance"
    elif any(w in msg for w in ["bonjour", "salut", "hello", "merci"]):
        return "general"
    return "orientation"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
