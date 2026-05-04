"""
Session Manager — In-memory session and profile storage for ORI Extended.
"""

import uuid
import time
from typing import Optional


class SessionManager:
    """Manages user sessions, profiles, gamification state and conversation history."""

    def __init__(self):
        self._sessions: dict = {}

    def create_session(self, persona: str = "lyceen") -> dict:
        """Create a new session with the given persona."""
        session_id = str(uuid.uuid4())
        session = {
            "session_id": session_id,
            "persona": persona,
            "created_at": time.time(),
            "last_active": time.time(),
            "profile": {},
            "onboarding_complete": False,
            "onboarding_step": 0,
            "conversation_history": [],
            "compared_options": [],
            "recommended_options": [],
            "bookmarked_options": [],
            # Gamification
            "xp": 0,
            "badges": [],
            "question_count": 0,
            "topics_explored": set(),
            "journey_stage": "discover",
            # Monetization tracking
            "article_clicks": 0,
            "partner_impressions": [],
            # Thread IDs for continuity
            "ori_thread_id": session_id,
            "openai_thread_id": None,
        }
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[dict]:
        """Retrieve a session by ID."""
        session = self._sessions.get(session_id)
        if session:
            session["last_active"] = time.time()
        return session

    def update_profile(self, session_id: str, field: str, value) -> Optional[dict]:
        """Update a specific field in the session profile."""
        session = self._sessions.get(session_id)
        if not session:
            return None
        session["profile"][field] = value
        session["last_active"] = time.time()
        return session

    def set_onboarding_complete(self, session_id: str) -> Optional[dict]:
        """Mark onboarding as complete and award the badge."""
        session = self._sessions.get(session_id)
        if not session:
            return None
        session["onboarding_complete"] = True
        self._award_badge(session_id, "profile_complete")
        return session

    def advance_onboarding_step(self, session_id: str) -> Optional[int]:
        """Advance to the next onboarding question."""
        session = self._sessions.get(session_id)
        if not session:
            return None
        session["onboarding_step"] += 1
        return session["onboarding_step"]

    def add_message(self, session_id: str, role: str, content: str, metadata: dict = None):
        """Add a message to the conversation history."""
        session = self._sessions.get(session_id)
        if not session:
            return
        message = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
            "metadata": metadata or {},
        }
        session["conversation_history"].append(message)

        if role == "user":
            session["question_count"] += 1
            # Check gamification milestones
            if session["question_count"] == 5:
                self._award_badge(session_id, "five_questions")
            elif session["question_count"] == 10:
                self._award_badge(session_id, "ten_questions")

    def track_topic(self, session_id: str, topic: str):
        """Track that a topic was explored (for gamification)."""
        session = self._sessions.get(session_id)
        if not session:
            return
        session["topics_explored"].add(topic)
        if len(session["topics_explored"]) >= 3:
            self._award_badge(session_id, "topic_diversity")

    def add_comparison(self, session_id: str, options: list):
        """Record a comparison action."""
        session = self._sessions.get(session_id)
        if not session:
            return
        session["compared_options"].extend(options)
        if not any(b["id"] == "first_comparison" for b in session["badges"]):
            self._award_badge(session_id, "first_comparison")
        # Advance journey stage
        self._advance_journey(session_id, "compare")

    def add_recommendation(self, session_id: str, options: list):
        """Record recommendations shown."""
        session = self._sessions.get(session_id)
        if not session:
            return
        session["recommended_options"].extend(options)
        if not any(b["id"] == "first_recommendation" for b in session["badges"]):
            self._award_badge(session_id, "first_recommendation")
        self._advance_journey(session_id, "explore")

    def bookmark_option(self, session_id: str, option: dict):
        """Bookmark a formation/school option."""
        session = self._sessions.get(session_id)
        if not session:
            return
        if option not in session["bookmarked_options"]:
            session["bookmarked_options"].append(option)

    def track_article_click(self, session_id: str, url: str):
        """Track when a user clicks through to a L'Étudiant article."""
        session = self._sessions.get(session_id)
        if not session:
            return
        session["article_clicks"] += 1

    def get_gamification_state(self, session_id: str) -> Optional[dict]:
        """Get the current gamification state."""
        session = self._sessions.get(session_id)
        if not session:
            return None
        return {
            "xp": session["xp"],
            "badges": session["badges"],
            "journey_stage": session["journey_stage"],
            "question_count": session["question_count"],
            "topics_explored": list(session["topics_explored"]),
            "bookmarked_count": len(session["bookmarked_options"]),
        }

    def _award_badge(self, session_id: str, badge_id: str):
        """Award a gamification badge."""
        from prompts import GAMIFICATION_MILESTONES

        session = self._sessions.get(session_id)
        if not session:
            return
        if any(b["id"] == badge_id for b in session["badges"]):
            return  # Already awarded

        milestone = GAMIFICATION_MILESTONES.get(badge_id)
        if milestone:
            badge = {
                "id": badge_id,
                "badge": milestone["badge"],
                "title": milestone["title"],
                "message": milestone["message"],
                "awarded_at": time.time(),
            }
            session["badges"].append(badge)
            session["xp"] += milestone["xp"]

    def _advance_journey(self, session_id: str, target_stage: str):
        """Advance the decision journey stage if the target is ahead of current."""
        stage_order = ["discover", "explore", "compare", "decide", "act"]
        session = self._sessions.get(session_id)
        if not session:
            return
        current_idx = stage_order.index(session["journey_stage"])
        target_idx = stage_order.index(target_stage)
        if target_idx > current_idx:
            session["journey_stage"] = target_stage

    def get_profile_summary(self, session_id: str) -> dict:
        """Get a serializable summary of the session for API responses."""
        session = self._sessions.get(session_id)
        if not session:
            return {}
        return {
            "session_id": session["session_id"],
            "persona": session["persona"],
            "profile": session["profile"],
            "onboarding_complete": session["onboarding_complete"],
            "onboarding_step": session["onboarding_step"],
            "gamification": self.get_gamification_state(session_id),
            "bookmarked_options": session["bookmarked_options"],
        }

    def build_profile_context(self, session_id: str) -> str:
        """Build a rich natural-language profile summary for GPT-4o."""
        session = self._sessions.get(session_id)
        if not session:
            return "Profil inconnu."

        profile = session["profile"]
        persona = session["persona"]
        parts = []

        if persona == "lyceen":
            level = profile.get("level", "")
            track = profile.get("track", "")
            interests = profile.get("interests", [])
            stage = profile.get("stage", "")
            constraints = profile.get("constraints", [])
            region = profile.get("region", "")

            if level:
                parts.append(f"Élève en {level}")
            if track:
                parts.append(f"filière {track}")
            if interests:
                parts.append(f"passionné·e par {', '.join(interests)}")
            if stage:
                parts.append(f"étape d'orientation: {stage}")
            if constraints:
                c_list = constraints if isinstance(constraints, list) else [constraints]
                parts.append(f"contraintes: {', '.join(c_list)}")
            if region:
                parts.append(f"région: {region}")

        elif persona == "collegien":
            level = profile.get("level", "")
            interests = profile.get("interests", [])
            if level:
                parts.append(f"Élève en {level}")
            if interests:
                parts.append(f"aime {', '.join(interests)}")

        elif persona == "parent":
            child_level = profile.get("child_level", "")
            concern = profile.get("concern", "")
            constraints = profile.get("constraints", [])
            if child_level:
                parts.append(f"Enfant en {child_level}")
            if concern:
                parts.append(f"préoccupation: {concern}")
            if constraints:
                c_list = constraints if isinstance(constraints, list) else [constraints]
                parts.append(f"critères: {', '.join(c_list)}")

        elif persona == "enseignant":
            role = profile.get("role", "")
            student_level = profile.get("student_level", "")
            need = profile.get("need", "")
            if role:
                parts.append(role)
            if student_level:
                parts.append(f"enseigne au {student_level}")
            if need:
                parts.append(f"besoin: {need}")

        # Add exploration history
        topics = list(session.get("topics_explored", []))
        if topics:
            parts.append(f"sujets déjà explorés: {', '.join(topics)}")

        unexplored = [t for t in ["orientation", "logement", "bourses", "parcoursup", "alternance", "vie étudiante"]
                       if t not in topics]
        if unexplored and len(topics) > 0:
            parts.append(f"pas encore exploré: {', '.join(unexplored[:3])}")

        return ". ".join(parts) + "." if parts else "Profil en cours de construction."

    def build_conversation_summary(self, session_id: str, max_messages: int = 6) -> str:
        """Build a short summary of the conversation so far for GPT-4o context."""
        session = self._sessions.get(session_id)
        if not session:
            return ""

        history = session.get("conversation_history", [])
        if not history:
            return "Début de la conversation."

        # Take last N messages
        recent = history[-max_messages:]
        lines = []
        for msg in recent:
            role = "Utilisateur" if msg["role"] == "user" else "ORI"
            content = msg["content"][:150] + "..." if len(msg["content"]) > 150 else msg["content"]
            lines.append(f"{role}: {content}")

        return "\n".join(lines)

    def store_profile_extra(self, session_id: str, field: str, value):
        """Store additional profile data gathered during conversation (e.g., region)."""
        session = self._sessions.get(session_id)
        if not session:
            return
        session["profile"][field] = value

