"""
Response Enhancer — GPT-4o intelligence layer for ORI Extended.

Dual-LLM strategy:
  • ORI Reasoning Engine (Vertex AI) = Knowledge brain (L'Étudiant RAG data)
  • GPT-4o = Communication brain (guidance, formatting, follow-ups, enrichment)

GPT-4o never invents L'Étudiant-specific data. It uses the RAG output as ground
truth and can supplement with general knowledge (clearly sourced).
"""

import os
import json
import logging
from typing import Optional
from openai import OpenAI

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# System prompt — the heart of ORI's guided personality
# ─────────────────────────────────────────────────────────────

ORCHESTRATOR_SYSTEM = """Tu es ORI, le compagnon d'orientation intelligent de L'Étudiant — le magazine de référence pour les jeunes en France.

## Ton rôle
Tu GUIDES l'utilisateur dans sa réflexion d'orientation. Tu ne te contentes pas de répondre aux questions : tu structures un parcours de découverte, tu poses des questions de suivi pertinentes, et tu proposes proactivement les étapes suivantes.

## Règles absolues
1. **Guide, ne prescris pas** — Tu ne dis JAMAIS "tu dois choisir X". Tu présentes des options, des critères, et tu aides à peser.
2. **Source tout** — Quand tu cites des données L'Étudiant (du contexte RAG), dis "selon L'Étudiant". Quand tu ajoutes des infos générales, dis "d'après les données publiques" ou cite ta source.
3. **Partenaires transparents** — Si tu mentionnes un partenaire L'Étudiant, marque-le avec 📌 SANS dire qu'il est mieux classé.
4. **Termine TOUJOURS par une relance** — Chaque réponse doit se terminer par une question ou suggestion de prochaine étape.
5. **Sois concis et structuré** — Utilise des émojis, du gras (**...**), des listes. Pas de paragraphes-fleuve.

## Ton style selon le persona
- **Lycéen·ne** : Tutoiement, ton chaleureux et encourageant, émojis fréquents
- **Collégien·ne** : Tutoiement, langage simple et ludique, rassure beaucoup
- **Parent** : Vouvoiement, ton professionnel et rassurant, données factuelles
- **Enseignant·e** : Vouvoiement, ton expert et collaboratif, statistiques

## Flow de guidance
Après chaque réponse, tu dois proposer UNE action concrète parmi :
- Explorer un sujet connexe ("On peut aussi regarder les aides financières pour cette formation 💰")
- Approfondir ("Veux-tu que je te détaille les spécialités de cette école ?")
- Comparer ("Tu hésites entre deux options ? Je peux faire une comparaison détaillée ⚖️")
- Passer à l'action ("Tu as l'air convaincu·e ! Veux-tu voir les étapes de candidature sur Parcoursup ? 📋")

## Contexte enrichi
Tu as accès à :
- Les données RAG de L'Étudiant (fournies dans le message)
- Le profil complet de l'utilisateur (persona, niveau, intérêts, contraintes)
- L'historique de conversation (ce qui a déjà été exploré)
Tu peux aussi utiliser tes connaissances générales pour compléter (ex: infos sur un métier, tendances du marché du travail) mais tu DOIS signaler quand une info ne vient pas de L'Étudiant.
"""

PROFILE_DEEPENING_PROMPTS = {
    "📍 Rester près de chez moi": "Tu as mentionné vouloir rester près de chez toi — dans quelle ville ou région habites-tu ? Ça m'aidera à te proposer des formations proches 📍",
    "💰 Budget limité / besoin de bourse": "Tu as un budget limité — est-ce que tu cherches uniquement des formations publiques gratuites, ou l'alternance (qui te rémunère) pourrait aussi t'intéresser ? 💰",
    "🌍 Envie de partir à l'étranger": "Tu aimerais partir à l'étranger — tu penses à un pays en particulier, ou plutôt un échange pendant tes études en France ? 🌍",
    "📍 Proximité géographique": "Vous avez mentionné la proximité géographique — dans quelle région cherchez-vous des formations pour votre enfant ? 📍",
    "💰 Formation gratuite / publique": "Vous privilégiez les formations publiques — saviez-vous que certaines grandes écoles ont des frais très réduits selon les revenus ? Je peux vous détailler les aides disponibles 💰",
}


class ResponseEnhancer:
    """GPT-4o-powered response quality and guidance layer."""

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY", "")
        self._available = False
        self._client = None

        if api_key and not api_key.startswith("sk-PASTE"):
            try:
                self._client = OpenAI(api_key=api_key)
                # Quick test
                self._client.models.list()
                self._available = True
                logger.info("GPT-4o Response Enhancer: ACTIVE ✅")
            except Exception as e:
                logger.warning(f"OpenAI unavailable: {e}. Using passthrough mode.")
        else:
            logger.info("GPT-4o Response Enhancer: No API key. Using passthrough mode.")

    @property
    def is_available(self) -> bool:
        return self._available

    async def enhance_response(
        self,
        raw_ori_response: str,
        user_message: str,
        profile_context: str,
        conversation_summary: str,
        persona: str,
        guidance_hint: str = "",
    ) -> str:
        """
        Take raw ORI RAG output and transform it into a guided, structured response.
        
        Args:
            raw_ori_response: The raw text from ORI Reasoning Engine
            user_message: What the user asked
            profile_context: Natural-language profile summary
            conversation_summary: What has been discussed so far
            persona: lyceen/collegien/parent/enseignant
            guidance_hint: Optional hint for what to guide towards
        """
        if not self._available:
            return raw_ori_response

        try:
            messages = [
                {"role": "system", "content": ORCHESTRATOR_SYSTEM},
                {"role": "user", "content": self._build_enhancement_prompt(
                    raw_ori_response, user_message, profile_context,
                    conversation_summary, persona, guidance_hint
                )},
            ]

            response = self._client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.7,
                max_tokens=1000,
            )

            enhanced = response.choices[0].message.content
            return enhanced.strip() if enhanced else raw_ori_response

        except Exception as e:
            logger.error(f"GPT-4o enhancement failed: {e}")
            return raw_ori_response

    async def generate_guided_welcome(
        self,
        profile: dict,
        persona: str,
        pending_deepening: list,
    ) -> str:
        """Generate a proactive first message after onboarding."""
        if not self._available:
            return self._fallback_welcome(profile, persona, pending_deepening)

        try:
            prompt = (
                f"L'utilisateur vient de terminer son onboarding. Voici son profil :\n\n"
                f"{json.dumps(profile, ensure_ascii=False, indent=2)}\n\n"
                f"Persona : {persona}\n\n"
            )

            if pending_deepening:
                prompt += (
                    f"Questions de suivi à poser (car les réponses d'onboarding étaient vagues) :\n"
                    + "\n".join(f"- {q}" for q in pending_deepening) + "\n\n"
                )

            prompt += (
                "Génère un message d'accueil chaleureux qui :\n"
                "1. Résume ce que tu as compris du profil (2-3 lignes, pas de répétition mot-à-mot)\n"
                "2. Pose LA question de suivi la plus importante\n"
                "3. Propose 1-2 pistes concrètes d'exploration basées sur le profil\n"
                "Format : structuré avec émojis et gras. Court (max 150 mots)."
            )

            messages = [
                {"role": "system", "content": ORCHESTRATOR_SYSTEM},
                {"role": "user", "content": prompt},
            ]

            response = self._client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.8,
                max_tokens=500,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"GPT-4o welcome generation failed: {e}")
            return self._fallback_welcome(profile, persona, pending_deepening)

    async def generate_dynamic_comparison(
        self,
        ori_responses: list,
        options: list,
        profile_context: str,
        persona: str,
    ) -> dict:
        """Use GPT-4o to structure a comparison from ORI RAG data."""
        if not self._available:
            return None

        try:
            prompt = (
                f"Tu dois créer une comparaison structurée entre ces formations : {', '.join(options)}.\n\n"
                f"Voici les données RAG de L'Étudiant pour chaque option :\n\n"
            )
            for i, (opt, resp) in enumerate(zip(options, ori_responses)):
                prompt += f"--- {opt} ---\n{resp}\n\n"

            prompt += (
                f"Profil de l'utilisateur : {profile_context}\n\n"
                "Crée un JSON avec cette structure EXACTE :\n"
                '{\n'
                '  "options": ["Nom complet 1", "Nom complet 2"],\n'
                '  "criteria": [\n'
                '    {"name": "Type de formation", "values": {"Option1": "...", "Option2": "..."}, "best_for_profile": "Option1 ou Option2 ou null"},\n'
                '    ... (inclure: Sélectivité, Localisation, Coût annuel, Spécialités, Débouchés, International, Vie étudiante)\n'
                '  ],\n'
                '  "recommendation": {"choice": "...", "reason": "Explication en 2 phrases basée sur le profil"},\n'
                '  "traffic_links": [{"label": "...", "url": "https://www.letudiant.fr/..."}]\n'
                '}\n\n'
                "IMPORTANT : utilise UNIQUEMENT des URLs letudiant.fr vérifiées. "
                "Si tu ne connais pas l'URL exacte, utilise le format de recherche : "
                "https://www.letudiant.fr/etudes/annuaire-enseignement-superieur/etablissement/\n"
                "Réponds UNIQUEMENT avec le JSON, rien d'autre."
            )

            messages = [
                {"role": "system", "content": "Tu es un assistant qui génère des comparaisons structurées en JSON."},
                {"role": "user", "content": prompt},
            ]

            response = self._client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.3,
                max_tokens=1500,
            )

            raw = response.choices[0].message.content.strip()
            # Extract JSON from potential markdown code block
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            return json.loads(raw)

        except Exception as e:
            logger.error(f"GPT-4o comparison failed: {e}")
            return None

    def _build_enhancement_prompt(
        self, raw_response, user_message, profile_context,
        conversation_summary, persona, guidance_hint
    ) -> str:
        return (
            f"## Contexte\n"
            f"**Persona** : {persona}\n"
            f"**Profil utilisateur** : {profile_context}\n"
            f"**Historique** : {conversation_summary}\n\n"
            f"## Question de l'utilisateur\n{user_message}\n\n"
            f"## Données RAG L'Étudiant\n{raw_response}\n\n"
            f"{'## Suggestion de guidance : ' + guidance_hint if guidance_hint else ''}\n\n"
            f"## Consigne\n"
            f"Reformule la réponse RAG en un message structuré, chaleureux et guidé. "
            f"Tu peux enrichir avec des informations complémentaires (marque-les comme 'info complémentaire'). "
            f"Garde les liens L'Étudiant du RAG. "
            f"Termine par une question de suivi ou suggestion de prochaine étape.\n"
            f"Format : émojis, gras, listes courtes. Max 200 mots."
        )

    def _fallback_welcome(self, profile, persona, pending_deepening):
        """Fallback welcome when GPT-4o is unavailable."""
        interests = profile.get("interests", [])
        interests_str = ", ".join(interests[:3]) if interests else "explorer"

        if persona == "lyceen":
            msg = (
                f"Merci ! Voilà ce que j'ai compris :\n\n"
                f"📚 **Niveau** : {profile.get('level', '?')}\n"
                f"💡 **Intérêts** : {interests_str}\n"
                f"🧭 **Étape** : {profile.get('stage', '?')}\n\n"
            )
            if pending_deepening:
                msg += pending_deepening[0] + "\n\n"
            msg += "Pose-moi n'importe quelle question sur l'orientation, la vie étudiante, le logement, les bourses… 🚀"
            return msg

        return f"Merci pour ces informations ! Je suis prêt à vous aider. {pending_deepening[0] if pending_deepening else 'Posez-moi vos questions !'}"

    def get_deepening_questions(self, profile: dict, persona: str) -> list:
        """Identify which onboarding answers need follow-up deepening."""
        questions = []
        constraints = profile.get("constraints", [])
        if isinstance(constraints, str):
            constraints = [constraints]

        for constraint in constraints:
            if constraint in PROFILE_DEEPENING_PROMPTS:
                questions.append(PROFILE_DEEPENING_PROMPTS[constraint])

        concern = profile.get("concern", "")
        if concern in PROFILE_DEEPENING_PROMPTS:
            questions.append(PROFILE_DEEPENING_PROMPTS[concern])

        return questions[:2]  # Max 2 follow-ups
