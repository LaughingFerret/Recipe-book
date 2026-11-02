from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Ingredient, Recipe
from .schemas import RecipeIngredientInput, RecipeInput, RecipeStepInput
from .services import CatalogService, RecipeService


@dataclass(frozen=True)
class SeedResult:
    created: bool
    recipes: int
    ingredients: int


INGREDIENT_CATEGORIES = {
    "Овощи": "Свежие и корнеплоды.",
    "Мясо и птица": "Мясные продукты и птица.",
    "Рыба и морепродукты": "Рыба и морепродукты.",
    "Молочные продукты": "Молоко, сливки, сыр и кисломолочные продукты.",
    "Крупы и макароны": "Крупы, мука и макаронные изделия.",
    "Специи": "Соль, перец и пряности.",
    "Травы": "Свежая и сушёная зелень.",
    "Фрукты": "Фрукты и ягоды.",
    "Яйца и прочее": "Яйца, сахар и прочие базовые продукты.",
    "Масла и жиры": "Растительные масла.",
}

INGREDIENTS = [
    # name, category, unit
    ("Картофель", "Овощи", "г"),
    ("Морковь", "Овощи", "г"),
    ("Лук репчатый", "Овощи", "г"),
    ("Свёкла", "Овощи", "г"),
    ("Капуста белокочанная", "Овощи", "г"),
    ("Помидор", "Овощи", "г"),
    ("Огурец", "Овощи", "г"),
    ("Тыква", "Овощи", "г"),
    ("Чеснок", "Овощи", "г"),
    ("Говядина", "Мясо и птица", "г"),
    ("Куриное филе", "Мясо и птица", "г"),
    ("Свинина", "Мясо и птица", "г"),
    ("Лосось", "Рыба и морепродукты", "г"),
    ("Сметана", "Молочные продукты", "г"),
    ("Сливки", "Молочные продукты", "мл"),
    ("Сыр твёрдый", "Молочные продукты", "г"),
    ("Молоко", "Молочные продукты", "мл"),
    ("Сливочное масло", "Молочные продукты", "г"),
    ("Рис", "Крупы и макароны", "г"),
    ("Макароны", "Крупы и макароны", "г"),
    ("Мука", "Крупы и макароны", "г"),
    ("Соль", "Специи", "г"),
    ("Перец чёрный", "Специи", "г"),
    ("Паприка", "Специи", "г"),
    ("Базилик", "Травы", "г"),
    ("Петрушка", "Травы", "г"),
    ("Укроп", "Травы", "г"),
    ("Яблоко", "Фрукты", "шт"),
    ("Яйцо", "Яйца и прочее", "шт"),
    ("Сахар", "Яйца и прочее", "г"),
    ("Растительное масло", "Масла и жиры", "мл"),
]

OPERATIONS = {
    "Нарезка": "Измельчение продуктов ножом или другим инструментом.",
    "Варка": "Приготовление в кипящей воде или бульоне.",
    "Жарка": "Приготовление на сковороде с небольшим количеством масла.",
    "Тушение": "Длительное приготовление в небольшом количестве жидкости.",
    "Запекание": "Приготовление в духовом шкафу.",
    "Гриль": "Приготовление на гриле или гриль-панели.",
    "Смешивание": "Соединение продуктов в однородную или неоднородную массу.",
    "Взбивание": "Насыщение массы воздухом при помощи венчика или миксера.",
    "Измельчение": "Превращение продуктов в пюре или мелкую крошку.",
    "Охлаждение": "Выдержка блюда при пониженной температуре.",
}

RECIPE_CATEGORIES = {
    "Супы": "Первые блюда.",
    "Основные блюда": "Горячие блюда на каждый день.",
    "Салаты": "Холодные закуски и салаты.",
    "Выпечка": "Пироги, печенье и другая выпечка.",
    "Десерты": "Сладкие блюда.",
    "Напитки": "Горячие и холодные напитки.",
}


RECIPES = [
    RecipeInput(
        name="Борщ",
        category="Супы",
        servings=4,
        cooking_time_minutes=90,
        description="Классический борщ на говяжьем бульоне со сметаной.",
        ingredients=(
            RecipeIngredientInput("Говядина", 500),
            RecipeIngredientInput("Картофель", 400),
            RecipeIngredientInput("Свёкла", 300),
            RecipeIngredientInput("Капуста белокочанная", 250),
            RecipeIngredientInput("Морковь", 150),
            RecipeIngredientInput("Лук репчатый", 100),
            RecipeIngredientInput("Помидор", 150),
            RecipeIngredientInput("Чеснок", 10),
            RecipeIngredientInput("Сметана", 100),
            RecipeIngredientInput("Соль", 5),
            RecipeIngredientInput("Перец чёрный", 2),
            RecipeIngredientInput("Растительное масло", 30, "мл"),
            RecipeIngredientInput("Петрушка", 10),
        ),
        steps=(
            RecipeStepInput(
                "Нарезка",
                "Нарезать овощи, мясо и зелень.",
                10,
                (
                    "Картофель",
                    "Свёкла",
                    "Капуста белокочанная",
                    "Морковь",
                    "Лук репчатый",
                    "Помидор",
                    "Чеснок",
                    "Петрушка",
                ),
            ),
            RecipeStepInput(
                "Варка",
                "Залить говядину водой и варить до мягкости, снимая пену.",
                50,
                ("Говядина",),
            ),
            RecipeStepInput(
                "Тушение",
                "Тушить свёклу, морковь и лук с растительным маслом.",
                15,
                ("Свёкла", "Морковь", "Лук репчатый", "Растительное масло"),
            ),
            RecipeStepInput(
                "Смешивание",
                "Добавить овощи в бульон, посолить, поперчить и настоять.",
                15,
                (
                    "Картофель",
                    "Капуста белокочанная",
                    "Помидор",
                    "Чеснок",
                    "Соль",
                    "Перец чёрный",
                ),
            ),
        ),
    ),
    RecipeInput(
        name="Паста с курицей и сливками",
        category="Основные блюда",
        servings=2,
        cooking_time_minutes=30,
        description="Сытная паста в сливочном соусе с курицей и сыром.",
        ingredients=(
            RecipeIngredientInput("Макароны", 250),
            RecipeIngredientInput("Куриное филе", 300),
            RecipeIngredientInput("Сливки", 200, "мл"),
            RecipeIngredientInput("Чеснок", 10),
            RecipeIngredientInput("Сыр твёрдый", 50),
            RecipeIngredientInput("Растительное масло", 15, "мл"),
            RecipeIngredientInput("Соль", 3),
            RecipeIngredientInput("Перец чёрный", 1),
        ),
        steps=(
            RecipeStepInput(
                "Нарезка",
                "Нарезать курицу небольшими кусочками, чеснок измельчить.",
                5,
                ("Куриное филе", "Чеснок"),
            ),
            RecipeStepInput(
                "Варка",
                "Отварить макароны до состояния аль денте.",
                10,
                ("Макароны",),
            ),
            RecipeStepInput(
                "Жарка",
                "Обжарить курицу с чесноком до золотистой корочки.",
                10,
                ("Куриное филе", "Чеснок", "Растительное масло"),
            ),
            RecipeStepInput(
                "Смешивание",
                "Добавить сливки и сыр, соединить с макаронами и приправить.",
                5,
                ("Сливки", "Сыр твёрдый", "Соль", "Перец чёрный"),
            ),
        ),
    ),
    RecipeInput(
        name="Овощной салат",
        category="Салаты",
        servings=2,
        cooking_time_minutes=10,
        description="Быстрый летний салат из свежих овощей.",
        ingredients=(
            RecipeIngredientInput("Помидор", 200),
            RecipeIngredientInput("Огурец", 150),
            RecipeIngredientInput("Лук репчатый", 50),
            RecipeIngredientInput("Укроп", 15),
            RecipeIngredientInput("Растительное масло", 20, "мл"),
            RecipeIngredientInput("Соль", 2),
        ),
        steps=(
            RecipeStepInput(
                "Нарезка",
                "Нарезать помидоры, огурцы и лук, порубить укроп.",
                7,
                ("Помидор", "Огурец", "Лук репчатый", "Укроп"),
            ),
            RecipeStepInput(
                "Смешивание",
                "Смешать овощи, заправить маслом и посолить.",
                3,
                ("Растительное масло", "Соль"),
            ),
        ),
    ),
    RecipeInput(
        name="Шарлотка с яблоками",
        category="Выпечка",
        servings=6,
        cooking_time_minutes=50,
        description="Домашний яблочный пирог на яйцах.",
        ingredients=(
            RecipeIngredientInput("Яблоко", 4, "шт"),
            RecipeIngredientInput("Яйцо", 4, "шт"),
            RecipeIngredientInput("Мука", 200),
            RecipeIngredientInput("Сахар", 150),
            RecipeIngredientInput("Сливочное масло", 20),
            RecipeIngredientInput("Соль", 1),
        ),
        steps=(
            RecipeStepInput(
                "Нарезка",
                "Нарезать яблоки тонкими ломтиками.",
                10,
                ("Яблоко",),
            ),
            RecipeStepInput(
                "Взбивание",
                "Взбить яйца с сахаром и солью до пышной массы.",
                10,
                ("Яйцо", "Сахар", "Соль"),
            ),
            RecipeStepInput(
                "Смешивание",
                "Аккуратно вмешать муку и яблоки, смазать форму маслом.",
                5,
                ("Мука", "Яблоко", "Сливочное масло"),
            ),
            RecipeStepInput(
                "Запекание",
                "Выпекать при 180 °C до золотистого цвета.",
                25,
                (),
            ),
        ),
    ),
    RecipeInput(
        name="Крем-суп из тыквы",
        category="Супы",
        servings=3,
        cooking_time_minutes=40,
        description="Бархатистый осенний суп из запечённой тыквы.",
        ingredients=(
            RecipeIngredientInput("Тыква", 600),
            RecipeIngredientInput("Лук репчатый", 100),
            RecipeIngredientInput("Сливки", 150, "мл"),
            RecipeIngredientInput("Сливочное масло", 20),
            RecipeIngredientInput("Соль", 3),
            RecipeIngredientInput("Перец чёрный", 1),
        ),
        steps=(
            RecipeStepInput(
                "Нарезка",
                "Нарезать тыкву и лук крупными кусками.",
                10,
                ("Тыква", "Лук репчатый"),
            ),
            RecipeStepInput(
                "Жарка",
                "Обжарить лук на сливочном масле до прозрачности.",
                5,
                ("Лук репчатый", "Сливочное масло"),
            ),
            RecipeStepInput(
                "Варка",
                "Добавить тыкву и воду, варить до мягкости.",
                15,
                ("Тыква",),
            ),
            RecipeStepInput(
                "Измельчение",
                "Пробить суп блендером до однородности.",
                7,
                ("Тыква", "Лук репчатый"),
            ),
            RecipeStepInput(
                "Смешивание",
                "Влить сливки, посолить и поперчить.",
                3,
                ("Сливки", "Соль", "Перец чёрный"),
            ),
        ),
    ),
    RecipeInput(
        name="Лосось на гриле",
        category="Основные блюда",
        servings=2,
        cooking_time_minutes=25,
        description="Сочный лосось с травами и лёгкой корочкой.",
        ingredients=(
            RecipeIngredientInput("Лосось", 400),
            RecipeIngredientInput("Растительное масло", 15, "мл"),
            RecipeIngredientInput("Соль", 2),
            RecipeIngredientInput("Перец чёрный", 1),
            RecipeIngredientInput("Петрушка", 10),
        ),
        steps=(
            RecipeStepInput(
                "Смешивание",
                "Смешать масло, соль, перец и рубленую петрушку.",
                5,
                ("Растительное масло", "Соль", "Перец чёрный", "Петрушка"),
            ),
            RecipeStepInput(
                "Гриль",
                "Смазать лосось маринадом и готовить на гриле.",
                20,
                ("Лосось",),
            ),
        ),
    ),
]


def seed_database(session: Session) -> SeedResult:
    """Заполнить пустую БД демонстрационными данными.

    Если в БД уже есть рецепты, ничего не меняем — повторный запуск безопасен.
    """

    existing_recipes = session.scalar(select(func.count(Recipe.id))) or 0
    existing_ingredients = session.scalar(select(func.count(Ingredient.id))) or 0
    if existing_recipes or existing_ingredients:
        return SeedResult(
            created=False,
            recipes=existing_recipes,
            ingredients=existing_ingredients,
        )

    catalog = CatalogService(session)
    for name, description in INGREDIENT_CATEGORIES.items():
        catalog.create_ingredient_category(name, description)
    for name, category, unit in INGREDIENTS:
        catalog.create_ingredient(name=name, category=category, default_unit=unit)
    for name, description in OPERATIONS.items():
        catalog.create_operation(name, description)
    for name, description in RECIPE_CATEGORIES.items():
        catalog.create_recipe_category(name, description)

    recipes = RecipeService(session)
    for recipe in RECIPES:
        recipes.create_recipe(recipe)

    return SeedResult(
        created=True,
        recipes=len(RECIPES),
        ingredients=len(INGREDIENTS),
    )
