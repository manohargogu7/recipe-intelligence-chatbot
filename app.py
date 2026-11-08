
import sys
import re
import sqlite3
import io
from pathlib import Path
from contextlib import redirect_stdout

import streamlit as st


# ============================================================
# 1. PROJECT CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
DB_FILE = BASE_DIR / "database" / "recipe_database.db"

sys.path.insert(0, str(SRC_DIR))

try:
    from dietary_filter import filter_recipes
    from recipe_analytics import run_analytics
    from ingredient_matcher import match_recipes
    from substitution_engine import suggest_substitutions

    MODULE_ERROR = None

except Exception as error:
    MODULE_ERROR = str(error)


# ============================================================
# 2. STREAMLIT CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Recipe Intelligence Chatbot",
    page_icon="🍲",
    layout="wide"
)


# ============================================================
# 3. DATABASE FUNCTIONS
# ============================================================

def get_connection():

    if not DB_FILE.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_FILE}"
        )

    connection = sqlite3.connect(DB_FILE)
    connection.row_factory = sqlite3.Row

    return connection


def search_recipes(keyword, limit=10):

    connection = get_connection()

    try:

        pattern = f"%{keyword.strip()}%"

        rows = connection.execute("""
            SELECT
                r.recipe_id,
                r.title,
                r.instructions
            FROM recipes r
            WHERE
                LOWER(COALESCE(r.title, '')) LIKE LOWER(?)
                OR EXISTS (
                    SELECT 1
                    FROM ingredients i
                    WHERE i.recipe_id = r.recipe_id
                    AND (
                        LOWER(COALESCE(i.original_text, '')) LIKE LOWER(?)
                        OR LOWER(COALESCE(i.normalized_name, '')) LIKE LOWER(?)
                    )
                )
            ORDER BY r.title
            LIMIT ?
        """, (
            pattern,
            pattern,
            pattern,
            limit
        )).fetchall()

        return [dict(row) for row in rows]

    finally:
        connection.close()


def get_recipe_details(identifier):

    connection = get_connection()

    try:

        recipe = connection.execute("""
            SELECT *
            FROM recipes
            WHERE recipe_id = ?
            OR LOWER(title) = LOWER(?)
            LIMIT 1
        """, (
            identifier,
            identifier
        )).fetchone()

        if recipe is None:
            return None

        ingredients = connection.execute("""
            SELECT original_text
            FROM ingredients
            WHERE recipe_id = ?
            ORDER BY position
        """, (
            recipe["recipe_id"],
        )).fetchall()

        return {
            "recipe": dict(recipe),
            "ingredients": [
                row["original_text"]
                for row in ingredients
                if row["original_text"]
            ]
        }

    finally:
        connection.close()


# ============================================================
# 4. OUTPUT CAPTURE
# ============================================================

def capture_function(function, *args, **kwargs):

    output = io.StringIO()

    with redirect_stdout(output):
        result = function(*args, **kwargs)

    return result, output.getvalue()


# ============================================================
# 5. CHATBOT RESPONSE FUNCTIONS
# ============================================================

def recipe_search_response(keyword):

    if not keyword:
        return "Please provide a recipe name or ingredient."

    results = search_recipes(keyword, limit=10)

    if not results:
        return f"No recipes found for '{keyword}'."

    response = [
        f"Found {len(results)} recipes matching '{keyword}':",
        ""
    ]

    for index, recipe in enumerate(results, 1):

        response.append(
            f"{index}. {recipe['title']}"
        )

        response.append(
            f"Recipe ID: {recipe['recipe_id']}"
        )

        response.append("")

    response.append(
        "Use `details <recipe ID>` to view a recipe."
    )

    return "\n".join(response)


def recipe_details_response(identifier):

    result = get_recipe_details(identifier)

    if result is None:
        return "Recipe not found. Please provide an exact title or recipe ID."

    recipe = result["recipe"]

    response = [
        "RECIPE DETAILS",
        "=" * 45,
        f"Title: {recipe['title']}",
        f"Recipe ID: {recipe['recipe_id']}",
        "",
        "INGREDIENTS",
        "-" * 30
    ]

    for item in result["ingredients"]:
        response.append(f"- {item}")

    response.extend([
        "",
        "INSTRUCTIONS",
        "-" * 30,
        recipe.get("instructions") or "Instructions unavailable."
    ])

    return "\n".join(response)


def analytics_response():

    try:
        _, output = capture_function(run_analytics)

        return output or "Analytics executed successfully."

    except Exception as error:
        return f"Analytics error: {error}"


def dietary_response(keyword, restrictions):

    try:

        result = filter_recipes(
            keyword,
            restrictions,
            limit=10
        )

        response = [
            "DIETARY FILTER RESULTS",
            "=" * 45,
            f"Search: {keyword}",
            f"Restrictions: {', '.join(restrictions)}",
            "",
            f"Total candidates: {result['total_candidates']}",
            f"Eligible: {result['eligible_count']}",
            f"Excluded: {result['excluded_count']}",
            f"Unknown: {result['unknown_count']}",
            "",
            "COMPATIBLE RECIPES",
            "-" * 30
        ]

        for recipe in result["eligible"]:

            response.append(
                f"{recipe['title']} | {recipe['recipe_id']}"
            )

        response.extend([
            "",
            "EXCLUDED RECIPES",
            "-" * 30
        ])

        for recipe in result["excluded"][:10]:

            response.append(
                f"{recipe['title']} | {recipe['recipe_id']}"
            )

            for violation in recipe.get("violations", []):

                response.append(
                    f"  Violation: {violation['original_ingredient']}"
                )

        return "\n".join(response)

    except Exception as error:
        return f"Dietary filtering error: {error}"


def matching_response(ingredients, restrictions, max_steps):

    try:

        result = match_recipes(
            available_ingredients=ingredients,
            restrictions=restrictions,
            max_steps=max_steps,
            limit=5
        )

        response = [
            "INGREDIENT MATCHING RESULTS",
            "=" * 45,
            f"Available ingredients: {', '.join(ingredients)}",
            f"Restrictions: {', '.join(restrictions) or 'None'}",
            f"Maximum steps: {max_steps or 'No limit'}",
            "",
            f"Total recipes: {result['total_recipes']}",
            f"Eligible matches: {result['eligible_count']}",
            f"Unknown recipes: {result['unknown_count']}",
            "",
            "TOP MATCHES",
            "-" * 30
        ]

        for index, recipe in enumerate(result["eligible"], 1):

            response.extend([
                "",
                f"Rank: {index}",
                f"Title: {recipe['title']}",
                f"Recipe ID: {recipe['recipe_id']}",
                f"Match score: {recipe['score']}",
                f"Matched: {', '.join(recipe['matched'])}",
                f"Missing from recipe: {', '.join(recipe['missing'])}",
                f"Additional ingredients: {', '.join(recipe['extra'])}",
                f"Instruction steps: {recipe['steps']}"
            ])

        if not result["eligible"]:
            response.append("No eligible matches found.")

        return "\n".join(response)

    except Exception as error:
        return f"Ingredient matching error: {error}"


def substitution_response(recipe_id, ingredient, restrictions):

    try:

        _, output = capture_function(
            suggest_substitutions,
            recipe_id,
            ingredient,
            restrictions
        )

        return output or "No substitution result was generated."

    except Exception as error:
        return f"Substitution error: {error}"


# ============================================================
# 6. NATURAL LANGUAGE INTENT ROUTER
# ============================================================

def process_message(message):

    text = message.strip()

    lower = text.casefold()

    if not text:
        return "Please enter a question."

    # HELP
    if lower in ["help", "menu", "commands"]:

        return """
RECIPE CHATBOT COMMANDS

1. Search:
   search chicken

2. Recipe details:
   details <recipe ID>

3. Analytics:
   analytics

4. Dietary filtering:
   filter chicken avoid peanut

5. Ingredient matching:
   I have eggs, onions, tomatoes, rice

6. Ingredient substitution:
   substitute buttermilk in <recipe ID> avoid dairy

Supported restrictions:
dairy, peanut, vegetarian
"""

    # ANALYTICS
    if any(word in lower for word in [
        "analytics", "statistics",
        "dataset summary", "top ingredients"
    ]):

        return analytics_response()

    # SUBSTITUTION
    substitution_match = re.match(
        r"^(?:substitute|replace)\s+(.+?)\s+in\s+(.+?)"
        r"(?:\s+avoid\s+(.+))?$",
        text,
        re.IGNORECASE
    )

    if substitution_match:

        ingredient = substitution_match.group(1).strip()

        recipe_id = substitution_match.group(2).strip()

        restrictions = []

        if substitution_match.group(3):

            restrictions = [
                item.strip().lower()
                for item in substitution_match.group(3).split(",")
                if item.strip()
            ]

        return substitution_response(
            recipe_id,
            ingredient,
            restrictions
        )

    # RECIPE DETAILS
    if lower.startswith("details "):

        identifier = text[8:].strip()

        return recipe_details_response(identifier)

    # DIETARY FILTER
    filter_match = re.match(
        r"^(?:filter|find|search)\s+(.+?)\s+"
        r"(?:avoid|without|exclude)\s+"
        r"(dairy|peanut|vegetarian"
        r"(?:\s*,\s*(?:dairy|peanut|vegetarian))*)$",
        text,
        re.IGNORECASE
    )

    if filter_match:

        keyword = filter_match.group(1).strip()

        restrictions = [
            item.strip().lower()
            for item in filter_match.group(2).split(",")
        ]

        return dietary_response(
            keyword,
            restrictions
        )

    # INGREDIENT MATCHING
    ingredient_match = re.match(
        r"^(?:i have|ingredients:)\s+(.+)$",
        text,
        re.IGNORECASE
    )

    if ingredient_match:

        raw = ingredient_match.group(1)

        restrictions = []

        restriction_match = re.search(
            r"\s+avoid\s+"
            r"(dairy|peanut|vegetarian"
            r"(?:\s*,\s*(?:dairy|peanut|vegetarian))*)$",
            raw,
            re.IGNORECASE
        )

        if restriction_match:

            restrictions = [
                item.strip().lower()
                for item in restriction_match.group(1).split(",")
            ]

            raw = raw[:restriction_match.start()].strip()

        ingredients = [
            item.strip()
            for item in raw.split(",")
            if item.strip()
        ]

        return matching_response(
            ingredients,
            restrictions,
            None
        )

    # RECIPE SEARCH
    search_match = re.match(
        r"^(?:search|find)\s+(.+)$",
        text,
        re.IGNORECASE
    )

    if search_match:

        return recipe_search_response(
            search_match.group(1).strip()
        )

    # DEFAULT: Search using the supplied words.
    return recipe_search_response(text)


# ============================================================
# 7. CHATBOT INTERFACE
# ============================================================

st.title("🍲 Recipe Intelligence Chatbot")

st.caption(
    "Search, analyze, match and adapt recipes using your local dataset."
)

if MODULE_ERROR:

    st.error(
        "Could not import one or more project modules:\n\n"
        + MODULE_ERROR
    )

    st.code(
        "Check src/dietary_filter.py\n"
        "Check src/recipe_analytics.py\n"
        "Check src/ingredient_matcher.py\n"
        "Check src/substitution_engine.py"
    )

    st.stop()


if not DB_FILE.exists():

    st.error(
        f"Recipe database not found: {DB_FILE}"
    )

    st.stop()


# ------------------------------------------------------------
# SIDEBAR
# ------------------------------------------------------------

with st.sidebar:

    st.header("Recipe Assistant")

    st.success("Database connected")

    st.markdown("### Supported features")

    st.markdown("""
    - Recipe search
    - Recipe details
    - Dietary filtering
    - Ingredient matching
    - Recipe analytics
    - Ingredient substitution
    """)

    st.divider()

    st.markdown("### Example commands")

    st.code(
        "search chicken\n"
        "details <recipe ID>\n"
        "analytics\n"
        "filter chicken avoid peanut\n"
        "I have eggs, rice, tomatoes\n"
        "substitute buttermilk in <recipe ID> avoid dairy"
    )

    if st.button("Clear conversation", use_container_width=True):

        st.session_state.messages = []

        st.rerun()


# ------------------------------------------------------------
# CHAT HISTORY
# ------------------------------------------------------------

if "messages" not in st.session_state:

    st.session_state.messages = []


for message in st.session_state.messages:

    with st.chat_message(message["role"]):

        st.markdown(message["content"])


# ------------------------------------------------------------
# CHAT INPUT
# ------------------------------------------------------------

user_message = st.chat_input(
    "Ask me about recipes, ingredients or substitutions..."
)


if user_message:

    st.session_state.messages.append({
        "role": "user",
        "content": user_message
    })

    with st.chat_message("user"):
        st.markdown(user_message)

    with st.chat_message("assistant"):

        with st.spinner("Analyzing your request..."):

            try:

                answer = process_message(user_message)

            except Exception as error:

                answer = (
                    "An error occurred while processing "
                    f"your request: {error}"
                )

        st.markdown(answer)

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer
    })


# ============================================================
# 8. FOOTER
# ============================================================

st.divider()

st.caption(
    "Recipe Intelligence Chatbot | "
    "Python • SQLite • Pandas • Streamlit"
)
