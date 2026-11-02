class RecipeBookError(Exception):
    """Базовое исключение приложения."""


class ValidationError(RecipeBookError):
    """Переданы некорректные данные."""


class NotFoundError(RecipeBookError):
    """Запрошенный объект не найден."""


class ConflictError(RecipeBookError):
    """Объект с такими данными уже существует."""
