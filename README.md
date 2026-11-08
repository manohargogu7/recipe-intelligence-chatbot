# 🍲 Recipe Intelligence Chatbot

An intelligent, data-driven recipe assistant that searches, analyzes, matches, filters, and adapts recipes using a dataset of 125,164 recipes.

## Project Overview

The Recipe Intelligence Chatbot combines Python, SQLite, data processing, recipe analytics, ingredient matching, dietary filtering, and evidence-based ingredient substitution in a Streamlit application.

The system helps users discover recipes based on available ingredients and dietary preferences while providing transparent results grounded in the underlying recipe dataset.

## Key Features

### 1. Recipe Search
- Search recipes using dish names or ingredients.
- Retrieve recipe details using recipe IDs.
- Display original ingredients and cooking instructions.

### 2. Dietary Filtering
- Dairy-free filtering.
- Peanut-free filtering.
- Vegetarian filtering.
- Identify compatible, excluded, and unknown recipes.
- Display ingredient-level violation evidence.

### 3. Ingredient-Based Recipe Matching
- Match recipes against available ingredients.
- Rank recipes using ingredient coverage.
- Identify additional required ingredients.
- Consider instruction-step limits.
- Display matching scores.

### 4. Recipe Analytics
- Dataset statistics.
- Most common ingredients.
- Ingredient-count distribution.
- Garlic and onion recipe analysis.
- Recipes with fewer cooking steps.

### 5. Ingredient Substitution
- Identify unavailable ingredients.
- Find related recipes.
- Retrieve alternative ingredient evidence.
- Generate an updated ingredient list.
- Communicate substitution uncertainty and limitations.

### 6. Conversational Interface
- Streamlit-based chatbot.
- Conversation history.
- Command-based intent routing.
- Integrated recipe search and analysis modules.

## Dataset Information

| Metric | Value |
|---|---:|
| Total recipes | 125,164 |
| Recipes with ingredient records | 122,971 |
| Ingredient records | 1,316,950 |
| Source files | 3 JSON files |

## Technology Stack

- Python
- SQLite
- Pandas
- NumPy
- Streamlit
- Regular Expressions
- JSON
- Git and GitHub

## Project Structure

```text
recipe-intelligence-chatbot/
│
├── data/
│   ├── raw/
│   └── processed/
│
├── database/
│   └── recipe_database.db
│
├── evaluation/
│   └── results/
│       └── final_evaluation_report.md
│
├── src/
│   ├── data_loader.py
│   ├── database.py
│   ├── inspect_dataset.py
│   ├── preprocessing.py
│   ├── recipe_search.py
│   ├── dietary_filter.py
│   ├── ingredient_matcher.py
│   ├── recipe_analytics.py
│   └── substitution_engine.py
│
├── app.py
├── README.md
├── requirements.txt
└── .gitignore
```

## Installation and Setup

### 1. Clone the repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd recipe-intelligence-chatbot
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

### 3. Activate the environment

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Prepare the database

Ensure the processed dataset and SQLite database are available.

If rebuilding the database, run the project's data-loading and database preparation scripts in the required order.

### 6. Launch the chatbot

```bash
streamlit run app.py
```

Open:

```text
http://localhost:8501
```

## Example Commands

```text
search chicken

details YOUR_RECIPE_ID

analytics

filter chicken avoid peanut

I have eggs, onions, tomatoes, rice

substitute buttermilk in YOUR_RECIPE_ID avoid dairy
```

## Evaluation

The project includes functional testing for:

- Recipe search and details.
- Dataset analytics.
- Ingredient matching.
- Dietary restrictions.
- No-match handling.
- Evidence-based ingredient substitution.

See `evaluation/results/final_evaluation_report.md` for the evaluation record.

## Limitations

- Some recipes contain missing ingredient information.
- Raw ingredient records may contain advertisement artifacts.
- Substitution recommendations depend on available dataset evidence.
- Ingredient quantities and cooking equivalence require additional validation.
- Dietary filtering based on text matching cannot guarantee allergy safety.
- The current chatbot uses rule-based intent routing rather than an integrated LLM.

## Responsible AI and Data Reliability

The application distinguishes between verified dataset evidence and uncertain recommendations. It avoids claiming that an ingredient substitution is guaranteed when sufficient evidence is unavailable.

## Author

**Manohar Gogu**

GitHub: https://github.com/manohargogu7

LinkedIn: https://www.linkedin.com/in/gogu-manohar-b06442257/

---

*Developed as a Recipe Intelligence and Generative AI application project.*