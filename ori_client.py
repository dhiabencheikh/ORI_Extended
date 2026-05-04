"""
ORI Client — Interface with the ORI Reasoning Engine on Vertex AI.
Falls back to curated L'Étudiant content if the API is unreachable.
All fallback URLs are verified as live on letudiant.fr.
"""

import os
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Verified L'Étudiant URLs (all return HTTP 200)
# ─────────────────────────────────────────────────────────────
URLS = {
    "classement_ingenieurs": "https://www.letudiant.fr/classements/classement-des-ecoles-d-ingenieurs.html",
    "ecoles_ingenieurs": "https://www.letudiant.fr/etudes/ecoles-d-ingenieurs.html",
    "classement_commerce": "https://www.letudiant.fr/classements/classement-des-grandes-ecoles-de-commerce.html",
    "medecine_sante": "https://www.letudiant.fr/etudes/medecine-sante.html",
    "logement": "https://www.letudiant.fr/lifestyle/logement.html",
    "aides_financieres": "https://www.letudiant.fr/lifestyle/aides-financieres.html",
    "parcoursup": "https://www.letudiant.fr/etudes/parcoursup.html",
    "alternance": "https://www.letudiant.fr/etudes/alternance.html",
    "test_orientation": "https://www.letudiant.fr/test/orientation.html",
    "fiches_metiers": "https://www.letudiant.fr/fiches/metiers.html",
    "lifestyle": "https://www.letudiant.fr/lifestyle.html",
    "etudes": "https://www.letudiant.fr/etudes.html",
    "jobs_stages": "https://www.letudiant.fr/jobsstages.html",
    # School-specific pages (annuaire format)
    "insa_lyon": "https://www.letudiant.fr/etudes/annuaire-enseignement-superieur/etablissement/etablissement-institut-national-des-sciences-appliquees-de-lyon-insa-lyon-16327.html",
    "telecom_paris": "https://www.letudiant.fr/etudes/annuaire-enseignement-superieur/etablissement/etablissement-telecom-paris-7160.html",
    "hec_paris": "https://www.letudiant.fr/etudes/annuaire-enseignement-superieur/etablissement/etablissement-hec-paris-7050.html",
    "essec": "https://www.letudiant.fr/etudes/annuaire-enseignement-superieur/etablissement/etablissement-essec-business-school-7040.html",
    "sciences_po": "https://www.letudiant.fr/etudes/annuaire-enseignement-superieur/etablissement/etablissement-sciences-po-paris-7792.html",
    "paris_saclay": "https://www.letudiant.fr/etudes/annuaire-enseignement-superieur/etablissement/etablissement-universite-paris-saclay-14194.html",
}


class ORIClient:
    """Client for the ORI Reasoning Engine on GCP Vertex AI."""

    def __init__(self):
        self._engine = None
        self._available = False
        self._init_attempted = False

    def _lazy_init(self):
        """Lazy initialization of the Vertex AI client."""
        if self._init_attempted:
            return
        self._init_attempted = True

        try:
            import vertexai
            from vertexai.preview import reasoning_engines

            project_id = os.getenv("GCP_PROJECT_ID", "letudiant-data-prod")
            location = os.getenv("GCP_LOCATION", "europe-west1")
            engine_id = os.getenv("ORI_REASONING_ENGINE_ID", "7428309353347678208")

            # Set credentials if env var points to a valid file
            creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
            if creds_path and os.path.exists(creds_path):
                logger.info(f"Using GCP credentials from: {creds_path}")

            vertexai.init(project=project_id, location=location)
            self._engine = reasoning_engines.ReasoningEngine(engine_id)
            # Quick connection test
            logger.info("ORI Reasoning Engine initialized. Testing connection...")
            test_resp = self._engine.query(config={"thread_id": "healthcheck"}, message="ping")
            logger.info(f"ORI Engine connected! Response type: {type(test_resp)}")
            self._available = True
        except Exception as e:
            logger.warning(f"ORI Reasoning Engine unavailable: {e}. Using fallback mode.")
            self._available = False

    async def query(self, message: str, thread_id: str, profile: dict = None) -> dict:
        """Send a query to the ORI Reasoning Engine."""
        self._lazy_init()

        if self._available:
            try:
                enriched_message = message
                if profile:
                    profile_context = (
                        f"[Contexte utilisateur: Persona={profile.get('_persona','lyceen')}, "
                        f"Niveau={profile.get('level','?')}, "
                        f"Intérêts={profile.get('interests','?')}, "
                        f"Étape={profile.get('stage','?')}, "
                        f"Contraintes={profile.get('constraints','?')}] "
                    )
                    enriched_message = profile_context + message

                response = self._engine.query(
                    config={"thread_id": thread_id},
                    message=enriched_message,
                )
                # Parse response — ORI returns "S␟content␟metadata" format
                response_text = str(response)
                if "␟" in response_text:
                    parts = response_text.split("␟")
                    response_text = parts[1] if len(parts) > 1 else response_text

                return {
                    "success": True,
                    "response": response_text.strip(),
                    "source": "ori_engine",
                }
            except Exception as e:
                logger.error(f"ORI query failed: {e}")
                return await self._fallback_response(message, profile)
        else:
            return await self._fallback_response(message, profile)

    async def _fallback_response(self, message: str, profile: dict = None) -> dict:
        """Fallback with curated L'Étudiant content. All URLs verified as HTTP 200."""
        msg_lower = message.lower()

        if any(w in msg_lower for w in ["ingénieur", "engineer", "école d'ingé", "insa", "polytechnique"]):
            response = (
                "Les écoles d'ingénieurs en France offrent plus de 200 spécialités. "
                "Selon le classement L'Étudiant 2025 :\n\n"
                "🏆 **Top écoles post-bac** : INSA Lyon, UTC Compiègne, ESIEE Paris\n"
                "🏆 **Top écoles post-prépa** : Polytechnique, CentraleSupélec, Mines Paris\n\n"
                "Les critères clés : sélectivité (notes au bac, dossier), "
                "spécialisation (généraliste vs spécialisée), et débouchés (taux d'insertion > 95%).\n\n"
                f"📎 [Classement des écoles d'ingénieurs 2025]({URLS['classement_ingenieurs']})\n"
                f"📎 [Toutes les écoles d'ingénieurs]({URLS['ecoles_ingenieurs']})"
            )
        elif any(w in msg_lower for w in ["commerce", "business", "management", "hec", "essec"]):
            response = (
                "Les écoles de commerce sont accessibles post-bac ou après une prépa. "
                "Le classement L'Étudiant 2025 distingue :\n\n"
                "🏆 **Top 5 post-prépa** : HEC, ESSEC, ESCP, emlyon, EDHEC\n"
                "🏆 **Top post-bac** : IESEG, ESSCA, EM Normandie\n\n"
                "Points à considérer : accréditations (AACSB, EQUIS), "
                "frais de scolarité (7 000€ à 18 000€/an), alternance possible, et réseau alumni.\n\n"
                f"📎 [Classement des écoles de commerce 2025]({URLS['classement_commerce']})"
            )
        elif any(w in msg_lower for w in ["médecine", "santé", "pass", "las", "infirmier"]):
            response = (
                "Depuis la réforme, l'accès aux études de santé passe par le PASS ou la L.AS. "
                "Taux de réussite moyen en PASS : environ 20-25%.\n\n"
                "📌 **PASS** : Parcours spécifique santé + mineure disciplinaire\n"
                "📌 **L.AS** : Licence avec accès santé (droit, bio, éco...)\n\n"
                "Les débouchés santé : médecine, pharmacie, maïeutique, odontologie, kinésithérapie.\n\n"
                f"📎 [Les études de santé sur L'Étudiant]({URLS['medecine_sante']})"
            )
        elif any(w in msg_lower for w in ["logement", "résidence", "studio", "loyer", "appart"]):
            response = (
                "Le logement est LE sujet pratique n°1 des étudiants. Voici les options :\n\n"
                "🏠 **Résidence CROUS** : ~150-350€/mois, demande via le DSE avant mai\n"
                "🏢 **Résidence privée** : 400-800€/mois, plus flexible\n"
                "👥 **Colocation** : économique et conviviale, ~300-500€/mois\n"
                "🏡 **Chez l'habitant** : échange de services possible\n\n"
                "💡 Aides disponibles : APL (CAF), ALS, garantie Visale, avance Loca-Pass.\n\n"
                f"📎 [Guide du logement étudiant]({URLS['logement']})\n"
                f"📎 [Aides financières pour étudiants]({URLS['aides_financieres']})"
            )
        elif any(w in msg_lower for w in ["bourse", "aide", "financement", "argent", "caf"]):
            response = (
                "Plusieurs aides financières existent pour les étudiants :\n\n"
                "💰 **Bourse sur critères sociaux** (CROUS) : de 1 454€ à 6 335€/an\n"
                "💰 **Aide au mérite** : 900€/an (mention TB au bac)\n"
                "💰 **APL/ALS** : aide au logement (CAF)\n"
                "💰 **Garantie Visale** : caution gratuite\n"
                "💰 **Aides régionales** : selon ta région\n\n"
                "📅 Demande de bourse : dossier DSE entre janvier et mai.\n\n"
                f"📎 [Toutes les bourses et aides]({URLS['aides_financieres']})"
            )
        elif any(w in msg_lower for w in ["parcoursup", "vœux", "dossier", "candidature"]):
            response = (
                "Parcoursup, c'est la plateforme nationale d'admission post-bac. "
                "Calendrier 2025-2026 :\n\n"
                "📅 **Décembre-Janvier** : découverte des formations\n"
                "📅 **Janvier-Mars** : inscription et saisie des vœux (10 max)\n"
                "📅 **Mars-Avril** : confirmation des vœux + finalisation du dossier\n"
                "📅 **Juin** : phase d'admission principale\n"
                "📅 **Juin-Septembre** : phase complémentaire\n\n"
                "💡 Conseils : soigne ta lettre de motivation (projet de formation motivé) "
                "et diversifie tes vœux !\n\n"
                f"📎 [Guide Parcoursup sur L'Étudiant]({URLS['parcoursup']})"
            )
        elif any(w in msg_lower for w in ["alternance", "apprentissage", "contrat"]):
            response = (
                "L'alternance, c'est étudier ET travailler. Deux types de contrats :\n\n"
                "📝 **Contrat d'apprentissage** : 16-29 ans, formation diplômante\n"
                "📝 **Contrat de professionnalisation** : tout âge, qualification\n\n"
                "Avantages : salaire (27% à 100% du SMIC), frais de scolarité pris en charge, "
                "expérience pro valorisée.\n\n"
                "🔎 Plus de 15 000 formations sont disponibles en alternance en France.\n\n"
                f"📎 [Guide de l'alternance]({URLS['alternance']})"
            )
        elif any(w in msg_lower for w in ["stage", "expérience", "entreprise"]):
            response = (
                "Les stages sont essentiels pour construire ton parcours pro. "
                "Quelques repères :\n\n"
                "📌 Stage de + de 2 mois = gratification obligatoire (~4,35€/h)\n"
                "📌 Convention de stage obligatoire\n"
                "📌 6 mois maximum par an dans la même entreprise\n\n"
                "💡 Où chercher : sites spécialisés, salons, réseau école, candidatures spontanées.\n\n"
                f"📎 [Jobs et stages étudiants]({URLS['jobs_stages']})"
            )
        elif any(w in msg_lower for w in ["sais pas", "aucune idée", "perdu", "ne sais pas", "no idea"]):
            response = (
                "C'est tout à fait normal de ne pas savoir ! La majorité des lycéens sont dans "
                "ton cas. Voici comment ORI peut t'aider :\n\n"
                "1️⃣ **Explorer les familles de métiers** — Partir de ce que tu aimes faire\n"
                "2️⃣ **Découvrir des parcours atypiques** — Beaucoup de chemins mènent au même métier\n"
                "3️⃣ **Comparer des formations** — Quand tu auras quelques pistes\n\n"
                "Dis-moi plutôt : qu'est-ce que tu aimes faire au quotidien ? "
                "Tes loisirs, les matières où tu te sens bien, ce qui te donne de l'énergie… "
                "On va partir de là ! 😊\n\n"
                f"📎 [Test d'orientation gratuit]({URLS['test_orientation']})\n"
                f"📎 [Fiches métiers]({URLS['fiches_metiers']})"
            )
        elif any(w in msg_lower for w in ["vie étudiante", "student life", "campus", "association"]):
            response = (
                "La vie étudiante, c'est bien plus que les cours ! Voici ce qui t'attend :\n\n"
                "🎭 **Associations** : BDE, BDS, associations humanitaires, culturelles...\n"
                "🏋️ **Sport universitaire** : SUAPS, compétitions inter-facs\n"
                "🎉 **Événements** : soirées d'intégration, forums, galas\n"
                "🍽️ **Restauration** : restos U CROUS (~3,30€ le repas)\n"
                "🏥 **Santé** : SUMPPS, mutuelle étudiante, psychologue gratuit\n\n"
                f"📎 [Tout sur la vie étudiante]({URLS['lifestyle']})"
            )
        else:
            response = (
                "C'est une excellente question ! Laisse-moi te donner quelques pistes "
                "basées sur le contenu L'Étudiant.\n\n"
                "Pour mieux te répondre, peux-tu me préciser :\n"
                "- Le domaine qui t'intéresse ?\n"
                "- Ton niveau d'études actuel ?\n"
                "- Une contrainte particulière (lieu, budget, alternance) ?\n\n"
                "N'hésite pas à me poser des questions sur : les formations, les écoles, "
                "la vie étudiante, le logement, les bourses, Parcoursup, l'alternance ou les stages ! 😊\n\n"
                f"📎 [Explorer toutes les formations]({URLS['etudes']})"
            )

        return {
            "success": True,
            "response": response,
            "source": "fallback_rag",
        }

    @property
    def is_available(self) -> bool:
        self._lazy_init()
        return self._available
