from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Sequence


@dataclass(frozen=True)
class CategoryView:
    id: int
    name: str
    description: str = ""


@dataclass(frozen=True)
class IngredientView:
    id: int
    name: str
    category: str
    default_unit: str
    description: str = ""


@dataclass(frozen=True)
class OperationView:
    id: int
    name: str
    description: str = ""


@dataclass(frozen=True)
class RecipeIngredientView:
    ingredient_id: int
    name: str
    category: str
    amount: Decimal
    unit: str
    note: str = ""


@dataclass(frozen=True)
class RecipeStepView:
    position: int
    operation: str
    description: str
    duration_minutes: int | None
    ingredients: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecipeView:
    id: int
    name: str
    category: str
    description: str
    servings: int
    cooking_time_minutes: int
    ingredients: tuple[RecipeIngredientView, ...]
    steps: tuple[RecipeStepView, ...]

    @property
    def methods(self) -> tuple[str, ...]:
        """Уникальные способы приготовления в порядке первого появления."""

        return tuple(dict.fromkeys(step.operation for step in self.steps))


@dataclass(frozen=True)
class RecipeIngredientInput:
    ingredient: str
    amount: Decimal | int | float | str
    unit: str | None = None
    note: str = ""


@dataclass(frozen=True)
class RecipeStepInput:
    operation: str
    description: str = ""
    duration_minutes: int | None = None
    ingredients: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecipeInput:
    name: str
    category: str
    ingredients: Sequence[RecipeIngredientInput]
    steps: Sequence[RecipeStepInput]
    servings: int = 1
    cooking_time_minutes: int | None = None
    description: str = ""


@dataclass(frozen=True)
class RecipeSearch:
    query: str | None = None
    ingredient_names: Sequence[str] = field(default_factory=tuple)
    category: str | None = None
    max_cooking_time: int | None = None
    method: str | None = None
    match_all_ingredients: bool = True
