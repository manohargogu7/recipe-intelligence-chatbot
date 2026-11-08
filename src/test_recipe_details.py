
from recipe_search import get_recipe


def display_recipe(recipe_id):

    recipe = get_recipe(recipe_id)

    if recipe is None:
        print("\nRecipe not found.")
        return

    print("\n" + "=" * 60)
    print("COMPLETE RECIPE DETAILS")
    print("=" * 60)

    print(f"\nTitle: {recipe['title']}")
    print(f"Recipe ID: {recipe['recipe_id']}")
    print(f"Source: {recipe['source']}")

    print("\nORIGINAL INGREDIENTS")
    print("-" * 40)

    for index, ingredient in enumerate(
        recipe["ingredients"], start=1
    ):
        print(f"{index}. {ingredient['original_text']}")

    print("\nORIGINAL INSTRUCTIONS")
    print("-" * 40)

    instructions = recipe.get("instructions")

    if instructions and instructions.strip():
        print(instructions)
    else:
        print("Instructions are unavailable in the dataset.")

    print("\n" + "=" * 60)


if __name__ == "__main__":

    recipe_id = input("Enter the recipe ID: ").strip()

    display_recipe(recipe_id)
