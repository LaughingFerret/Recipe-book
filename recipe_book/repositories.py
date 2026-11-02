from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from .models import (
    Ingredient,
    IngredientCategory,
    Operation,
    Recipe,
    RecipeCategory,
    RecipeIngredient,
    RecipeStep,
)
from .schemas import RecipeSearch


def _recipe_load_options():

    return (
        joinedload(Recipe.category),
        selectinload(Recipe.ingredients)
        .joinedload(RecipeIngredient.ingredient)
        .joinedload(Ingredient.category),
        selectinload(Recipe.steps).joinedload(RecipeStep.operation),
        selectinload(Recipe.steps)
        .selectinload(RecipeStep.ingredients)
        .joinedload(RecipeIngredient.ingredient)
        .joinedload(Ingredient.category),
    )


class CatalogRepository:

    def __init__(self, session: Session) -> None:
        self.session = session

    def ingredient_category_by_name(self, name: str) -> IngredientCategory | None:
        stmt = select(IngredientCategory).where(
            func.lower(IngredientCategory.name) == name.casefold()
        )
        return self.session.scalar(stmt)

    def get_or_create_ingredient_category(
        self, name: str, description: str = ""
    ) -> IngredientCategory:
        category = self.ingredient_category_by_name(name)
        if category is None:
            category = IngredientCategory(name=name, description=description)
            self.session.add(category)
            self.session.flush()
        return category

    def list_ingredient_categories(self) -> list[IngredientCategory]:
        stmt = select(IngredientCategory).order_by(IngredientCategory.name)
        return list(self.session.scalars(stmt))

    def ingredient_by_name(self, name: str) -> Ingredient | None:
        stmt = (
            select(Ingredient)
            .where(func.lower(Ingredient.name) == name.casefold())
            .options(joinedload(Ingredient.category))
        )
        return self.session.scalar(stmt)

    def add_ingredient(
        self,
        *,
        name: str,
        category: IngredientCategory,
        default_unit: str,
        description: str = "",
    ) -> Ingredient:
        ingredient = Ingredient(
            name=name,
            category=category,
            default_unit=default_unit,
            description=description,
        )
        self.session.add(ingredient)
        self.session.flush()
        return ingredient

    def list_ingredients(
        self, *, category: str | None = None, query: str | None = None
    ) -> list[Ingredient]:
        stmt = (
            select(Ingredient)
            .join(Ingredient.category)
            .options(joinedload(Ingredient.category))
        )
        if category:
            stmt = stmt.where(
                func.lower(IngredientCategory.name) == category.casefold()
            )
        if query:
            stmt = stmt.where(
                func.lower(Ingredient.name).contains(query.casefold(), autoescape=True)
            )
        stmt = stmt.order_by(Ingredient.name)
        return list(self.session.scalars(stmt))

    def operation_by_name(self, name: str) -> Operation | None:
        stmt = select(Operation).where(func.lower(Operation.name) == name.casefold())
        return self.session.scalar(stmt)

    def get_or_create_operation(
        self, name: str, description: str = ""
    ) -> Operation:
        operation = self.operation_by_name(name)
        if operation is None:
            operation = Operation(name=name, description=description)
            self.session.add(operation)
            self.session.flush()
        return operation

    def list_operations(self) -> list[Operation]:
        return list(self.session.scalars(select(Operation).order_by(Operation.name)))

    def recipe_category_by_name(self, name: str) -> RecipeCategory | None:
        stmt = select(RecipeCategory).where(
            func.lower(RecipeCategory.name) == name.casefold()
        )
        return self.session.scalar(stmt)

    def get_or_create_recipe_category(
        self, name: str, description: str = ""
    ) -> RecipeCategory:
        category = self.recipe_category_by_name(name)
        if category is None:
            category = RecipeCategory(name=name, description=description)
            self.session.add(category)
            self.session.flush()
        return category

    def list_recipe_categories(self) -> list[RecipeCategory]:
        stmt = select(RecipeCategory).order_by(RecipeCategory.name)
        return list(self.session.scalars(stmt))


class RecipeRepository:

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, recipe: Recipe) -> Recipe:
        self.session.add(recipe)
        self.session.flush()
        return recipe

    def get(self, recipe_id: int) -> Recipe | None:
        stmt = (
            select(Recipe)
            .where(Recipe.id == recipe_id)
            .options(*_recipe_load_options())
        )
        return self.session.scalar(stmt)

    def by_name(self, name: str) -> Recipe | None:
        stmt = (
            select(Recipe)
            .where(func.lower(Recipe.name) == name.casefold())
            .options(*_recipe_load_options())
        )
        return self.session.scalar(stmt)

    def search(self, filters: RecipeSearch) -> list[Recipe]:
        stmt = select(Recipe).options(*_recipe_load_options())

        if filters.query:
            needle = filters.query.casefold()
            stmt = stmt.where(
                or_(
                    func.lower(Recipe.name).contains(needle, autoescape=True),
                    func.lower(Recipe.description).contains(needle, autoescape=True),
                )
            )

        if filters.category:
            stmt = stmt.where(
                Recipe.category.has(
                    func.lower(RecipeCategory.name) == filters.category.casefold()
                )
            )

        if filters.max_cooking_time is not None:
            stmt = stmt.where(
                Recipe.cooking_time_minutes <= filters.max_cooking_time
            )

        if filters.method:
            method = filters.method.casefold()
            stmt = stmt.where(
                Recipe.steps.any(
                    RecipeStep.operation.has(
                        func.lower(Operation.name) == method
                    )
                )
            )

        ingredient_names = [
            name.strip().casefold()
            for name in filters.ingredient_names
            if name and name.strip()
        ]
        if ingredient_names:
            if filters.match_all_ingredients:
                for ingredient_name in ingredient_names:
                    stmt = stmt.where(
                        Recipe.ingredients.any(
                            RecipeIngredient.ingredient.has(
                                func.lower(Ingredient.name) == ingredient_name
                            )
                        )
                    )
            else:
                stmt = stmt.where(
                    Recipe.ingredients.any(
                        RecipeIngredient.ingredient.has(
                            func.lower(Ingredient.name).in_(ingredient_names)
                        )
                    )
                )

        stmt = stmt.order_by(Recipe.cooking_time_minutes, Recipe.name)
        return list(self.session.scalars(stmt))