from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


recipe_step_ingredients = Table(
    "recipe_step_ingredients",
    Base.metadata,
    Column(
        "step_id",
        ForeignKey("recipe_steps.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "recipe_ingredient_id",
        ForeignKey("recipe_ingredients.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class IngredientCategory(Base):
    __tablename__ = "ingredient_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)

    ingredients: Mapped[list[Ingredient]] = relationship(
        back_populates="category",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"IngredientCategory(id={self.id!r}, name={self.name!r})"


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("ingredient_categories.id", ondelete="RESTRICT"),
        index=True,
    )
    default_unit: Mapped[str] = mapped_column(String(20), default="г", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)

    category: Mapped[IngredientCategory] = relationship(
        back_populates="ingredients",
        lazy="joined",
    )
    recipe_links: Mapped[list[RecipeIngredient]] = relationship(
        back_populates="ingredient",
    )

    def __repr__(self) -> str:
        return f"Ingredient(id={self.id!r}, name={self.name!r})"


class RecipeCategory(Base):
    __tablename__ = "recipe_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)

    recipes: Mapped[list[Recipe]] = relationship(back_populates="category")

    def __repr__(self) -> str:
        return f"RecipeCategory(id={self.id!r}, name={self.name!r})"


class Operation(Base):
    __tablename__ = "operations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)

    steps: Mapped[list[RecipeStep]] = relationship(back_populates="operation")

    def __repr__(self) -> str:
        return f"Operation(id={self.id!r}, name={self.name!r})"


class Recipe(Base):
    __tablename__ = "recipes"
    __table_args__ = (
        CheckConstraint("servings > 0", name="ck_recipes_servings_positive"),
        CheckConstraint(
            "cooking_time_minutes > 0",
            name="ck_recipes_cooking_time_positive",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("recipe_categories.id", ondelete="RESTRICT"),
        index=True,
    )
    servings: Mapped[int] = mapped_column(default=1, nullable=False)
    cooking_time_minutes: Mapped[int] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    category: Mapped[RecipeCategory] = relationship(
        back_populates="recipes",
        lazy="joined",
    )
    ingredients: Mapped[list[RecipeIngredient]] = relationship(
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeIngredient.id",
    )
    steps: Mapped[list[RecipeStep]] = relationship(
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="RecipeStep.position",
    )

    def __repr__(self) -> str:
        return f"Recipe(id={self.id!r}, name={self.name!r})"


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"
    __table_args__ = (
        UniqueConstraint(
            "recipe_id",
            "ingredient_id",
            name="uq_recipe_ingredients_recipe_ingredient",
        ),
        CheckConstraint("amount > 0", name="ck_recipe_ingredients_amount_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"),
        index=True,
    )
    ingredient_id: Mapped[int] = mapped_column(
        ForeignKey("ingredients.id", ondelete="RESTRICT"),
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str] = mapped_column(String(200), default="", nullable=False)

    recipe: Mapped[Recipe] = relationship(back_populates="ingredients")
    ingredient: Mapped[Ingredient] = relationship(
        back_populates="recipe_links",
        lazy="joined",
    )
    steps: Mapped[list[RecipeStep]] = relationship(
        secondary=recipe_step_ingredients,
        back_populates="ingredients",
    )

    def __repr__(self) -> str:
        return (
            "RecipeIngredient("
            f"id={self.id!r}, recipe_id={self.recipe_id!r}, "
            f"ingredient_id={self.ingredient_id!r})"
        )


class RecipeStep(Base):
    __tablename__ = "recipe_steps"
    __table_args__ = (
        UniqueConstraint("recipe_id", "position", name="uq_recipe_steps_position"),
        CheckConstraint("position > 0", name="ck_recipe_steps_position_positive"),
        CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes > 0",
            name="ck_recipe_steps_duration_positive",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"),
        index=True,
    )
    position: Mapped[int] = mapped_column(nullable=False)
    operation_id: Mapped[int] = mapped_column(
        ForeignKey("operations.id", ondelete="RESTRICT"),
        index=True,
    )
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    duration_minutes: Mapped[int | None] = mapped_column(nullable=True)

    recipe: Mapped[Recipe] = relationship(back_populates="steps")
    operation: Mapped[Operation] = relationship(
        back_populates="steps",
        lazy="joined",
    )
    ingredients: Mapped[list[RecipeIngredient]] = relationship(
        secondary=recipe_step_ingredients,
        back_populates="steps",
    )

    def __repr__(self) -> str:
        return (
            "RecipeStep("
            f"id={self.id!r}, recipe_id={self.recipe_id!r}, "
            f"position={self.position!r})"
        )