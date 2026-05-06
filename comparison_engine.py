"""
Comparison Engine — Structures side-by-side comparisons of formations/schools.
"""

import json
from typing import Optional


# Pre-built comparison data for common programme matchups (L'Étudiant sourced)
COMPARISON_DATA = {
    "insa lyon": {
        "full_name": "INSA Lyon",
        "type": "École d'ingénieurs post-bac",
        "selectivity": "Très sélectif (dossier + entretien)",
        "location": "Lyon (Villeurbanne)",
        "cost": "~610€/an (frais universitaires)",
        "specialties": "Génie civil, Informatique, Télécommunications, Biosciences, Mécanique",
        "career": "Industrie, R&D, Conseil, 95% d'insertion à 6 mois",
        "international": "40% des diplômés ont une expérience internationale",
        "student_life": "Campus intégré, 120 associations, résidence sur campus",
        "url": "https://www.letudiant.fr/etudes/annuaire-enseignement-superieur/etablissement/etablissement-institut-national-des-sciences-appliquees-de-lyon-insa-lyon-16327.html",
    },
    "telecom paris": {
        "full_name": "Télécom Paris",
        "type": "École d'ingénieurs post-prépa (IMT)",
        "selectivity": "Très sélectif (concours Mines-Télécom)",
        "location": "Palaiseau (Paris-Saclay)",
        "cost": "~2 650€/an",
        "specialties": "IA, Data Science, Cybersécurité, Réseaux, Signal",
        "career": "GAFAM, Startups tech, Finance quantitative, 100% d'insertion",
        "international": "Double diplôme avec MIT, NUS, TU Munich",
        "student_life": "Campus Saclay, proximité HEC/Polytechnique",
        "url": "https://www.letudiant.fr/etudes/annuaire-enseignement-superieur/etablissement/etablissement-telecom-paris-7160.html",
    },
    "hec paris": {
        "full_name": "HEC Paris",
        "type": "Grande école de commerce post-prépa",
        "selectivity": "Extrêmement sélectif (concours BCE)",
        "location": "Jouy-en-Josas (Île-de-France)",
        "cost": "~18 000€/an (bourses disponibles)",
        "specialties": "Finance, Strategy, Entrepreneuriat, Luxe, Digital",
        "career": "Consulting (McKinsey, BCG), Finance, Entrepreneuriat, salaire moyen 65k€",
        "international": "99% des étudiants font un échange, 150 partenaires",
        "student_life": "Campus résidentiel, 130 associations, vie communautaire intense",
        "url": "https://www.letudiant.fr/etudes/annuaire-enseignement-superieur/etablissement/etablissement-hec-paris-7050.html",
    },
    "essec": {
        "full_name": "ESSEC Business School",
        "type": "Grande école de commerce",
        "selectivity": "Très sélectif (concours BCE)",
        "location": "Cergy-Pontoise + Singapour + Rabat",
        "cost": "~17 000€/an",
        "specialties": "Management, Finance, Luxe, Hospitality, Data Analytics",
        "career": "Consulting, Finance, Luxe, Tech, salaire moyen 55k€",
        "international": "3 campus internationaux, 200 universités partenaires",
        "student_life": "Campus Cergy, nombreuses associations, incubateur",
        "url": "https://www.letudiant.fr/etudes/annuaire-enseignement-superieur/etablissement/etablissement-essec-business-school-7040.html",
    },
    "sciences po paris": {
        "full_name": "Sciences Po Paris",
        "type": "Grande école (IEP)",
        "selectivity": "Très sélectif (dossier + oral)",
        "location": "Paris (7 campus en France)",
        "cost": "0€ à 15 000€ selon revenus",
        "specialties": "Relations internationales, Droit, Économie, Journalisme, Affaires publiques",
        "career": "Fonction publique, ONG, Consulting, Journalisme, Diplomatie",
        "international": "3ème année obligatoire à l'étranger",
        "student_life": "7 campus, vie associative riche, diversité culturelle",
        "url": "https://www.letudiant.fr/etudes/annuaire-enseignement-superieur/etablissement/etablissement-sciences-po-paris-7792.html",
    },
    "université paris-saclay": {
        "full_name": "Université Paris-Saclay",
        "type": "Université publique",
        "selectivity": "Accès via Parcoursup (capacité variable)",
        "location": "Plateau de Saclay (Essonne)",
        "cost": "~170€/an (frais universitaires)",
        "specialties": "Sciences, Informatique, Mathématiques, Physique, Biologie",
        "career": "Recherche, Industrie, Enseignement, Startups deeptech",
        "international": "Classée top 15 mondial en maths et physique (Shanghai)",
        "student_life": "Nouveau campus, proximité grandes écoles, sport universitaire",
        "url": "https://www.letudiant.fr/etudes/annuaire-enseignement-superieur/etablissement/etablissement-universite-paris-saclay-14194.html",
    },
}


async def build_comparison(option1: str, option2: str, option3: str = None, profile: dict = None, agent = None) -> dict:
    """Build a structured comparison between 2-3 options."""

    options = [option1, option2]
    if option3:
        options.append(option3)

    # Try to match options to our database
    matched = {}
    for opt in options:
        opt_lower = opt.lower().strip()
        for key, data in COMPARISON_DATA.items():
            if key in opt_lower or opt_lower in key:
                matched[opt] = data
                break

    # If we don't have data for an option, fetch dynamically
    for opt in options:
        if opt not in matched:
            if agent and agent.is_available:
                matched[opt] = await _fetch_dynamic_school_data(opt, agent)
            else:
                matched[opt] = {
                    "full_name": opt,
                    "type": "Formation",
                    "selectivity": "Consulte la fiche L'Étudiant",
                    "location": "—",
                    "cost": "—",
                    "specialties": "—",
                    "career": "—",
                    "international": "—",
                    "student_life": "—",
                    "url": f"https://www.letudiant.fr/etudes/annuaire-enseignement-superieur.html?q={opt.replace(' ', '+')}",
                }

    # Build comparison criteria
    criteria_keys = [
        ("Type de formation", "type"),
        ("Sélectivité", "selectivity"),
        ("Localisation", "location"),
        ("Coût annuel", "cost"),
        ("Spécialités", "specialties"),
        ("Débouchés", "career"),
        ("International", "international"),
        ("Vie étudiante", "student_life"),
    ]

    criteria = []
    for label, key in criteria_keys:
        values = {}
        for opt in options:
            values[opt] = matched[opt].get(key, "—")

        # Determine best for profile
        best = _determine_best_for_profile(key, values, profile)

        criteria.append({
            "name": label,
            "values": values,
            "best_for_profile": best,
        })

    # Build recommendation
    recommendation = _build_recommendation(options, matched, profile)

    # Traffic links
    traffic_links = []
    for opt in options:
        if matched[opt].get("url"):
            traffic_links.append({
                "label": f"Fiche {matched[opt]['full_name']} sur L'Étudiant",
                "url": matched[opt]["url"],
            })

    return {
        "options": [matched[opt]["full_name"] for opt in options],
        "criteria": criteria,
        "recommendation": recommendation,
        "traffic_links": traffic_links,
    }


def _determine_best_for_profile(criterion: str, values: dict, profile: dict) -> Optional[str]:
    """Determine which option best matches the user profile for a given criterion."""
    if not profile:
        return None

    constraints = profile.get("constraints", [])
    interests = profile.get("interests", [])

    # Location matching
    if criterion == "location":
        for constraint in constraints:
            if "près" in str(constraint).lower() or "proxim" in str(constraint).lower():
                # We'd need the user's city to match properly
                return None

    # Cost matching
    if criterion == "cost":
        for constraint in constraints:
            if "budget" in str(constraint).lower() or "bourse" in str(constraint).lower():
                # Prefer cheaper option
                costs = {}
                for opt, val in values.items():
                    try:
                        cost_str = val.replace("€", "").replace("/an", "").replace("~", "").replace(" ", "")
                        cost_str = cost_str.split("(")[0].strip()
                        costs[opt] = float(cost_str.replace(",", "."))
                    except (ValueError, AttributeError):
                        costs[opt] = float("inf")
                if costs:
                    return min(costs, key=costs.get)

    # International matching
    if criterion == "international":
        for constraint in constraints:
            if "étranger" in str(constraint).lower() or "international" in str(constraint).lower():
                return None  # Can't automatically determine best

    return None


def _build_recommendation(options: list, matched: dict, profile: dict) -> dict:
    """Build a named recommendation based on profile matching."""
    if not profile:
        return {
            "choice": options[0] if options else "",
            "reason": "Complète ton profil pour recevoir une recommandation personnalisée."
        }

    # Simple scoring based on profile match
    scores = {}
    for opt in options:
        score = 0
        data = matched[opt]

        # Check interest alignment
        interests = profile.get("interests", [])
        for interest in interests:
            interest_lower = str(interest).lower()
            specialties_lower = data.get("specialties", "").lower()
            if any(w in specialties_lower for w in interest_lower.split()):
                score += 2

        # Check constraint alignment
        constraints = profile.get("constraints", [])
        for constraint in constraints:
            constraint_lower = str(constraint).lower()
            if "alternance" in constraint_lower and "alternance" in data.get("career", "").lower():
                score += 1
            if "budget" in constraint_lower:
                try:
                    cost_str = data.get("cost", "").replace("€", "").replace("/an", "").replace("~", "").replace(" ", "")
                    cost_str = cost_str.split("(")[0].strip()
                    cost = float(cost_str.replace(",", "."))
                    if cost < 1000:
                        score += 2
                except (ValueError, AttributeError):
                    pass

        scores[opt] = score

    best = max(scores, key=scores.get)
    best_data = matched[best]

    return {
        "choice": best_data["full_name"],
        "reason": (
            f"D'après ton profil, {best_data['full_name']} semble le mieux correspondre "
            f"à tes intérêts et contraintes. Ses spécialités ({best_data.get('specialties', '')}) "
            f"s'alignent avec ce que tu recherches."
        ),
    }


async def _fetch_dynamic_school_data(school_name: str, agent) -> dict:
    prompt = f"""Génère une fiche de comparaison structurée pour l'établissement suivant : {school_name}.
Tu dois extraire ou estimer les informations suivantes au format JSON strictement:
{{
    "full_name": "Nom complet de l'école/formation",
    "type": "Type de formation (ex: Université, Grande école)",
    "selectivity": "Niveau de sélectivité (ex: Très sélectif, Dossier)",
    "location": "Ville ou campus principal",
    "cost": "Coût annuel estimé",
    "specialties": "2 à 3 spécialités principales",
    "career": "Débouchés ou secteurs principaux",
    "international": "Opportunités à l'international",
    "student_life": "Aperçu de la vie étudiante",
    "url": "https://www.letudiant.fr/etudes/annuaire-enseignement-superieur.html?q=[NOM DE L'ECOLE SANS ESPACES REMPLACES PAR PLUS]"
}}
Si tu n'es pas sûr d'une information, utilise 'Non précisé'. Le JSON doit être valide et ne rien contenir d'autre."""

    try:
        response = agent._client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=400,
            response_format={ "type": "json_object" }
        )
        content = response.choices[0].message.content.strip()
        data = json.loads(content)
        # Ensure URL format
        if "url" not in data or "recherche" in data["url"]:
            data["url"] = f"https://www.letudiant.fr/etudes/annuaire-enseignement-superieur.html?q={school_name.replace(' ', '+')}"
        return data
    except Exception as e:
        return {
            "full_name": school_name,
            "type": "Formation",
            "selectivity": "Consulte la fiche",
            "location": "—",
            "cost": "—",
            "specialties": "—",
            "career": "—",
            "international": "—",
            "student_life": "—",
            "url": f"https://www.letudiant.fr/etudes/annuaire-enseignement-superieur.html?q={school_name.replace(' ', '+')}",
        }
