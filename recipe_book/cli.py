from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path
from typing import Sequence

from sqlalchemy.orm import Session

from .db import Database
from .errors import RecipeBookError
from .schemas import CategoryView, RecipeSearch, RecipeView
from .seed import seed_database
from .services import CatalogService, RecipeService


def _database_url(value: str) -> str:
    if "://" in value:
        return value
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return f"sqlite:///{path.resolve().as_posix()}"


def _format_amount(amount: Decimal) -> str:
    text = format(amount.normalize(), "f")
    return text


def _print_table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> None:
    if not rows:
        print("Ничего не найдено.")
        return
    string_rows = [[str(cell) for cell in row] for row in rows]
    widths = [
        max(len(str(header)), *(len(row[index]) for row in string_rows))
        for index, header in enumerate(headers)
    ]
    print("  ".join(str(header).ljust(widths[index]) for index, header in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for row in string_rows:
        print("  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)))


def _print_categories(title: str, categories: Sequence[CategoryView]) -> None:
    print(title)
    _print_table(
        ["ID", "Название", "Описание"],
        [[item.id, item.name, item.description] for item in categories],
    )
    print()


def _print_operations(service: CatalogService) -> None:
    print("Операции:")
    _print_table(
        ["ID", "Название", "Описание"],
        [
            [item.id, item.name, item.description]
            for item in service.list_operations()
        ],
    )
    print()


def _print_recipes(recipes: Sequence[RecipeView]) -> None:
    if not recipes:
        print("Рецепты не найдены.")
        return
    _print_table(
        ["ID", "Название", "Категория", "Время", "Способы"],
        [
            [
                recipe.id,
                recipe.name,
                recipe.category,
                f"{recipe.cooking_time_minutes} мин",
                ", ".join(recipe.methods),
            ]
            for recipe in recipes
        ],
    )


def _print_recipe(recipe: RecipeView) -> None:
    print(recipe.name)
    print("=" * len(recipe.name))
    print(
        f"Категория: {recipe.category} | "
        f"Порций: {recipe.servings} | "
        f"Время: {recipe.cooking_time_minutes} мин"
    )
    if recipe.description:
        print(f"Описание: {recipe.description}")
    print(f"Способы приготовления: {', '.join(recipe.methods) or '—'}")
    print()
    print("Ингредиенты:")
    for item in recipe.ingredients:
        note = f" — {item.note}" if item.note else ""
        print(
            f"  - {item.name}: {_format_amount(item.amount)} {item.unit} "
            f"[{item.category}]{note}"
        )
    print()
    print("Приготовление:")
    for step in recipe.steps:
        duration = f" — {step.duration_minutes} мин" if step.duration_minutes else ""
        print(f"  {step.position}. {step.operation}{duration}")
        if step.description:
            print(f"     {step.description}")
        if step.ingredients:
            print(f"     Ингредиенты: {', '.join(step.ingredients)}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="recipe-book",
        description="Книга рецептов: ингредиенты, операции, рецепты и поиск.",
    )
    parser.add_argument(
        "--db",
        default="recipe_book.sqlite3",
        help="путь к файлу SQLite или SQLAlchemy URL (по умолчанию recipe_book.sqlite3)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="создать таблицы базы данных")

    seed_parser = subparsers.add_parser(
        "seed", help="заполнить базу демонстрационными данными"
    )
    seed_parser.add_argument(
        "--reset",
        action="store_true",
        help="удалить существующую схему и создать её заново",
    )

    categories_parser = subparsers.add_parser(
        "categories", help="показать категории ингредиентов и рецептов"
    )
    categories_parser.set_defaults()

    category_add_parser = subparsers.add_parser(
        "category-add", help="добавить категорию"
    )
    category_add_parser.add_argument(
        "--kind",
        choices=("ingredient", "recipe"),
        required=True,
        help="тип категории",
    )
    category_add_parser.add_argument("--name", required=True)
    category_add_parser.add_argument("--description", default="")

    ingredients_parser = subparsers.add_parser(
        "ingredients", help="показать ингредиенты"
    )
    ingredients_parser.add_argument("--category", help="фильтр по категории")
    ingredients_parser.add_argument("--query", help="поиск по названию")

    ingredient_add_parser = subparsers.add_parser(
        "ingredient-add", help="добавить ингредиент"
    )
    ingredient_add_parser.add_argument("--name", required=True)
    ingredient_add_parser.add_argument("--category", required=True)
    ingredient_add_parser.add_argument("--unit", default="г")
    ingredient_add_parser.add_argument("--description", default="")

    operations_parser = subparsers.add_parser(
        "operations", help="показать кулинарные операции"
    )
    operations_parser.set_defaults()

    operation_add_parser = subparsers.add_parser(
        "operation-add", help="добавить кулинарную операцию"
    )
    operation_add_parser.add_argument("--name", required=True)
    operation_add_parser.add_argument("--description", default="")

    recipes_parser = subparsers.add_parser("recipes", help="показать все рецепты")
    recipes_parser.set_defaults()

    recipe_show_parser = subparsers.add_parser(
        "recipe-show", help="показать рецепт по ID"
    )
    recipe_show_parser.add_argument("id", type=int)

    search_parser = subparsers.add_parser("search", help="поиск рецептов")
    search_parser.add_argument("--query", help="строка поиска по названию/описанию")
    search_parser.add_argument(
        "--ingredient",
        action="append",
        default=[],
        help="ингредиент; можно указать несколько раз",
    )
    search_parser.add_argument("--category", help="категория рецепта")
    search_parser.add_argument(
        "--max-time",
        type=int,
        help="максимальное время приготовления, минут",
    )
    search_parser.add_argument("--method", help="способ приготовления (жарка, варка...)")
    search_parser.add_argument(
        "--any-ingredients",
        action="store_true",
        help="достаточно любого из указанных ингредиентов (по умолчанию — всех)",
    )

    subparsers.add_parser(
        "gui", help="открыть графический интерфейс"
    )
    return parser


def _dispatch(args: argparse.Namespace, session: Session) -> int:
    catalog = CatalogService(session)
    recipes = RecipeService(session)

    if args.command == "init":
        print("Схема базы данных создана.")
        return 0

    if args.command == "seed":
        result = seed_database(session)
        if result.created:
            print(
                f"Добавлено: ингредиентов — {result.ingredients}, "
                f"рецептов — {result.recipes}."
            )
        else:
            print(
                f"База уже заполнена: рецептов — {result.recipes}, "
                f"ингредиентов — {result.ingredients}. Используйте --reset для пересоздания."
            )
        return 0

    if args.command == "categories":
        _print_categories(
            "Категории ингредиентов:", catalog.list_ingredient_categories()
        )
        _print_categories("Категории рецептов:", catalog.list_recipe_categories())
        _print_operations(catalog)
        return 0

    if args.command == "category-add":
        if args.kind == "ingredient":
            category = catalog.create_ingredient_category(args.name, args.description)
            label = "Категория ингредиентов"
        else:
            category = catalog.create_recipe_category(args.name, args.description)
            label = "Категория рецептов"
        print(f"{label} «{category.name}» создана (ID {category.id}).")
        return 0

    if args.command == "ingredients":
        items = catalog.list_ingredients(
            category=args.category, query=args.query
        )
        _print_table(
            ["ID", "Название", "Категория", "Ед. изм.", "Описание"],
            [
                [item.id, item.name, item.category, item.default_unit, item.description]
                for item in items
            ],
        )
        return 0

    if args.command == "ingredient-add":
        item = catalog.create_ingredient(
            name=args.name,
            category=args.category,
            default_unit=args.unit,
            description=args.description,
        )
        print(
            f"Ингредиент «{item.name}» добавлен в категорию "
            f"«{item.category}» (ID {item.id})."
        )
        return 0

    if args.command == "operations":
        _print_operations(catalog)
        return 0

    if args.command == "operation-add":
        operation = catalog.create_operation(args.name, args.description)
        print(f"Операция «{operation.name}» добавлена (ID {operation.id}).")
        return 0

    if args.command == "recipes":
        _print_recipes(recipes.list_recipes())
        return 0

    if args.command == "recipe-show":
        _print_recipe(recipes.get_recipe(args.id))
        return 0

    if args.command == "search":
        filters = RecipeSearch(
            query=args.query,
            ingredient_names=tuple(args.ingredient),
            category=args.category,
            max_cooking_time=args.max_time,
            method=args.method,
            match_all_ingredients=not args.any_ingredients,
        )
        _print_recipes(recipes.search_recipes(filters))
        return 0

    raise AssertionError(f"Неизвестная команда: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = _build_parser()
    args = parser.parse_args(argv)
    database = Database(_database_url(args.db))
    try:
        if args.command == "seed" and args.reset:
            database.drop_schema()
        database.create_schema()
        if args.command == "gui":
            from .gui import run_gui

            return run_gui(database)
        with database.session_scope() as session:
            return _dispatch(args, session)
    except RecipeBookError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2
    finally:
        database.dispose()
