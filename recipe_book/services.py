from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy.orm import Session

from .errors import ConflictError, NotFoundError, ValidationError
from .models import (
    Ingredient,
    IngredientCategory,
    Operation,
    Recipe,
    RecipeCategory,
    RecipeIngredient,
    RecipeStep,
)
from .repositories import CatalogRepository, RecipeRepository
from .schemas import (
    CategoryView,
    IngredientView,
    OperationView,
    RecipeIngredientView,
    RecipeInput,
    RecipeSearch,
    RecipeStepView,
    RecipeView,
)

AMOUNT_QUANT = Decimal("0.001")


def _clean_name(value: str, field: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field}: ожидалась строка.")
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValidationError(f"{field}: значение не может быть пустым.")
    if len(cleaned) > max_length:
        raise ValidationError(
            f"{field}: длина не должна превышать {max_length} символов."
        )
    return cleaned


def _clean_text(value: str | None, field: str, max_length: int) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValidationError(f"{field}: ожидалась строка.")
    cleaned = value.strip()
    if len(cleaned) > max_length:
        raise ValidationError(
            f"{field}: длина не должна превышать {max_length} символов."
        )
    return cleaned


def _positive_int(value: int, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{field}: ожидалось целое число.")
    if value <= 0:
        raise ValidationError(f"{field}: значение должно быть больше нуля.")
    return value


def _amount(value: Decimal | int | float | str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError("Количество ингредиента: ожидалось число.") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise ValidationError(
            "Количество ингредиента: значение должно быть больше нуля."
        )
    if parsed > Decimal("9999999.999"):
        raise ValidationError("Количество ингредиента слишком велико.")
    return parsed.quantize(AMOUNT_QUANT, rounding=ROUND_HALF_UP)


class CatalogService:

    def __init__(self, session: Session) -> None:
        self.session = session
        self.catalog = CatalogRepository(session)

    def create_ingredient_category(
        self, name: str, description: str = ""
    ) -> CategoryView:
        name = _clean_name(name, "Название категории ингредиентов", 100)
        if self.catalog.ingredient_category_by_name(name):
            raise ConflictError(f"Категория ингредиентов «{name}» уже существует.")
        category = IngredientCategory(
            name=name,
            description=_clean_text(description, "Описание категории", 2000),
        )
        self.session.add(category)
        self.session.flush()
        return self._category_view(category)

    def create_recipe_category(
        self, name: str, description: str = ""
    ) -> CategoryView:
        name = _clean_name(name, "Название категории рецептов", 100)
        if self.catalog.recipe_category_by_name(name):
            raise ConflictError(f"Категория рецептов «{name}» уже существует.")
        category = RecipeCategory(
            name=name,
            description=_clean_text(description, "Описание категории", 2000),
        )
        self.session.add(category)
        self.session.flush()
        return self._category_view(category)

    # --- ингредиенты ------------------------------------------------------------

    def create_ingredient(
        self,
        *,
        name: str,
        category: str,
        default_unit: str = "г",
        description: str = "",
    ) -> IngredientView:
        name = _clean_name(name, "Название ингредиента", 120)
        if self.catalog.ingredient_by_name(name):
            raise ConflictError(f"Ингредиент «{name}» уже существует.")

        category_name = _clean_name(category, "Категория ингредиента", 100)
        category_obj = self.catalog.ingredient_category_by_name(category_name)
        if category_obj is None:
            raise NotFoundError(
                f"Категория ингредиентов «{category_name}» не найдена."
            )

        unit = _clean_name(default_unit, "Единица измерения", 20)
        ingredient = self.catalog.add_ingredient(
            name=name,
            category=category_obj,
            default_unit=unit,
            description=_clean_text(description, "Описание ингредиента", 2000),
        )
        return self._ingredient_view(ingredient)

    def list_ingredients(
        self, *, category: str | None = None, query: str | None = None
    ) -> list[IngredientView]:
        category = _clean_text(category, "Категория", 100) or None
        query = _clean_text(query, "Строка поиска", 200) or None
        ingredients = self.catalog.list_ingredients(category=category, query=query)
        return [self._ingredient_view(item) for item in ingredients]

    # --- операции ---------------------------------------------------------------

    def create_operation(self, name: str, description: str = "") -> OperationView:
        name = _clean_name(name, "Название операции", 100)
        if self.catalog.operation_by_name(name):
            raise ConflictError(f"Операция «{name}» уже существует.")
        operation = Operation(
            name=name,
            description=_clean_text(description, "Описание операции", 2000),
        )
        self.session.add(operation)
        self.session.flush()
        return self._operation_view(operation)

    def list_operations(self) -> list[OperationView]:
        return [self._operation_view(item) for item in self.catalog.list_operations()]

    # --- категории: чтение ------------------------------------------------------

    def list_ingredient_categories(self) -> list[CategoryView]:
        return [
            self._category_view(item)
            for item in self.catalog.list_ingredient_categories()
        ]

    def list_recipe_categories(self) -> list[CategoryView]:
        return [
            self._category_view(item)
            for item in self.catalog.list_recipe_categories()
        ]

    # --- преобразование в DTO ---------------------------------------------------

    @staticmethod
    def _category_view(category: IngredientCategory | RecipeCategory) -> CategoryView:
        return CategoryView(
            id=category.id,
            name=category.name,
            description=category.description,
        )

    @staticmethod
    def _ingredient_view(ingredient: Ingredient) -> IngredientView:
        return IngredientView(
            id=ingredient.id,
            name=ingredient.name,
            category=ingredient.category.name,
            default_unit=ingredient.default_unit,
            description=ingredient.description,
        )

    @staticmethod
    def _operation_view(operation: Operation) -> OperationView:
        return OperationView(
            id=operation.id,
            name=operation.name,
            description=operation.description,
        )


class RecipeService:
    """Создание, чтение и поиск рецептов."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.recipes = RecipeRepository(session)
        self.catalog = CatalogRepository(session)

    def create_recipe(self, data: RecipeInput) -> RecipeView:
        name = _clean_name(data.name, "Название рецепта", 150)
        if self.recipes.by_name(name):
            raise ConflictError(f"Рецепт «{name}» уже существует.")

        category_name = _clean_name(data.category, "Категория рецепта", 100)
        category = self.catalog.recipe_category_by_name(category_name)
        if category is None:
            raise NotFoundError(f"Категория рецептов «{category_name}» не найдена.")

        servings = _positive_int(data.servings, "Количество порций")
        description = _clean_text(data.description, "Описание рецепта", 5000)

        if not data.ingredients:
            raise ValidationError("В рецепте должен быть хотя бы один ингредиент.")
        if not data.steps:
            raise ValidationError("В рецепте должен быть хотя бы один шаг.")

        # Сначала проверяем и подготавливаем ингредиенты рецепта.
        prepared_ingredients: list[
            tuple[Ingredient, str, Decimal, str, str]
        ] = []
        seen_ingredients: set[str] = set()
        for item in data.ingredients:
            ingredient_name = _clean_name(
                item.ingredient, "Название ингредиента", 120
            )
            key = ingredient_name.casefold()
            if key in seen_ingredients:
                raise ValidationError(
                    f"Ингредиент «{ingredient_name}» указан в рецепте дважды."
                )
            seen_ingredients.add(key)

            ingredient = self.catalog.ingredient_by_name(ingredient_name)
            if ingredient is None:
                raise NotFoundError(
                    f"Ингредиент «{ingredient_name}» не найден в справочнике."
                )

            amount = _amount(item.amount)
            unit = _clean_name(
                item.unit or ingredient.default_unit, "Единица измерения", 20
            )
            note = _clean_text(item.note, "Примечание", 200)
            prepared_ingredients.append(
                (ingredient, ingredient_name, amount, unit, note)
            )

        recipe = Recipe(
            name=name,
            category=category,
            description=description,
            servings=servings,
            cooking_time_minutes=1,  # временно; ниже вычисляется/проверяется
        )

        # ORM-объекты ингредиентов рецепта; по ним разрешаются ссылки в шагах.
        links_by_name: dict[str, RecipeIngredient] = {}
        for ingredient, ingredient_name, amount, unit, note in prepared_ingredients:
            link = RecipeIngredient(
                ingredient=ingredient,
                amount=amount,
                unit=unit,
                note=note,
            )
            recipe.ingredients.append(link)
            links_by_name[ingredient_name.casefold()] = link

        total_duration = 0
        durations_present = False
        for position, step_data in enumerate(data.steps, start=1):
            operation_name = _clean_name(
                step_data.operation, "Название операции", 100
            )
            operation = self.catalog.operation_by_name(operation_name)
            if operation is None:
                raise NotFoundError(f"Операция «{operation_name}» не найдена.")

            description_step = _clean_text(
                step_data.description, "Описание шага", 2000
            )
            duration = step_data.duration_minutes
            if duration is not None:
                duration = _positive_int(duration, "Длительность шага")
                total_duration += duration
                durations_present = True

            step_ingredient_names: list[str] = []
            seen_step_ingredients: set[str] = set()
            for raw_name in step_data.ingredients:
                ingredient_name = _clean_name(
                    raw_name, "Ингредиент шага", 120
                )
                key = ingredient_name.casefold()
                if key not in links_by_name:
                    raise ValidationError(
                        f"Ингредиент «{ingredient_name}» из шага {position} "
                        "не указан в составе рецепта."
                    )
                if key in seen_step_ingredients:
                    raise ValidationError(
                        f"Ингредиент «{ingredient_name}» указан в шаге {position} дважды."
                    )
                seen_step_ingredients.add(key)
                step_ingredient_names.append(key)

            step = RecipeStep(
                position=position,
                operation=operation,
                description=description_step,
                duration_minutes=duration,
            )
            step.ingredients = [
                links_by_name[ingredient_key]
                for ingredient_key in step_ingredient_names
            ]
            recipe.steps.append(step)

        if data.cooking_time_minutes is None:
            if not durations_present:
                raise ValidationError(
                    "Укажите общее время приготовления или длительность шагов."
                )
            cooking_time = total_duration
        else:
            cooking_time = _positive_int(
                data.cooking_time_minutes, "Время приготовления"
            )
        recipe.cooking_time_minutes = cooking_time

        self.recipes.add(recipe)
        return self._recipe_view(recipe)

    def get_recipe(self, recipe_id: int) -> RecipeView:
        if isinstance(recipe_id, bool) or not isinstance(recipe_id, int):
            raise ValidationError("ID рецепта: ожидалось целое число.")
        recipe = self.recipes.get(recipe_id)
        if recipe is None:
            raise NotFoundError(f"Рецепт с ID {recipe_id} не найден.")
        return self._recipe_view(recipe)

    def list_recipes(self) -> list[RecipeView]:
        return [self._recipe_view(item) for item in self.recipes.search(RecipeSearch())]

    def search_recipes(self, filters: RecipeSearch) -> list[RecipeView]:
        if filters.max_cooking_time is not None:
            _positive_int(filters.max_cooking_time, "Максимальное время приготовления")
        query = _clean_text(filters.query, "Строка поиска", 200) or None
        category = _clean_text(filters.category, "Категория", 100) or None
        method = _clean_text(filters.method, "Способ приготовления", 100) or None
        ingredient_names = tuple(
            _clean_name(name, "Ингредиент для поиска", 120)
            for name in filters.ingredient_names
            if name and str(name).strip()
        )
        normalized_filters = RecipeSearch(
            query=query,
            ingredient_names=ingredient_names,
            category=category,
            max_cooking_time=filters.max_cooking_time,
            method=method,
            match_all_ingredients=filters.match_all_ingredients,
        )
        recipes = self.recipes.search(normalized_filters)
        return [self._recipe_view(item) for item in recipes]

    @staticmethod
    def _recipe_view(recipe: Recipe) -> RecipeView:
        ingredients = tuple(
            RecipeIngredientView(
                ingredient_id=link.ingredient.id,
                name=link.ingredient.name,
                category=link.ingredient.category.name,
                amount=link.amount,
                unit=link.unit,
                note=link.note,
            )
            for link in recipe.ingredients
        )
        steps = tuple(
            RecipeStepView(
                position=step.position,
                operation=step.operation.name,
                description=step.description,
                duration_minutes=step.duration_minutes,
                ingredients=tuple(
                    sorted(link.ingredient.name for link in step.ingredients)
                ),
            )
            for step in recipe.steps
        )
        return RecipeView(
            id=recipe.id,
            name=recipe.name,
            category=recipe.category.name,
            description=recipe.description,
            servings=recipe.servings,
            cooking_time_minutes=recipe.cooking_time_minutes,
            ingredients=ingredients,
            steps=steps,
        )
