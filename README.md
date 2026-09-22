# Стандарт репозитория feature selector

Селектор — обычный git-репозиторий. Он будет **склонирован и подан в ноду
архивом автоматически — вам об этом беспокоиться не нужно**. Достаточно
следовать стандарту ниже.

## Структура репозитория

```text
my-feature-selector/          # имя репозитория любое
├── selector.py               # ОБЯЗАТЕЛЬНО — модуль с классом селектора
├── config.yaml               # ОБЯЗАТЕЛЬНО — python_version и опции
├── requirements.txt          # ОБЯЗАТЕЛЬНО — зависимости селектора
└── ...                       # опционально — свои модули, пакеты, спеки
```

Обязательные файлы должны лежать в **корне репозитория** (не в подпапках).

## config.yaml

```yaml
python_version: "3.12"        # ОБЯЗАТЕЛЬНО — версия Python для venv селектора
selector_class: "MySelector"  # опционально, по умолчанию FeatureSelector
params:                       # опционально — прокидываются в конструктор
  top_k: 50
```

## requirements.txt

Всё, что импортирует ваш код. Базовая установка venv даёт только
pyarrow / PyYAML / loguru / orjson — `pandas` и остальное должно быть здесь:

```text
pandas==2.3.3
scikit-learn==1.2.3
```

## Что нужно реализовать

| Элемент             | Тип     | Обязателен | Назначение |
|---------------------|---------|:----------:|------------|
| `__init__`          | метод   | ✅ | Принимает всё при инициализации: `params` из config.yaml + kwargs ноды (таблица ниже) |
| `select_features()` | метод   | ✅ | Точка входа: вызывается после `__init__`, здесь вся магия отбора |
| `df_middlelist`     | атрибут | ✅ | `pd.DataFrame` — middle list: key-колонки + выбранные фичи (+ производные) |
| `artefacts`         | атрибут | ❌ | `str` — путь к собранному вами zip с артефактами (где угодно, нода сама переместит его в порт `artefacts_zip`). Нет артефактов — просто не объявляйте атрибут |

Минимальный рабочий пример:

```python
# selector.py
class FeatureSelector:
    def __init__(self, df_longlist, nm_target=None, nm_id=None, *args, **kwargs):
        self.df = df_longlist                        # датасет уже прочитан нодой
        self.nm_target = nm_target or []
        self.nm_id = nm_id or []

    def select_features(self):
        feats = [...]                                # ваша логика отбора
        keys = [*self.nm_id, *self.nm_target]
        self.df_middlelist = self.df[keys + feats]   # ⚠️ без .copy()!
```

Пример с артефактами (необязательно):

```python
import json, tempfile, zipfile

class FeatureSelector:
    ...
    def select_features(self):
        ...
        tmp_dir = tempfile.mkdtemp()
        zip_path = f"{tmp_dir}/artefacts.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("selected_features.json", json.dumps({"selected": feats}))
        self.artefacts = zip_path
```

## Что приходит в конструктор (kwargs ноды)

| Kwarg | Тип | Что это |
|---|---|---|
| `df_longlist` | `pd.DataFrame` | Датасет лонглиста — нода прочитала его сама |
| `nm_target`, `nm_short_target` | `list[str] \| None` | Таргет |
| `nm_category`, `nm_numeric`, `nm_date`, `nm_text`, `nm_embedding`, `nm_baseline`, `nm_weight`, `nm_group` | `list[str] \| None` | Фичи по типам |
| `nm_report_date`, `nm_id` | `list[str] \| None` | Служебные роли |
| `selector_zip`, `extra_zip` | `str` | Пути к соответствующим архивам |
| `pr_log_level` | `str` | Уровень логирования из UI |

Сверху теми же именами прокидываются `params` из `config.yaml` (опционально!).

**⚠️ Не копируйте датафреймы!** `df.copy()`, «глубокие» concat/merge — сразу
x2 в памяти, а датасеты приходят огромные. Срезы колонок для middle list
берите без `.copy()`, с `df_longlist` работайте экономно.

---