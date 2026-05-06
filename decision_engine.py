"""
Decision Engine — Deterministic state machine for ORI v3.
Drives the conversation through 4 phases toward a decision.
GPT-4o is a tool of this engine, not the pilot.
"""

import json
import logging
import time
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


class Phase(str, Enum):
    CADRAGE = "CADRAGE"
    AFFINEMENT = "AFFINEMENT"
    RESSERREMENT = "RESSERREMENT"
    DECISION = "DECISION"


class Strategy(str, Enum):
    PROJET_PRECIS = "PROJET_PRECIS"
    HESITATION = "HESITATION"
    EXPLORATION_OUVERTE = "EXPLORATION_OUVERTE"
    REORIENTATION = "REORIENTATION"
    UNDETERMINED = "UNDETERMINED"


# ─────────────────────────────────────────────────────────────
# Constraint coverage checklist
# ─────────────────────────────────────────────────────────────
STRUCTURAL_CONSTRAINTS = [
    "geographic",   # mobilité, région, ville
    "financial",    # budget, alternance, bourse
    "academic",     # niveau, prérequis, dossier
    "temporal",     # durée d'études acceptable
    "personal",     # rythme, présentiel/distanciel, équilibre
]


def _empty_state() -> dict:
    return {
        "phase": Phase.CADRAGE,
        "strategy": Strategy.UNDETERMINED,
        "confirmed": {},
        "inferred": {},
        "missing": {},
        "constraints_covered": {c: False for c in STRUCTURAL_CONSTRAINTS},
        "hard_filters": [],
        "options_pool": [],
        "options_eliminated": [],
        "shortlist": [],
        "turn_count": 0,
        "turn_log": [],
    }


# ─────────────────────────────────────────────────────────────
# What's missing at each phase
# ─────────────────────────────────────────────────────────────

CADRAGE_FIELDS = {
    "filiere": {"priority": "HIGH", "reason": "Filière actuelle ou visée inconnue"},
    "ambition": {"priority": "HIGH", "reason": "Ambition non formulée"},
    "etape": {"priority": "HIGH", "reason": "Étape de recherche inconnue"},
    "interests": {"priority": "MEDIUM", "reason": "Centres d'intérêt non recueillis"},
}

CONSTRAINT_QUESTIONS = {
    "geographic": {
        "field": "region",
        "question_hint": "Demande la zone géographique souhaitée (région, ville, ou mobilité totale).",
        "priority": "HIGH",
    },
    "financial": {
        "field": "budget",
        "question_hint": "Demande le budget max annuel, et si l'alternance ou les bourses sont envisagées.",
        "priority": "HIGH",
    },
    "academic": {
        "field": "academic_level",
        "question_hint": "Demande le niveau scolaire approximatif (mention au bac, notes moyennes, spécialités).",
        "priority": "HIGH",
    },
    "temporal": {
        "field": "study_duration",
        "question_hint": "Demande la durée d'études acceptable (bac+2, bac+3, bac+5 ?).",
        "priority": "MEDIUM",
    },
    "personal": {
        "field": "personal_prefs",
        "question_hint": "Demande les préférences de rythme (présentiel/distanciel/hybride, ville/campus).",
        "priority": "LOW",
    },
}




class DecisionEngine:
    """Deterministic decision state machine for orientation guidance."""

    def __init__(self):
        self._states: dict[str, dict] = {}

    def get_state(self, session_id: str) -> dict:
        if session_id not in self._states:
            self._states[session_id] = _empty_state()
        return self._states[session_id]

    def get_audit_snapshot(self, session_id: str) -> dict:
        """Return a serializable snapshot for the API response."""
        s = self.get_state(session_id)
        missing_count = len([v for v in s["missing"].values() if v.get("priority") == "HIGH"])
        covered = sum(1 for v in s["constraints_covered"].values() if v)
        total = len(STRUCTURAL_CONSTRAINTS)
        progress = 0
        if s["phase"] == Phase.CADRAGE:
            progress = 10
        elif s["phase"] == Phase.AFFINEMENT:
            progress = 25 + int(15 * covered / max(total, 1))
        elif s["phase"] == Phase.RESSERREMENT:
            progress = 50 + int(30 * covered / max(total, 1))
        elif s["phase"] == Phase.DECISION:
            progress = 90 if not s["shortlist"] else 100

        return {
            "phase": s["phase"],
            "strategy": s["strategy"],
            "missing_count": missing_count,
            "constraints_covered": s["constraints_covered"],
            "progress_pct": min(progress, 100),
            "turn_count": s["turn_count"],
            "shortlist_count": len(s["shortlist"]),
            "next_action": self._next_action_label(s),
            "suggested_replies": self.get_suggested_replies(session_id),
        }

    def get_suggested_replies(self, session_id: str) -> list:
        """Return dynamically generated suggested replies from the LLM extraction."""
        s = self.get_state(session_id)
        return s.get("suggested_replies", [])

    # ─────────────────────────────────────────────────────────
    # Core: process onboarding completion
    # ─────────────────────────────────────────────────────────

    def process_onboarding(self, session_id: str, profile: dict, persona: str):
        """Called when onboarding finishes. Produces the canonical triplet and sets strategy."""
        s = self.get_state(session_id)

        # Extract canonical triplet
        filiere = profile.get("track", profile.get("child_level", ""))
        ambition = self._infer_ambition(profile)
        etape = self._map_etape(profile.get("stage", ""))

        s["confirmed"]["filiere"] = filiere or "Non précisé"
        s["confirmed"]["ambition"] = ambition
        s["confirmed"]["etape"] = etape
        s["confirmed"]["persona"] = persona
        s["confirmed"]["interests"] = profile.get("interests", [])
        s["confirmed"]["level"] = profile.get("level", profile.get("child_level", ""))

        # Set strategy from etape
        s["strategy"] = self._etape_to_strategy(etape)

        # Infer what we can from constraints
        constraints = profile.get("constraints", [])
        if isinstance(constraints, str):
            constraints = [constraints]
        for c in constraints:
            cl = c.lower()
            if "près" in cl or "proximité" in cl or "géograph" in cl:
                s["inferred"]["mobilite_limitee"] = True
            if "budget" in cl or "bourse" in cl or "gratuit" in cl:
                s["inferred"]["budget_sensible"] = True
            if "alternance" in cl:
                s["inferred"]["alternance_souhaitee"] = True
                s["confirmed"]["alternance"] = True
            if "étranger" in cl or "international" in cl:
                s["inferred"]["international_souhaite"] = True

        # Build initial missing list
        s["missing"] = {}
        if s["inferred"].get("mobilite_limitee") and "region" not in s["confirmed"]:
            s["missing"]["region"] = {"priority": "HIGH", "reason": "Contrainte géo déclarée, zone non précisée"}
        if s["inferred"].get("budget_sensible") and "budget" not in s["confirmed"]:
            s["missing"]["budget"] = {"priority": "MEDIUM", "reason": "Sensibilité budget détectée, montant inconnu"}

        # Transition to AFFINEMENT
        s["phase"] = Phase.AFFINEMENT
        self._log_turn(s, "onboarding_complete", f"Triplet: filiere={filiere}, ambition={ambition}, etape={etape}, strategy={s['strategy']}")

    # ─────────────────────────────────────────────────────────
    # Core: generate instructions for GPT-4o
    # ─────────────────────────────────────────────────────────

    def generate_agent_instructions(self, session_id: str, user_message: str) -> str:
        """Generate precise, deterministic instructions for the LLM based on current state."""
        s = self.get_state(session_id)
        s["turn_count"] += 1

        persona = s["confirmed"].get("persona", "lyceen")
        tone = "Tutoiement, chaleureux" if persona in ("lyceen", "collegien") else "Vouvoiement, professionnel"

        phase = s["phase"]

        if phase == Phase.AFFINEMENT:
            return self._instructions_affinement(s, user_message, tone)
        elif phase == Phase.RESSERREMENT:
            return self._instructions_resserrement(s, user_message, tone)
        elif phase == Phase.DECISION:
            return self._instructions_decision(s, user_message, tone)
        else:
            return self._instructions_cadrage(s, user_message, tone)

    # ─────────────────────────────────────────────────────────
    # Core: update state after LLM response
    # ─────────────────────────────────────────────────────────

    def update_state_from_extraction(self, session_id: str, extraction: dict):
        """Update decision state from structured info extracted by GPT-4o."""
        s = self.get_state(session_id)

        # Merge confirmed fields
        for key, val in extraction.get("confirmed", {}).items():
            if val and val != "?" and val != "null":
                s["confirmed"][key] = val
                s["missing"].pop(key, None)

        # Merge inferred fields
        for key, val in extraction.get("inferred", {}).items():
            if val is not None:
                s["inferred"][key] = val

        # Hard filters
        for hf in extraction.get("hard_filters", []):
            if hf and hf not in s["hard_filters"]:
                s["hard_filters"].append(hf)

        # Options mentioned
        for opt in extraction.get("options_mentioned", []):
            if opt and opt not in s["options_pool"]:
                s["options_pool"].append(opt)

        # Update constraint coverage
        self._update_constraint_coverage(s)

        # Suggested replies generated by LLM
        s["suggested_replies"] = extraction.get("suggested_replies", [])

        # Check phase transitions
        self._check_transitions(s)

        self._log_turn(s, "state_update", json.dumps(extraction, ensure_ascii=False)[:200])

    # ─────────────────────────────────────────────────────────
    # Phase-specific instruction generators
    # ─────────────────────────────────────────────────────────

    def _instructions_affinement(self, s: dict, user_msg: str, tone: str) -> str:
        strategy = s["strategy"]
        confirmed = json.dumps(s["confirmed"], ensure_ascii=False)
        inferred = json.dumps(s["inferred"], ensure_ascii=False)

        # Find highest priority missing field
        next_q = self._highest_priority_missing(s)

        base = (
            f"PHASE: AFFINEMENT\n"
            f"STRATÉGIE: {strategy}\n"
            f"TON: {tone}\n"
            f"CONFIRMÉ: {confirmed}\n"
            f"INFÉRÉ: {inferred}\n"
            f"MESSAGE UTILISATEUR: {user_msg}\n\n"
        )

        if strategy == Strategy.PROJET_PRECIS:
            base += (
                "MODE: STRESS-TEST. L'utilisateur a un projet précis.\n"
                "OBJECTIF: Valider ou challenger cette décision.\n"
                "ACTIONS:\n"
                "1. Réponds à sa question en utilisant l'outil query_letudiant_database si tu as besoin de faits.\n"
                "2. Vérifie la cohérence entre son ambition et sa situation (niveau, filière, contraintes).\n"
                "3. Si incohérence détectée, signale-la avec bienveillance.\n"
            )
        elif strategy == Strategy.HESITATION:
            base += (
                "MODE: DIFFÉRENCIATION. L'utilisateur hésite entre options.\n"
                "OBJECTIF: Faire émerger les critères de choix et comparer méthodiquement.\n"
                "ACTIONS:\n"
                "1. Réponds à sa question en utilisant l'outil pour chercher des faits concrets.\n"
                "2. Identifie les critères de différenciation (coût, prestige, débouchés, proximité...).\n"
                "3. Compare les options mentionnées sur ces critères.\n"
            )
        elif strategy == Strategy.EXPLORATION_OUVERTE:
            base += (
                "MODE: ÉCOUTE ACTIVE. L'utilisateur ne sait pas encore.\n"
                "OBJECTIF: Identifier intérêts, valeurs, et réduire le champ des possibles.\n"
                "ACTIONS:\n"
                "1. Écoute et reformule ce que l'utilisateur exprime.\n"
                "2. Pose UNE question ouverte pour explorer ses motivations.\n"
                "3. Si suffisamment d'info, propose 2-3 familles de formations à explorer.\n"
            )
        else:
            base += (
                "MODE: RÉORIENTATION. L'utilisateur veut changer de voie.\n"
                "OBJECTIF: Comprendre ce qui ne va pas et identifier les passerelles.\n"
            )

        if next_q:
            base += f"\nINFO MANQUANTE PRIORITAIRE: {next_q['field']} — {next_q['hint']}\nIntègre cette question naturellement dans ta réponse.\n"

        base += (
            "\nRÈGLES:\n"
            "- NE RÉPÈTE PAS les informations du profil ou l'historique. Sois direct, factuel et concis.\n"
            "- Chaque réponse DOIT faire avancer l'état (résoudre une incertitude ou en poser une nouvelle).\n"
            "- Tu peux proposer 1 ou 2 exemples concrets de formations pour illustrer et éviter que l'échange soit trop théorique.\n"
            "- Si l'utilisateur mentionne un critère hors-modèle (conviction, religion, famille), respecte-le comme filtre dur.\n"
            "- Distingue ce que l'utilisateur a dit (fait) de ce que tu infères (hypothèse), et signale l'inférence.\n"
            "- Termine par UNE question précise qui fait avancer vers la décision.\n"
        )
        return base

    def _instructions_resserrement(self, s: dict, user_msg: str, tone: str) -> str:
        confirmed = json.dumps(s["confirmed"], ensure_ascii=False)
        constraints = json.dumps(s["constraints_covered"], ensure_ascii=False)
        uncovered = [c for c, v in s["constraints_covered"].items() if not v]

        next_constraint = None
        if uncovered:
            cname = uncovered[0]
            cdata = CONSTRAINT_QUESTIONS.get(cname, {})
            next_constraint = cdata.get("question_hint", f"Explorer la contrainte '{cname}'")

        return (
            f"PHASE: RESSERREMENT\n"
            f"TON: {tone}\n"
            f"CONFIRMÉ: {confirmed}\n"
            f"CONTRAINTES COUVERTES: {constraints}\n"
            f"OPTIONS EN JEU: {json.dumps(s['options_pool'], ensure_ascii=False)}\n"
            f"MESSAGE UTILISATEUR: {user_msg}\n\n"
            f"OBJECTIF: Couvrir toutes les contraintes structurantes avant de recommander.\n"
            f"CONTRAINTES NON COUVERTES: {', '.join(uncovered)}\n"
            f"{'PROCHAINE QUESTION: ' + next_constraint if next_constraint else 'Toutes couvertes → prépare la transition vers DECISION.'}\n\n"
            f"RÈGLES:\n"
            f"- NE RÉPÈTE PAS les informations du profil ou l'historique. Sois direct, factuel et concis.\n"
            f"- Réponds à la question de l'utilisateur (utilise l'outil RAG si nécessaire).\n"
            f"- Intègre la question sur la contrainte manquante dans ta réponse, mais de façon naturelle.\n"
            f"- Donne des exemples concrets d'écoles ou de formations pour aider l'utilisateur à se projeter.\n"
            f"- Chaque tour doit couvrir AU MOINS une contrainte.\n"
        )

    def _instructions_decision(self, s: dict, user_msg: str, tone: str) -> str:
        confirmed = json.dumps(s["confirmed"], ensure_ascii=False)
        options = json.dumps(s["options_pool"], ensure_ascii=False)
        hard_filters = json.dumps(s["hard_filters"], ensure_ascii=False)

        return (
            f"PHASE: DECISION\n"
            f"TON: {tone}\n"
            f"PROFIL COMPLET: {confirmed}\n"
            f"OPTIONS EN JEU: {options}\n"
            f"FILTRES DURS: {hard_filters}\n"
            f"MESSAGE UTILISATEUR: {user_msg}\n\n"
            f"OBJECTIF: Émettre une recommandation finale.\n"
            f"RÈGLE: NE RÉPÈTE PAS les informations du profil ou l'historique. Sois direct, factuel et concis.\n"
            f"FORMAT OBLIGATOIRE:\n"
            f"- Si UNE option domine → Recommandation unique avec justification point par point + risques.\n"
            f"- Si pas de dominance claire → Shortlist de 2 à 3 maximum, chacune avec son profil distinctif.\n"
            f"- JAMAIS plus de 3 options. Au-delà, le resserrement a échoué.\n\n"
            f"POUR CHAQUE OPTION:\n"
            f"- Pourquoi elle correspond (critères confirmés)\n"
            f"- Ce qui la distingue des autres\n"
            f"- Risques identifiés / angles morts\n"
            f"- Lien L'Étudiant (utilise l'outil pour trouver l'URL exacte)\n\n"
            f"UTILISE l'outil query_letudiant_database pour vérifier les faits sur chaque option recommandée.\n"
        )

    def _instructions_cadrage(self, s: dict, user_msg: str, tone: str) -> str:
        return (
            f"PHASE: CADRAGE\n"
            f"TON: {tone}\n"
            f"MESSAGE: {user_msg}\n"
            f"OBJECTIF: Recueillir filière, ambition, et étape de recherche.\n"
            f"Pose une question pour identifier ces éléments.\n"
        )

    # ─────────────────────────────────────────────────────────
    # Transition logic
    # ─────────────────────────────────────────────────────────

    def _check_transitions(self, s: dict):
        """Check if we should transition to the next phase."""
        phase = s["phase"]

        if phase == Phase.AFFINEMENT:
            # Transition to RESSERREMENT when we have enough info to start narrowing
            has_options = len(s["options_pool"]) >= 1
            has_direction = bool(s["confirmed"].get("ambition")) and s["confirmed"]["ambition"] != "À DÉFINIR"
            high_missing = [k for k, v in s["missing"].items() if v.get("priority") == "HIGH"]

            if (has_options or has_direction) and len(high_missing) == 0:
                s["phase"] = Phase.RESSERREMENT
                self._log_turn(s, "phase_transition", "AFFINEMENT → RESSERREMENT")

        elif phase == Phase.RESSERREMENT:
            # Transition to DECISION when all high priority constraints are covered or we've had enough turns
            uncovered = [c for c, v in s["constraints_covered"].items() if not v]
            high_missing = [c for c in uncovered if CONSTRAINT_QUESTIONS.get(c, {}).get("priority") == "HIGH"]
            
            if len(high_missing) == 0 or s["turn_count"] >= 5:
                s["phase"] = Phase.DECISION
                self._log_turn(s, "phase_transition", "RESSERREMENT → DECISION")

    def _update_constraint_coverage(self, s: dict):
        """Update which structural constraints are covered based on confirmed data."""
        c = s["confirmed"]
        i = s["inferred"]

        # Geographic
        if c.get("region") or c.get("city") or c.get("mobilite") == "totale":
            s["constraints_covered"]["geographic"] = True

        # Financial
        if c.get("budget") or c.get("alternance") or c.get("financial_detail"):
            s["constraints_covered"]["financial"] = True

        # Academic
        if c.get("academic_level") or c.get("mention") or c.get("notes"):
            s["constraints_covered"]["academic"] = True

        # Temporal
        if c.get("study_duration") or c.get("target_degree"):
            s["constraints_covered"]["temporal"] = True

        # Personal
        if c.get("personal_prefs") or c.get("rythme") or c.get("presentiel"):
            s["constraints_covered"]["personal"] = True

    # ─────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────

    def _infer_ambition(self, profile: dict) -> str:
        stage = profile.get("stage", "")
        interests = profile.get("interests", [])
        if "🎯" in stage or "précis" in stage.lower():
            # Try to infer from interests
            if any("ingénieur" in i.lower() or "tech" in i.lower() or "info" in i.lower() for i in interests):
                return "École d'ingénieur / filière scientifique"
            elif any("commerce" in i.lower() or "management" in i.lower() for i in interests):
                return "École de commerce / management"
            elif any("santé" in i.lower() for i in interests):
                return "Études de santé"
            elif any("droit" in i.lower() or "politique" in i.lower() for i in interests):
                return "Droit / Sciences politiques"
            elif any("art" in i.lower() or "design" in i.lower() for i in interests):
                return "Arts / Design"
            return "Projet précis (à clarifier)"
        return "À DÉFINIR"

    def _map_etape(self, stage: str) -> str:
        sl = stage.lower()
        if "précis" in sl or "🎯" in sl:
            return "PROJET_PRECIS"
        elif "hésite" in sl or "⚖" in sl or "plusieurs" in sl:
            return "HESITATION"
        elif "explore" in sl or "🔍" in sl or "pistes" in sl:
            return "EXPLORATION_OUVERTE"
        elif "aucune" in sl or "🌊" in sl or "pas" in sl:
            return "EXPLORATION_OUVERTE"
        return "EXPLORATION_OUVERTE"

    def _etape_to_strategy(self, etape: str) -> Strategy:
        mapping = {
            "PROJET_PRECIS": Strategy.PROJET_PRECIS,
            "HESITATION": Strategy.HESITATION,
            "EXPLORATION_OUVERTE": Strategy.EXPLORATION_OUVERTE,
        }
        return mapping.get(etape, Strategy.EXPLORATION_OUVERTE)

    def _highest_priority_missing(self, s: dict) -> Optional[dict]:
        """Return the highest-priority missing field."""
        high = [(k, v) for k, v in s["missing"].items() if v.get("priority") == "HIGH"]
        if high:
            k, v = high[0]
            return {"field": k, "hint": v.get("reason", ""), "priority": "HIGH"}

        # In RESSERREMENT, check uncovered constraints
        if s["phase"] in (Phase.AFFINEMENT, Phase.RESSERREMENT):
            for cname, covered in s["constraints_covered"].items():
                if not covered:
                    cdata = CONSTRAINT_QUESTIONS.get(cname, {})
                    return {"field": cdata.get("field", cname), "hint": cdata.get("question_hint", ""), "priority": "MEDIUM"}
        return None

    def _next_action_label(self, s: dict) -> str:
        nxt = self._highest_priority_missing(s)
        if nxt:
            return f"ask_{nxt['field']}"
        if s["phase"] == Phase.DECISION:
            return "emit_recommendation"
        return "continue_conversation"

    def _log_turn(self, s: dict, action: str, detail: str):
        s["turn_log"].append({
            "turn": s["turn_count"],
            "phase": s["phase"],
            "action": action,
            "detail": detail[:300],
            "timestamp": time.time(),
        })
