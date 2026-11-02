from __future__ import annotations

import argparse
import sys
import tkinter as tk
from decimal import Decimal
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Callable, Sequence

from .db import Database
from .errors import RecipeBookError
from .schemas import (
    RecipeIngredientInput,
    RecipeInput,
    RecipeSearch,
    RecipeStepInput,
    RecipeView,
)
from .seed import seed_database
from .services import CatalogService, RecipeService


APP_TITLE = "Книга рецептов"
BG = "#f4f7fa"
ACCENT = "#1f4e79"


def format_amount(value: Any) -> str:
    text = format(Decimal(str(value)), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",")


def optional_int(text: str, field: str) -> int | None:
    text = text.strip()
    if not text:
        return None
    try:
        value = int(text)
    except ValueError as exc:
        raise ValueError(f"{field}: нужно целое число.") from exc
    if value <= 0:
        raise ValueError(f"{field}: значение должно быть больше нуля.")
    return value


def required_int(text: str, field: str) -> int:
    value = optional_int(text, field)
    if value is None:
        raise ValueError(f"{field}: значение не может быть пустым.")
    return value


def split_ingredients(text: str) -> tuple[str, ...]:
    parts = text.replace(";", ",").split(",")
    return tuple(part.strip() for part in parts if part.strip())


def attach_scrollbars(
    parent: tk.Misc, widget: tk.Widget
) -> tuple[ttk.Scrollbar, ttk.Scrollbar]:
    vertical = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=widget.yview)
    horizontal = ttk.Scrollbar(parent, orient=tk.HORIZONTAL, command=widget.xview)
    widget.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
    return vertical, horizontal


def make_tree(
    parent: tk.Misc,
    columns: Sequence[tuple[str, str, int]],
    *,
    height: int = 10,
) -> ttk.Treeview:
    tree = ttk.Treeview(
        parent,
        columns=[item[0] for item in columns],
        show="headings",
        height=height,
        selectmode="browse",
    )
    for key, title, width in columns:
        tree.heading(key, text=title)
        tree.column(key, width=width, minwidth=45, stretch=key == columns[-1][0])
    return tree


class RecipeBookApp(tk.Tk):

    def __init__(self, database: Database) -> None:
        super().__init__()
        self.database = database
        self.title(APP_TITLE)
        self.configure(bg=BG)
        self.minsize(1040, 680)
        self._configure_style()
        self._center_window()
        self._build_menu()
        self._build_header()
        self.status_var = tk.StringVar(value="Подключено")

        status = tk.Label(
            self,
            textvariable=self.status_var,
            anchor="w",
            bg="#e8eef5",
            fg="#40566b",
            padx=10,
            pady=4,
        )
        status.pack(fill=tk.X, side=tk.BOTTOM)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 6))

        self.recipes_tab = RecipesTab(self.notebook, self)
        self.new_recipe_tab = NewRecipeTab(self.notebook, self)
        self.catalog_tab = CatalogTab(self.notebook, self)
        self.notebook.add(self.recipes_tab, text="  Рецепты  ")
        self.notebook.add(self.new_recipe_tab, text="  Новый рецепт  ")
        self.notebook.add(self.catalog_tab, text="  Справочники  ")

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<F5>", lambda _event: self.refresh_all())
        self.after(180, self._initial_load)

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10))
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground="#172a3a")
        style.configure("TLabelframe", background=BG)
        style.configure("TLabelframe.Label", background=BG, foreground=ACCENT,
                        font=("Segoe UI", 10, "bold"))
        style.configure("TButton", padding=(10, 5))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("Treeview", rowheight=26, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        style.configure("TNotebook.Tab", padding=(14, 7), font=("Segoe UI", 10))
        style.map("TNotebook.Tab", background=[("selected", "#ffffff")])

    def _center_window(self) -> None:
        width = min(1240, self.winfo_screenwidth() - 70)
        height = min(800, self.winfo_screenheight() - 90)
        x = max(0, (self.winfo_screenwidth() - width) // 2)
        y = max(0, (self.winfo_screenheight() - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=BG)
        header.pack(fill=tk.X, padx=16, pady=(12, 4))
        tk.Label(
            header,
            text="Книга рецептов",
            font=("Segoe UI", 22, "bold"),
            fg=ACCENT,
            bg=BG,
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Python 3.12 · SQLAlchemy · SQLite · ингредиенты, операции и поиск",
            font=("Segoe UI", 9),
            fg="#5a6470",
            bg=BG,
            anchor="w",
        ).pack(anchor="w", pady=(2, 0))

    def _build_menu(self) -> None:
        menu = tk.Menu(self)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Обновить всё", accelerator="F5",
                              command=self.refresh_all)
        file_menu.add_command(label="Загрузить демо-данные",
                              command=self.load_demo_data)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.destroy)
        menu.add_cascade(label="Файл", menu=file_menu)

        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="О программе", command=self.show_about)
        menu.add_cascade(label="Справка", menu=help_menu)
        self.configure(menu=menu)

    def read(self, operation: Callable[[RecipeService, CatalogService], Any]) -> Any:
        with self.database.session_scope() as session:
            return operation(RecipeService(session), CatalogService(session))

    def write(self, operation: Callable[[RecipeService, CatalogService], Any]) -> Any:
        with self.database.session_scope() as session:
            return operation(RecipeService(session), CatalogService(session))

    def status(self, message: str) -> None:
        self.status_var.set(message)

    def report_error(self, error: Exception) -> None:
        self.status(f"Ошибка: {error}")
        messagebox.showerror("Ошибка", str(error), parent=self)

    def show_about(self) -> None:
        messagebox.showinfo(
            "О программе",
            "Книга рецептов\n"
            "Вариант 2: ингредиенты, операции, рецепты и поиск.\n\n"
            "Python 3.12 · SQLAlchemy 2.0 · SQLite\n"
            "Графический интерфейс: Tkinter/ttk",
            parent=self,
        )

    def select_tab(self, index: int) -> None:
        self.notebook.select(index)
        if index == 1:
            self.new_recipe_tab.refresh_catalog()

    def _initial_load(self) -> None:
        try:
            data = self.read(
                lambda recipes, catalog: (
                    len(recipes.list_recipes()),
                    len(catalog.list_ingredients()),
                    len(catalog.list_recipe_categories()),
                )
            )
            if data == (0, 0, 0):
                if messagebox.askyesno(
                    "Пустая база",
                    "В базе пока нет данных. Заполнить её демонстрационными "
                    "ингредиентами и рецептами?",
                    parent=self,
                ):
                    self.load_demo_data()
                    return
            self.refresh_all()
        except Exception as exc:
            self.report_error(exc)

    def refresh_all(self) -> None:
        try:
            self.recipes_tab.refresh()
            self.new_recipe_tab.refresh_catalog()
            self.catalog_tab.refresh()
            self.status("Данные обновлены")
        except Exception as exc:
            self.report_error(exc)

    def load_demo_data(self) -> None:
        try:
            with self.database.session_scope() as session:
                result = seed_database(session)
            if result.created:
                messagebox.showinfo(
                    "Демо-данные",
                    f"Добавлено ингредиентов: {result.ingredients}, "
                    f"рецептов: {result.recipes}.",
                    parent=self,
                )
            else:
                messagebox.showinfo(
                    "Демо-данные",
                    "База уже содержит данные; повторное заполнение не требуется.",
                    parent=self,
                )
            self.refresh_all()
        except Exception as exc:
            self.report_error(exc)


class RecipeResultsView(ttk.Panedwindow):

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, orient=tk.VERTICAL)
        self._recipes: dict[str, RecipeView] = {}

        tree_frame = ttk.Frame(self)
        self.tree = make_tree(
            tree_frame,
            [
                ("id", "ID", 55),
                ("name", "Название", 250),
                ("category", "Категория", 150),
                ("time", "Время", 80),
                ("servings", "Порций", 70),
                ("methods", "Способы", 230),
            ],
            height=9,
        )
        vertical, horizontal = attach_scrollbars(tree_frame, self.tree)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        self.add(tree_frame, weight=3)

        detail_frame = ttk.LabelFrame(self, text="Карточка рецепта")
        self.detail = tk.Text(
            detail_frame,
            height=11,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("Segoe UI", 10),
            padx=10,
            pady=8,
            background="#ffffff",
            relief=tk.FLAT,
        )
        detail_scroll = ttk.Scrollbar(detail_frame, orient=tk.VERTICAL,
                                      command=self.detail.yview)
        self.detail.configure(yscrollcommand=detail_scroll.set)
        self.detail.grid(row=0, column=0, sticky="nsew")
        detail_scroll.grid(row=0, column=1, sticky="ns")
        detail_frame.rowconfigure(0, weight=1)
        detail_frame.columnconfigure(0, weight=1)
        self.detail.tag_configure("title", font=("Segoe UI", 16, "bold"),
                                  foreground=ACCENT)
        self.detail.tag_configure("heading", font=("Segoe UI", 10, "bold"),
                                  foreground="#172a3a", spacing1=8)
        self.detail.tag_configure("muted", foreground="#5a6470")
        self.add(detail_frame, weight=2)

        self.tree.bind("<<TreeviewSelect>>", self._on_select)

    def set_recipes(self, recipes: Sequence[RecipeView]) -> None:
        self._recipes = {str(recipe.id): recipe for recipe in recipes}
        for item in self.tree.get_children():
            self.tree.delete(item)
        for recipe in recipes:
            self.tree.insert(
                "",
                tk.END,
                iid=str(recipe.id),
                values=(
                    recipe.id,
                    recipe.name,
                    recipe.category,
                    f"{recipe.cooking_time_minutes} мин",
                    recipe.servings,
                    ", ".join(recipe.methods),
                ),
            )
        if recipes:
            first = str(recipes[0].id)
            self.tree.selection_set(first)
            self.tree.focus(first)
            self.tree.see(first)
            self._show(recipes[0])
        else:
            self._show_empty()

    def _on_select(self, _event: tk.Event) -> None:
        selected = self.tree.selection()
        if selected:
            recipe = self._recipes.get(selected[0])
            if recipe is not None:
                self._show(recipe)

    def _show_empty(self) -> None:
        self.detail.configure(state=tk.NORMAL)
        self.detail.delete("1.0", tk.END)
        self.detail.insert(tk.END, "Рецепты не найдены.", "muted")
        self.detail.configure(state=tk.DISABLED)

    def _show(self, recipe: RecipeView) -> None:
        self.detail.configure(state=tk.NORMAL)
        self.detail.delete("1.0", tk.END)
        self.detail.insert(tk.END, recipe.name + "\n", "title")
        self.detail.insert(
            tk.END,
            f"{recipe.category} · {recipe.servings} порц. · "
            f"{recipe.cooking_time_minutes} мин\n",
            "muted",
        )
        if recipe.description:
            self.detail.insert(tk.END, recipe.description + "\n")
        self.detail.insert(tk.END, "\nСпособы приготовления: ", "heading")
        self.detail.insert(tk.END, ", ".join(recipe.methods) or "—")

        self.detail.insert(tk.END, "\n\nИнгредиенты\n", "heading")
        for item in recipe.ingredients:
            line = (f"  • {item.name} — {format_amount(item.amount)} "
                    f"{item.unit}  [{item.category}]")
            if item.note:
                line += f"  ({item.note})"
            self.detail.insert(tk.END, line + "\n")

        self.detail.insert(tk.END, "\nПриготовление\n", "heading")
        for step in recipe.steps:
            duration = f" — {step.duration_minutes} мин" if step.duration_minutes else ""
            self.detail.insert(tk.END,
                               f"  {step.position}. {step.operation}{duration}\n")
            if step.description:
                self.detail.insert(tk.END, f"     {step.description}\n", "muted")
            if step.ingredients:
                self.detail.insert(
                    tk.END,
                    f"     Ингредиенты: {', '.join(step.ingredients)}\n",
                    "muted",
                )
        self.detail.configure(state=tk.DISABLED)
        self.detail.yview_moveto(0)


class RecipesTab(ttk.Frame):
    def __init__(self, parent: tk.Misc, app: RecipeBookApp) -> None:
        super().__init__(parent)
        self.app = app
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self._build_filters()
        self.results = RecipeResultsView(self)
        self.results.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        self.refresh()

    def _build_filters(self) -> None:
        box = ttk.LabelFrame(self, text="Поиск рецептов")
        box.grid(row=0, column=0, sticky="ew", pady=(8, 0))
        for column in (1, 3, 5, 7):
            box.columnconfigure(column, weight=1)

        self.query_var = tk.StringVar()
        self.ingredients_var = tk.StringVar()
        self.category_var = tk.StringVar(value="Все")
        self.method_var = tk.StringVar(value="Все")
        self.max_time_var = tk.StringVar()
        self.match_all_var = tk.BooleanVar(value=True)

        ttk.Label(box, text="Название / описание:").grid(
            row=0, column=0, sticky="w", padx=(8, 4), pady=5)
        ttk.Entry(box, textvariable=self.query_var, width=28).grid(
            row=0, column=1, sticky="ew", padx=(0, 12), pady=5)
        ttk.Label(box, text="Ингредиенты через запятую:").grid(
            row=0, column=2, sticky="w", padx=(0, 4), pady=5)
        ttk.Entry(box, textvariable=self.ingredients_var, width=32).grid(
            row=0, column=3, sticky="ew", padx=(0, 12), pady=5)
        ttk.Label(box, text="Макс. время, мин:").grid(
            row=0, column=4, sticky="w", padx=(0, 4), pady=5)
        ttk.Entry(box, textvariable=self.max_time_var, width=8).grid(
            row=0, column=5, sticky="w", padx=(0, 12), pady=5)

        ttk.Label(box, text="Категория:").grid(
            row=1, column=0, sticky="w", padx=(8, 4), pady=5)
        self.category_combo = ttk.Combobox(
            box, textvariable=self.category_var, state="readonly", width=24)
        self.category_combo.grid(row=1, column=1, sticky="w", pady=5)
        ttk.Label(box, text="Способ:").grid(
            row=1, column=2, sticky="w", padx=(0, 4), pady=5)
        self.method_combo = ttk.Combobox(
            box, textvariable=self.method_var, state="readonly", width=24)
        self.method_combo.grid(row=1, column=3, sticky="w", pady=5)
        ttk.Checkbutton(
            box,
            text="Нужны все указанные ингредиенты",
            variable=self.match_all_var,
        ).grid(row=1, column=4, columnspan=2, sticky="w", padx=(0, 8), pady=5)

        actions = ttk.Frame(box)
        actions.grid(row=2, column=0, columnspan=8, sticky="e", padx=8,
                     pady=(0, 6))
        ttk.Button(actions, text="Найти", style="Accent.TButton",
                   command=self.search).pack(side=tk.LEFT)
        ttk.Button(actions, text="Сбросить", command=self.reset).pack(
            side=tk.LEFT, padx=(6, 0))
        ttk.Button(actions, text="Добавить рецепт",
                   command=lambda: self.app.select_tab(1)).pack(
            side=tk.LEFT, padx=(6, 0))

    def refresh_filters(self) -> None:
        data = self.app.read(
            lambda _recipes, catalog: (
                [item.name for item in catalog.list_recipe_categories()],
                [item.name for item in catalog.list_operations()],
            )
        )
        categories, methods = data
        self.category_combo["values"] = ["Все", *categories]
        self.method_combo["values"] = ["Все", *methods]
        if self.category_var.get() not in self.category_combo["values"]:
            self.category_var.set("Все")
        if self.method_var.get() not in self.method_combo["values"]:
            self.method_var.set("Все")

    def build_filters(self) -> RecipeSearch:
        return RecipeSearch(
            query=self.query_var.get().strip() or None,
            ingredient_names=split_ingredients(self.ingredients_var.get()),
            category=(
                None
                if self.category_var.get() in ("", "Все")
                else self.category_var.get()
            ),
            max_cooking_time=optional_int(
                self.max_time_var.get(), "Максимальное время"),
            method=(
                None
                if self.method_var.get() in ("", "Все")
                else self.method_var.get()
            ),
            match_all_ingredients=self.match_all_var.get(),
        )

    def search(self) -> None:
        try:
            filters = self.build_filters()
            recipes = self.app.read(
                lambda service, _catalog: service.search_recipes(filters)
            )
            self.results.set_recipes(recipes)
            self.app.status(f"Найдено рецептов: {len(recipes)}")
        except (ValueError, RecipeBookError) as exc:
            self.app.report_error(exc)
        except Exception as exc:
            self.app.report_error(exc)

    def reset(self) -> None:
        self.query_var.set("")
        self.ingredients_var.set("")
        self.category_var.set("Все")
        self.method_var.set("Все")
        self.max_time_var.set("")
        self.match_all_var.set(True)
        self.search()

    def refresh(self) -> None:
        self.refresh_filters()
        self.search()


class NewRecipeTab(ttk.Frame):
    def __init__(self, parent: tk.Misc, app: RecipeBookApp) -> None:
        super().__init__(parent)
        self.app = app
        self._ingredients: list[dict[str, Any]] = []
        self._steps: list[dict[str, Any]] = []
        self._ingredient_units: dict[str, str] = {}
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self._build_info()
        self._build_body()
        self._build_actions()
        self.refresh_catalog()

    def _build_info(self) -> None:
        box = ttk.LabelFrame(self, text="Основное")
        box.grid(row=0, column=0, sticky="ew", pady=(8, 0))
        box.columnconfigure(1, weight=1)
        box.columnconfigure(3, weight=1)

        self.name_var = tk.StringVar()
        self.category_var = tk.StringVar()
        self.servings_var = tk.StringVar(value="2")
        self.time_var = tk.StringVar()

        ttk.Label(box, text="Название:").grid(
            row=0, column=0, sticky="w", padx=(8, 4), pady=5)
        ttk.Entry(box, textvariable=self.name_var).grid(
            row=0, column=1, sticky="ew", padx=(0, 12), pady=5)
        ttk.Label(box, text="Категория:").grid(
            row=0, column=2, sticky="w", padx=(0, 4), pady=5)
        self.category_combo = ttk.Combobox(
            box, textvariable=self.category_var, state="readonly")
        self.category_combo.grid(row=0, column=3, sticky="ew", padx=(0, 8), pady=5)

        ttk.Label(box, text="Порций:").grid(
            row=1, column=0, sticky="w", padx=(8, 4), pady=5)
        ttk.Entry(box, textvariable=self.servings_var, width=10).grid(
            row=1, column=1, sticky="w", pady=5)
        ttk.Label(box, text="Общее время, мин (пусто = сумма шагов):").grid(
            row=1, column=2, sticky="w", padx=(0, 4), pady=5)
        ttk.Entry(box, textvariable=self.time_var, width=10).grid(
            row=1, column=3, sticky="w", pady=5)

        ttk.Label(box, text="Описание:").grid(
            row=2, column=0, sticky="nw", padx=(8, 4), pady=5)
        self.description = tk.Text(
            box, height=3, wrap=tk.WORD, font=("Segoe UI", 10),
            relief=tk.SOLID, borderwidth=1)
        self.description.grid(row=2, column=1, columnspan=3, sticky="nsew",
                              padx=(0, 8), pady=5)

    def _build_body(self) -> None:
        body = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        body.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        self._build_ingredients(body)
        self._build_steps(body)

    def _build_ingredients(self, parent: ttk.Panedwindow) -> None:
        frame = ttk.LabelFrame(parent, text="Состав рецепта")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        form = ttk.Frame(frame)
        form.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 2))
        form.columnconfigure(0, weight=1)

        self.ingredient_var = tk.StringVar()
        self.ingredient_combo = ttk.Combobox(
            form, textvariable=self.ingredient_var, state="readonly")
        self.ingredient_combo.grid(row=0, column=0, sticky="ew")
        self.ingredient_combo.bind("<<ComboboxSelected>>",
                                   self._on_ingredient_selected)

        line = ttk.Frame(frame)
        line.grid(row=1, column=0, sticky="ew", padx=8, pady=2)
        line.columnconfigure(1, weight=1)
        ttk.Label(line, text="Кол-во:").grid(row=0, column=0, padx=(0, 4))
        self.amount_var = tk.StringVar()
        ttk.Entry(line, textvariable=self.amount_var, width=8).grid(
            row=0, column=1, sticky="w")
        ttk.Label(line, text="Ед.:").grid(row=0, column=2, padx=(8, 4))
        self.unit_var = tk.StringVar(value="г")
        ttk.Entry(line, textvariable=self.unit_var, width=6).grid(
            row=0, column=3, sticky="w")
        ttk.Label(line, text="Примечание:").grid(row=0, column=4, padx=(8, 4))
        self.note_var = tk.StringVar()
        ttk.Entry(line, textvariable=self.note_var).grid(
            row=0, column=5, sticky="ew")
        ttk.Button(line, text="Добавить", command=self.add_ingredient).grid(
            row=0, column=6, padx=(8, 0))

        table = ttk.Frame(frame)
        table.grid(row=2, column=0, sticky="nsew", padx=8, pady=4)
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)
        self.ingredient_tree = make_tree(
            table,
            [("name", "Ингредиент", 170),
             ("amount", "Кол-во", 70),
             ("unit", "Ед.", 55),
             ("note", "Примечание", 150)],
            height=7,
        )
        vertical, horizontal = attach_scrollbars(table, self.ingredient_tree)
        self.ingredient_tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        ttk.Button(frame, text="Удалить ингредиент",
                   command=self.remove_ingredient).grid(
            row=3, column=0, sticky="w", padx=8, pady=(0, 8))
        parent.add(frame, weight=1)

    def _build_steps(self, parent: ttk.Panedwindow) -> None:
        frame = ttk.LabelFrame(parent, text="Шаги приготовления")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)

        top = ttk.Frame(frame)
        top.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 2))
        top.columnconfigure(1, weight=1)
        self.operation_var = tk.StringVar()
        self.operation_combo = ttk.Combobox(
            top, textvariable=self.operation_var, state="readonly")
        self.operation_combo.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.step_duration_var = tk.StringVar()
        ttk.Label(top, text="Длительность, мин:").grid(
            row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Entry(top, textvariable=self.step_duration_var, width=8).grid(
            row=1, column=1, sticky="w", pady=(4, 0))
        self.step_description_var = tk.StringVar()
        ttk.Label(top, text="Описание:").grid(
            row=2, column=0, sticky="w", pady=(4, 0))
        ttk.Entry(top, textvariable=self.step_description_var).grid(
            row=2, column=1, sticky="ew", pady=(4, 0))

        pick = ttk.Frame(frame)
        pick.grid(row=1, column=0, sticky="ew", padx=8, pady=4)
        pick.columnconfigure(0, weight=1)
        ttk.Label(pick, text="Ингредиенты шага (Ctrl+клик):").grid(
            row=0, column=0, sticky="w")
        self.step_ingredient_list = tk.Listbox(
            pick, height=4, selectmode=tk.MULTIPLE, exportselection=False,
            font=("Segoe UI", 9), relief=tk.SOLID, borderwidth=1)
        self.step_ingredient_list.grid(row=1, column=0, sticky="ew")
        ttk.Button(pick, text="Добавить шаг", command=self.add_step).grid(
            row=1, column=1, padx=(8, 0), sticky="s")

        table = ttk.Frame(frame)
        table.grid(row=2, column=0, sticky="nsew", padx=8, pady=4)
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)
        self.step_tree = make_tree(
            table,
            [("n", "№", 35),
             ("operation", "Операция", 120),
             ("duration", "Мин", 55),
             ("description", "Описание", 190),
             ("ingredients", "Ингредиенты", 170)],
            height=7,
        )
        vertical, horizontal = attach_scrollbars(table, self.step_tree)
        self.step_tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        ttk.Button(frame, text="Удалить шаг", command=self.remove_step).grid(
            row=3, column=0, sticky="w", padx=8, pady=(0, 8))
        parent.add(frame, weight=1)

    def _build_actions(self) -> None:
        actions = ttk.Frame(self)
        actions.grid(row=2, column=0, sticky="ew", pady=8)
        ttk.Button(actions, text="Сохранить рецепт", style="Accent.TButton",
                   command=self.save).pack(side=tk.LEFT)
        ttk.Button(actions, text="Очистить форму", command=self.reset).pack(
            side=tk.LEFT, padx=(8, 0))
        ttk.Label(
            actions,
            text="Категории, ингредиенты и операции можно добавить во вкладке "
                 "«Справочники».",
        ).pack(side=tk.RIGHT)

    def refresh_catalog(self) -> None:
        try:
            categories, operations, ingredients = self.app.read(
                lambda _recipes, catalog: (
                    [item.name for item in catalog.list_recipe_categories()],
                    [item.name for item in catalog.list_operations()],
                    catalog.list_ingredients(),
                )
            )
        except Exception as exc:
            self.app.report_error(exc)
            return

        self.category_combo["values"] = categories
        self.operation_combo["values"] = operations
        self._ingredient_units = {item.name: item.default_unit for item in ingredients}
        ingredient_names = list(self._ingredient_units)
        self.ingredient_combo["values"] = ingredient_names
        if self.category_var.get() not in categories:
            self.category_var.set(categories[0] if categories else "")
        if self.operation_var.get() not in operations:
            self.operation_var.set(operations[0] if operations else "")
        if self.ingredient_var.get() not in ingredient_names:
            self.ingredient_var.set(ingredient_names[0] if ingredient_names else "")
            self._on_ingredient_selected()
        self._refresh_step_ingredient_list()

    def _on_ingredient_selected(self, _event: tk.Event | None = None) -> None:
        unit = self._ingredient_units.get(self.ingredient_var.get(), "г")
        self.unit_var.set(unit)

    def _refresh_step_ingredient_list(self) -> None:
        self.step_ingredient_list.delete(0, tk.END)
        for item in self._ingredients:
            self.step_ingredient_list.insert(tk.END, item["name"])

    def _refresh_ingredient_tree(self) -> None:
        for item in self.ingredient_tree.get_children():
            self.ingredient_tree.delete(item)
        for index, item in enumerate(self._ingredients):
            self.ingredient_tree.insert(
                "", tk.END, iid=str(index),
                values=(item["name"], format_amount(item["amount"]),
                        item["unit"], item["note"]),
            )

    def _refresh_step_tree(self) -> None:
        for item in self.step_tree.get_children():
            self.step_tree.delete(item)
        for index, step in enumerate(self._steps):
            self.step_tree.insert(
                "", tk.END, iid=str(index),
                values=(index + 1, step["operation"],
                        step["duration"] or "—", step["description"],
                        ", ".join(step["ingredients"])),
            )

    def add_ingredient(self) -> None:
        name = self.ingredient_var.get().strip()
        amount = self.amount_var.get().strip()
        if not name:
            messagebox.showwarning("Состав", "Выберите ингредиент.", parent=self)
            return
        if not amount:
            messagebox.showwarning("Состав", "Укажите количество.", parent=self)
            return
        if any(item["name"].casefold() == name.casefold()
               for item in self._ingredients):
            messagebox.showwarning("Состав", "Этот ингредиент уже добавлен.",
                                   parent=self)
            return
        self._ingredients.append({
            "name": name,
            "amount": amount,
            "unit": self.unit_var.get().strip() or "г",
            "note": self.note_var.get().strip(),
        })
        self.amount_var.set("")
        self.note_var.set("")
        self._refresh_ingredient_tree()
        self._refresh_step_ingredient_list()

    def remove_ingredient(self) -> None:
        selected = self.ingredient_tree.selection()
        if not selected:
            return
        index = int(selected[0])
        name = self._ingredients[index]["name"]
        if any(name in step["ingredients"] for step in self._steps):
            messagebox.showwarning(
                "Состав",
                "Ингредиент используется в шаге. Сначала удалите шаг.",
                parent=self,
            )
            return
        del self._ingredients[index]
        self._refresh_ingredient_tree()
        self._refresh_step_ingredient_list()

    def add_step(self) -> None:
        operation = self.operation_var.get().strip()
        if not operation:
            messagebox.showwarning("Шаги", "Выберите операцию.", parent=self)
            return
        try:
            duration = optional_int(self.step_duration_var.get(),
                                    "Длительность шага")
        except ValueError as exc:
            messagebox.showwarning("Шаги", str(exc), parent=self)
            return
        selected = [
            self.step_ingredient_list.get(index)
            for index in self.step_ingredient_list.curselection()
        ]
        self._steps.append({
            "operation": operation,
            "description": self.step_description_var.get().strip(),
            "duration": duration,
            "ingredients": tuple(selected),
        })
        self.step_duration_var.set("")
        self.step_description_var.set("")
        self.step_ingredient_list.selection_clear(0, tk.END)
        self._refresh_step_tree()

    def remove_step(self) -> None:
        selected = self.step_tree.selection()
        if not selected:
            return
        del self._steps[int(selected[0])]
        self._refresh_step_tree()

    def save(self) -> None:
        name = self.name_var.get().strip()
        category = self.category_var.get().strip()
        if not name:
            messagebox.showwarning("Рецепт", "Укажите название.", parent=self)
            return
        if not category:
            messagebox.showwarning(
                "Рецепт",
                "Нет категории рецепта. Создайте её во вкладке «Справочники».",
                parent=self,
            )
            return
        if not self._ingredients:
            messagebox.showwarning("Рецепт", "Добавьте хотя бы один ингредиент.",
                                   parent=self)
            return
        if not self._steps:
            messagebox.showwarning("Рецепт", "Добавьте хотя бы один шаг.",
                                   parent=self)
            return
        try:
            data = RecipeInput(
                name=name,
                category=category,
                ingredients=tuple(
                    RecipeIngredientInput(
                        ingredient=item["name"],
                        amount=item["amount"],
                        unit=item["unit"] or None,
                        note=item["note"],
                    )
                    for item in self._ingredients
                ),
                steps=tuple(
                    RecipeStepInput(
                        operation=step["operation"],
                        description=step["description"],
                        duration_minutes=step["duration"],
                        ingredients=step["ingredients"],
                    )
                    for step in self._steps
                ),
                servings=required_int(self.servings_var.get(), "Количество порций"),
                cooking_time_minutes=optional_int(
                    self.time_var.get(), "Общее время"),
                description=self.description.get("1.0", tk.END).strip(),
            )
            recipe = self.app.write(
                lambda service, _catalog: service.create_recipe(data)
            )
        except (ValueError, RecipeBookError) as exc:
            self.app.report_error(exc)
            return
        except Exception as exc:
            self.app.report_error(exc)
            return

        messagebox.showinfo(
            "Рецепт сохранён",
            f"«{recipe.name}» добавлен. Время: {recipe.cooking_time_minutes} мин.",
            parent=self,
        )
        self.reset()
        self.app.recipes_tab.refresh()
        self.app.catalog_tab.refresh()
        self.app.select_tab(0)

    def reset(self) -> None:
        self.name_var.set("")
        self.servings_var.set("2")
        self.time_var.set("")
        self.description.delete("1.0", tk.END)
        self._ingredients.clear()
        self._steps.clear()
        self.amount_var.set("")
        self.note_var.set("")
        self.step_duration_var.set("")
        self.step_description_var.set("")
        self._refresh_ingredient_tree()
        self._refresh_step_tree()
        self._refresh_step_ingredient_list()
        self.refresh_catalog()


class IngredientsPane(ttk.Frame):
    def __init__(self, parent: tk.Misc, app: RecipeBookApp) -> None:
        super().__init__(parent)
        self.app = app
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        self.query_var = tk.StringVar()
        self.category_var = tk.StringVar(value="Все")
        self._build_filters()
        self._build_table()
        self._build_form()
        self.refresh()

    def _build_filters(self) -> None:
        bar = ttk.Frame(self)
        bar.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        ttk.Label(bar, text="Поиск:").pack(side=tk.LEFT)
        ttk.Entry(bar, textvariable=self.query_var, width=24).pack(
            side=tk.LEFT, padx=(4, 12))
        ttk.Label(bar, text="Категория:").pack(side=tk.LEFT)
        self.category_combo = ttk.Combobox(
            bar, textvariable=self.category_var, state="readonly", width=24)
        self.category_combo.pack(side=tk.LEFT, padx=(4, 8))
        ttk.Button(bar, text="Найти", command=self.search).pack(side=tk.LEFT)
        ttk.Button(bar, text="Сбросить", command=self.reset).pack(
            side=tk.LEFT, padx=(6, 0))

    def _build_table(self) -> None:
        frame = ttk.Frame(self)
        frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=4)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.tree = make_tree(
            frame,
            [("name", "Ингредиент", 220),
             ("category", "Категория", 180),
             ("unit", "Ед.", 70),
             ("description", "Описание", 300)],
            height=12,
        )
        vertical, horizontal = attach_scrollbars(frame, self.tree)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")

    def _build_form(self) -> None:
        box = ttk.LabelFrame(self, text="Новый ингредиент")
        box.grid(row=3, column=0, sticky="ew", padx=8, pady=(4, 8))
        box.columnconfigure(1, weight=1)
        box.columnconfigure(3, weight=1)

        self.name_var = tk.StringVar()
        self.new_category_var = tk.StringVar()
        self.unit_var = tk.StringVar(value="г")
        self.description_var = tk.StringVar()

        ttk.Label(box, text="Название:").grid(row=0, column=0, sticky="w",
                                             padx=(8, 4), pady=4)
        ttk.Entry(box, textvariable=self.name_var).grid(
            row=0, column=1, sticky="ew", padx=(0, 12), pady=4)
        ttk.Label(box, text="Категория:").grid(row=0, column=2, sticky="w",
                                               padx=(0, 4), pady=4)
        self.new_category_combo = ttk.Combobox(
            box, textvariable=self.new_category_var, state="readonly")
        self.new_category_combo.grid(row=0, column=3, sticky="ew",
                                    padx=(0, 8), pady=4)
        ttk.Label(box, text="Ед. изм.:").grid(row=1, column=0, sticky="w",
                                              padx=(8, 4), pady=4)
        ttk.Entry(box, textvariable=self.unit_var, width=12).grid(
            row=1, column=1, sticky="w", pady=4)
        ttk.Label(box, text="Описание:").grid(row=2, column=0, sticky="w",
                                               padx=(8, 4), pady=4)
        ttk.Entry(box, textvariable=self.description_var).grid(
            row=2, column=1, columnspan=3, sticky="ew", padx=(0, 8), pady=4)
        ttk.Button(box, text="Добавить ингредиент", style="Accent.TButton",
                   command=self.add).grid(row=3, column=1, sticky="w", pady=4)

    def refresh(self) -> None:
        try:
            categories, ingredients = self.app.read(
                lambda _recipes, catalog: (
                    [item.name for item in catalog.list_ingredient_categories()],
                    catalog.list_ingredients(),
                )
            )
        except Exception as exc:
            self.app.report_error(exc)
            return
        self.category_combo["values"] = ["Все", *categories]
        self.new_category_combo["values"] = categories
        if self.category_var.get() not in self.category_combo["values"]:
            self.category_var.set("Все")
        if self.new_category_var.get() not in categories:
            self.new_category_var.set(categories[0] if categories else "")
        self._populate(ingredients)

    def _populate(self, ingredients: Sequence[Any]) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for item in ingredients:
            self.tree.insert(
                "", tk.END,
                values=(item.name, item.category, item.default_unit,
                        item.description),
            )

    def search(self) -> None:
        category = self.category_var.get()
        try:
            ingredients = self.app.read(
                lambda _recipes, catalog: catalog.list_ingredients(
                    category=None if category in ("", "Все") else category,
                    query=self.query_var.get().strip() or None,
                )
            )
            self._populate(ingredients)
            self.app.status(f"Ингредиентов: {len(ingredients)}")
        except Exception as exc:
            self.app.report_error(exc)

    def reset(self) -> None:
        self.query_var.set("")
        self.category_var.set("Все")
        self.search()

    def add(self) -> None:
        try:
            self.app.write(
                lambda _recipes, catalog: catalog.create_ingredient(
                    name=self.name_var.get(),
                    category=self.new_category_var.get(),
                    default_unit=self.unit_var.get(),
                    description=self.description_var.get(),
                )
            )
        except Exception as exc:
            self.app.report_error(exc)
            return
        self.name_var.set("")
        self.description_var.set("")
        self.app.refresh_all()
        self.app.status("Ингредиент добавлен.")


class CategoriesPane(ttk.Frame):
    def __init__(self, parent: tk.Misc, app: RecipeBookApp) -> None:
        super().__init__(parent)
        self.app = app
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self._build_tables()
        self._build_form()
        self.refresh()

    def _build_tables(self) -> None:
        body = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        body.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        left = ttk.LabelFrame(body, text="Категории ингредиентов")
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        self.ingredient_tree = make_tree(
            left, [("name", "Название", 180), ("description", "Описание", 240)],
            height=11)
        v, h = attach_scrollbars(left, self.ingredient_tree)
        self.ingredient_tree.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        v.grid(row=0, column=1, sticky="ns", pady=6)
        h.grid(row=1, column=0, sticky="ew", padx=6)
        body.add(left, weight=1)

        right = ttk.LabelFrame(body, text="Категории рецептов")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.recipe_tree = make_tree(
            right, [("name", "Название", 180), ("description", "Описание", 240)],
            height=11)
        v, h = attach_scrollbars(right, self.recipe_tree)
        self.recipe_tree.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        v.grid(row=0, column=1, sticky="ns", pady=6)
        h.grid(row=1, column=0, sticky="ew", padx=6)
        body.add(right, weight=1)

    def _build_form(self) -> None:
        box = ttk.LabelFrame(self, text="Новая категория")
        box.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        box.columnconfigure(3, weight=1)
        self.kind_var = tk.StringVar(value="Категория ингредиентов")
        self.name_var = tk.StringVar()
        self.description_var = tk.StringVar()
        ttk.Label(box, text="Тип:").grid(row=0, column=0, sticky="w",
                                         padx=(8, 4), pady=5)
        ttk.Combobox(
            box, textvariable=self.kind_var, state="readonly", width=24,
            values=("Категория ингредиентов", "Категория рецептов"),
        ).grid(row=0, column=1, sticky="w", padx=(0, 12), pady=5)
        ttk.Label(box, text="Название:").grid(row=0, column=2, sticky="w",
                                              padx=(0, 4), pady=5)
        ttk.Entry(box, textvariable=self.name_var, width=28).grid(
            row=0, column=3, sticky="ew", padx=(0, 12), pady=5)
        ttk.Label(box, text="Описание:").grid(row=1, column=0, sticky="w",
                                              padx=(8, 4), pady=5)
        ttk.Entry(box, textvariable=self.description_var).grid(
            row=1, column=1, columnspan=3, sticky="ew", padx=(0, 8), pady=5)
        ttk.Button(box, text="Добавить категорию", style="Accent.TButton",
                   command=self.add).grid(row=2, column=1, sticky="w", pady=4)

    def refresh(self) -> None:
        try:
            ingredient_categories, recipe_categories = self.app.read(
                lambda _recipes, catalog: (
                    catalog.list_ingredient_categories(),
                    catalog.list_recipe_categories(),
                )
            )
        except Exception as exc:
            self.app.report_error(exc)
            return
        for tree, items in ((self.ingredient_tree, ingredient_categories),
                            (self.recipe_tree, recipe_categories)):
            for item in tree.get_children():
                tree.delete(item)
            for category in items:
                tree.insert("", tk.END,
                            values=(category.name, category.description))

    def add(self) -> None:
        try:
            if self.kind_var.get() == "Категория рецептов":
                operation = lambda _recipes, catalog: catalog.create_recipe_category(
                    self.name_var.get(), self.description_var.get())
            else:
                operation = lambda _recipes, catalog: catalog.create_ingredient_category(
                    self.name_var.get(), self.description_var.get())
            self.app.write(operation)
        except Exception as exc:
            self.app.report_error(exc)
            return
        self.name_var.set("")
        self.description_var.set("")
        self.app.refresh_all()
        self.app.status("Категория добавлена.")


class OperationsPane(ttk.Frame):
    def __init__(self, parent: tk.Misc, app: RecipeBookApp) -> None:
        super().__init__(parent)
        self.app = app
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self._build_table()
        self._build_form()
        self.refresh()

    def _build_table(self) -> None:
        frame = ttk.Frame(self)
        frame.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.tree = make_tree(
            frame,
            [("name", "Операция", 220), ("description", "Описание", 460)],
            height=12)
        v, h = attach_scrollbars(frame, self.tree)
        self.tree.grid(row=0, column=0, sticky="nsew")
        v.grid(row=0, column=1, sticky="ns")
        h.grid(row=1, column=0, sticky="ew")

    def _build_form(self) -> None:
        box = ttk.LabelFrame(self, text="Новая операция")
        box.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        box.columnconfigure(1, weight=1)
        self.name_var = tk.StringVar()
        self.description_var = tk.StringVar()
        ttk.Label(box, text="Название:").grid(row=0, column=0, sticky="w",
                                              padx=(8, 4), pady=5)
        ttk.Entry(box, textvariable=self.name_var).grid(
            row=0, column=1, sticky="ew", padx=(0, 8), pady=5)
        ttk.Label(box, text="Описание:").grid(row=1, column=0, sticky="w",
                                              padx=(8, 4), pady=5)
        ttk.Entry(box, textvariable=self.description_var).grid(
            row=1, column=1, sticky="ew", padx=(0, 8), pady=5)
        ttk.Button(box, text="Добавить операцию", style="Accent.TButton",
                   command=self.add).grid(row=2, column=1, sticky="w", pady=4)

    def refresh(self) -> None:
        try:
            operations = self.app.read(
                lambda _recipes, catalog: catalog.list_operations())
        except Exception as exc:
            self.app.report_error(exc)
            return
        for item in self.tree.get_children():
            self.tree.delete(item)
        for operation in operations:
            self.tree.insert("", tk.END,
                             values=(operation.name, operation.description))

    def add(self) -> None:
        try:
            self.app.write(
                lambda _recipes, catalog: catalog.create_operation(
                    self.name_var.get(), self.description_var.get())
            )
        except Exception as exc:
            self.app.report_error(exc)
            return
        self.name_var.set("")
        self.description_var.set("")
        self.app.refresh_all()
        self.app.status("Операция добавлена.")


class CatalogTab(ttk.Frame):
    def __init__(self, parent: tk.Misc, app: RecipeBookApp) -> None:
        super().__init__(parent)
        self.app = app
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.ingredients_pane = IngredientsPane(self.notebook, app)
        self.categories_pane = CategoriesPane(self.notebook, app)
        self.operations_pane = OperationsPane(self.notebook, app)
        self.notebook.add(self.ingredients_pane, text="  Ингредиенты  ")
        self.notebook.add(self.categories_pane, text="  Категории  ")
        self.notebook.add(self.operations_pane, text="  Операции  ")

    def refresh(self) -> None:
        self.ingredients_pane.refresh()
        self.categories_pane.refresh()
        self.operations_pane.refresh()


def run_gui(database: Database) -> int:
    app = RecipeBookApp(database)
    app.mainloop()
    return 0


def _database_url(value: str) -> str:
    if "://" in value:
        return value
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return f"sqlite:///{path.resolve().as_posix()}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="recipe-book-gui",
        description="Графический интерфейс «Книги рецептов».",
    )
    parser.add_argument(
        "--db",
        default="recipe_book.sqlite3",
        help="путь к SQLite-базе или SQLAlchemy URL",
    )
    args = parser.parse_args(argv)
    database = Database(_database_url(args.db))
    try:
        database.create_schema()
        return run_gui(database)
    except Exception as exc:
        try:
            messagebox.showerror("Книга рецептов", str(exc))
        except Exception:
            print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    finally:
        database.dispose()


if __name__ == "__main__":
    raise SystemExit(main())