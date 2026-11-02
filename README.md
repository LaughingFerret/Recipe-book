# Книга рецептов (Recipe Book)

Приложение на Python для ведения справочников ингредиентов и операций, составления рецептов и их поиска. Поддерживает работу через командную строку (CLI) и графический интерфейс (GUI). Данные хранятся в SQLite с использованием SQLAlchemy 2.0.

## Требования

- Python 3.12+
- SQLAlchemy 2.0+
- Tkinter (для графического интерфейса)

## Установка

```bash
git clone https://github.com/LaughingFerret/Recipe-book.git
cd Recipe-book

python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows

pip install -e .
