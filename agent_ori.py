"""
Agent ORI v3 — OpenAI Assistants API + Decision Engine integration.
The Agent no longer decides what to ask. It receives precise instructions
from the DecisionEngine and executes them.
"""

import os
import json
import time
import logging
from typing import Optional
from openai import OpenAI

from prompts import ORCHESTRATOR_SYSTEM

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Analyse le dernier échange (message utilisateur + réponse ORI) et extrais les informations structurées.

MESSAGE UTILISATEUR: {user_message}
RÉPONSE ORI: {ori_response}

Retourne un JSON avec EXACTEMENT cette structure (laisse les champs vides si non applicable):
{{
  "confirmed": {{
    "region": null,
    "city": null,
    "budget": null,
    "alternance": null,
    "academic_level": null,
    "mention": null,
    "study_duration": null,
    "target_degree": null,
    "personal_prefs": null,
    "rythme": null,
    "presentiel": null,
    "mobilite": null,
    "financial_detail": null,
    "notes": null,
    "ambition": null
  }},
  "inferred": {{}},
  "hard_filters": [],
  "options_mentioned": [],
  "suggested_replies": []
}}

RÈGLES:
- "confirmed" = ce que l'utilisateur a EXPLICITEMENT dit. Ne mets une valeur que si l'utilisateur l'a clairement exprimé.
- "inferred" = ce que tu déduis (ex: "je veux un bon salaire" → {{"ambition_financiere": true}}).
- "hard_filters" = critères non-négociables (religion, famille, conviction).
- "options_mentioned" = noms d'écoles ou formations mentionnées par l'utilisateur.
- "suggested_replies" = Si la réponse ORI pose une question à l'utilisateur, génère EXACTEMENT 3 options de réponse très pertinentes.
  * "label" : Titre court du bouton (1 à 3 mots max + un émoji). Ex: "🔬 Recherche scientifique".
  * "value" : Le message EXACT qui sera envoyé au bot. DOIT être UNE phrase complète, robuste, factuelle, précise et parfaitement cohérente avec le label. Pas de sentimentalisme, pas de réponse en 1 mot déconnectée. Ex: "Je suis intéressé par les parcours universitaires orientés vers la recherche scientifique."
  Ajoute TOUJOURS {{"label": "✍️ Préciser...", "value": ""}} comme 4ème option.
- Retourne UNIQUEMENT le JSON, rien d'autre.
"""


class AgentORI:
    def __init__(self, ori_client):
        self._ori_client = ori_client
        self._available = False
        self._client = None
        self._assistant_id = None

        api_key = os.getenv("OPENAI_API_KEY", "")
        if api_key and not api_key.startswith("sk-PASTE"):
            try:
                self._client = OpenAI(api_key=api_key)
                self._init_assistant()
                self._available = True
                logger.info("Agent ORI v3 (Assistants API): ACTIVE ✅")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI Assistant: {e}")
        else:
            logger.warning("Agent ORI: No valid OpenAI API key. Agent disabled.")

    @property
    def is_available(self) -> bool:
        return self._available

    def _init_assistant(self):
        assistants = self._client.beta.assistants.list(limit=50)
        for asst in assistants.data:
            if asst.name == "ORI Companion Agent v3":
                self._assistant_id = asst.id
                self._client.beta.assistants.update(
                    assistant_id=self._assistant_id,
                    instructions=ORCHESTRATOR_SYSTEM,
                    tools=[self._get_tool_schema()]
                )
                logger.info(f"Using existing Assistant v3: {self._assistant_id}")
                return

        assistant = self._client.beta.assistants.create(
            name="ORI Companion Agent v3",
            instructions=ORCHESTRATOR_SYSTEM,
            model="gpt-4o",
            tools=[self._get_tool_schema()]
        )
        self._assistant_id = assistant.id
        logger.info(f"Created Assistant v3: {self._assistant_id}")

    def _get_tool_schema(self):
        return {
            "type": "function",
            "function": {
                "name": "query_letudiant_database",
                "description": "Recherche dans la base de données éditoriale L'Étudiant. Utilisez cet outil pour des faits sur des écoles, classements, logement, bourses, Parcoursup.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "La question précise à poser à la base de données."
                        }
                    },
                    "required": ["query"]
                }
            }
        }

    def create_thread(self) -> str:
        if not self._available:
            return ""
        thread = self._client.beta.threads.create()
        return thread.id

    async def chat(
        self,
        thread_id: str,
        user_message: str,
        engine_instructions: str,
        persona: str,
    ) -> dict:
        """
        Send message to the Agent with Decision Engine instructions.
        The Agent follows the instructions precisely.
        """
        if not self._available:
            return {"response": "Agent indisponible.", "source": "error"}

        # Build the contextual message with engine instructions
        contextual_msg = (
            f"[INSTRUCTIONS DU MOTEUR DE DÉCISION — SUIS-LES PRÉCISÉMENT]\n"
            f"{engine_instructions}\n"
            f"[FIN DES INSTRUCTIONS]\n\n"
            f"{user_message}"
        )

        self._client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=contextual_msg
        )

        run = self._client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=self._assistant_id,
            instructions=f"Persona: {persona}. Suis les INSTRUCTIONS DU MOTEUR DE DÉCISION dans le message."
        )

        source_used = "agent_no_tools"
        max_iterations = 30
        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            run_status = self._client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)

            if run_status.status == 'completed':
                break
            elif run_status.status == 'requires_action':
                tool_calls = run_status.required_action.submit_tool_outputs.tool_calls
                tool_outputs = []
                for tool_call in tool_calls:
                    if tool_call.function.name == "query_letudiant_database":
                        args = json.loads(tool_call.function.arguments)
                        query = args.get("query", "")
                        logger.info(f"Agent Tool Call: query_letudiant_database('{query[:80]}')")
                        rag_result = await self._ori_client.query(
                            message=query, thread_id=thread_id, profile=None
                        )
                        tool_outputs.append({
                            "tool_call_id": tool_call.id,
                            "output": rag_result["response"]
                        })
                        source_used = "agent_with_rag"
                self._client.beta.threads.runs.submit_tool_outputs(
                    thread_id=thread_id, run_id=run.id, tool_outputs=tool_outputs
                )
            elif run_status.status in ['failed', 'cancelled', 'expired']:
                logger.error(f"Run failed: {run_status.last_error}")
                return {"response": "Désolé, un problème technique est survenu. Reformule ta question ?", "source": "error"}
            time.sleep(1)

        messages = self._client.beta.threads.messages.list(thread_id=thread_id)
        final_message = messages.data[0].content[0].text.value

        return {"response": final_message, "source": source_used}

    async def extract_structured_info(self, user_message: str, ori_response: str) -> dict:
        """Use GPT-4o to extract structured information from the exchange."""
        if not self._available:
            return {"confirmed": {}, "inferred": {}, "hard_filters": [], "options_mentioned": []}
        try:
            prompt = EXTRACTION_PROMPT.format(user_message=user_message, ori_response=ori_response)
            response = self._client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500,
            )
            raw = response.choices[0].message.content.strip()
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            result = json.loads(raw)
            # Clean nulls
            if "confirmed" in result:
                result["confirmed"] = {k: v for k, v in result["confirmed"].items() if v is not None and v != "null"}
            return result
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return {"confirmed": {}, "inferred": {}, "hard_filters": [], "options_mentioned": []}

    async def generate_guided_welcome(self, profile: dict, persona: str, pending_deepening: list, thread_id: str) -> str:
        """Generate proactive welcome and inject into thread."""
        if not self._available:
            return "Bienvenue ! Je suis ORI. Comment puis-je t'aider ?"
        try:
            prompt = (
                f"L'utilisateur vient de terminer son onboarding. Profil :\n{json.dumps(profile, ensure_ascii=False)}\n\n"
            )
            if pending_deepening:
                prompt += f"Questions de suivi :\n" + "\n".join(f"- {q}" for q in pending_deepening) + "\n\n"
            prompt += (
                "Génère un message d'accueil qui :\n"
                "1. Résume le profil (2-3 lignes)\n"
                "2. Pose LA question de suivi la plus importante\n"
                "3. Propose 1-2 pistes d'exploration\n"
                "Format : émojis et gras. Max 150 mots."
            )
            response = self._client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": ORCHESTRATOR_SYSTEM},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8
            )
            welcome = response.choices[0].message.content.strip()
            self._client.beta.threads.messages.create(
                thread_id=thread_id, role="assistant", content=welcome
            )
            return welcome
        except Exception as e:
            logger.error(f"Welcome generation failed: {e}")
            return "Bienvenue ! Je suis ORI. Comment puis-je t'aider ?"
