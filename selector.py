"""Шаблон селектора признаков для ноды Feature Selector (fs-node).

Контракт ноды:
- всё приходит при инициализации: `params` из config.yaml + kwargs ноды.
  Датасет — уже прочитанный `df_longlist: pd.DataFrame`; остальное —
  списки колонок nm_*, пути портов (selector_zip, extra_zip), pr_log_level;
- магия запускается методом `select_features()`;
- результат — атрибуты:
    df_middlelist: pd.DataFrame — middle list (key-колонки + выбранные фичи);
    artefacts: str — путь к zip-архиву, который селектор собирает сам
    (где угодно — нода сама переместит его и отдаст в порт artefacts_zip).

Замените логику отбора в `select_features()` на свою.
"""

import json
import os
import tempfile
import zipfile
from typing import List, Optional

import pandas as pd


class FeatureSelector:
    """Пример отбора: фильтр по пропускам/вариации + ранжирование по корреляции."""

    def __init__(
        self,
        df_longlist: pd.DataFrame,
        nm_target: Optional[List[str]] = None,
        nm_short_target: Optional[List[str]] = None,
        nm_category: Optional[List[str]] = None,
        nm_numeric: Optional[List[str]] = None,
        nm_date: Optional[List[str]] = None,
        nm_report_date: Optional[List[str]] = None,
        nm_id: Optional[List[str]] = None,
        nm_baseline: Optional[List[str]] = None,
        nm_weight: Optional[List[str]] = None,
        nm_group: Optional[List[str]] = None,
        nm_text: Optional[List[str]] = None,
        nm_embedding: Optional[List[str]] = None,
        # params из config.yaml
        max_missing_rate: float = 0.5,
        min_variance: float = 1e-6,
        top_k: int = 50,
        *args,
        **kwargs,
    ):
        self.df = df_longlist
        self.nm_target = nm_target[0] if nm_target else None
        self.nm_id = nm_id or []
        self.nm_numeric = nm_numeric

        # params из config.yaml
        self.max_missing_rate = max_missing_rate
        self.min_variance = min_variance
        self.top_k = top_k

        self.selected: List[str] = []
        self.df_middlelist: Optional[pd.DataFrame] = None
        self.artefacts: Optional[str] = None

    # main function
    def select_features(self) -> None:
        candidates = self._candidates()
        stats = self._calc_stats(candidates)

        passed = stats[
            (stats["missing_rate"] <= self.max_missing_rate)
            & (stats["variance"] >= self.min_variance)
        ]
        ranked = passed.sort_values("corr_with_target", key=lambda s: s.abs(), ascending=False)
        self.selected = ranked.head(self.top_k)["column"].tolist()

        # Middle list: key-колонки + выбранные фичи.
        # ВАЖНО: без .copy() — не плодим копии огромного датасета в памяти!
        key_cols = [c for c in [*self.nm_id, *([self.nm_target] if self.nm_target else [])] if c]
        self.df_middlelist = self.df[key_cols + self.selected]

        self.artefacts = self._zip_artefacts(stats)

    def _candidates(self) -> List[str]:
        if self.nm_numeric:
            return list(self.nm_numeric)
        exclude = set(self.nm_id) | {self.nm_target}
        return [c for c in self.df.select_dtypes(include="number").columns if c not in exclude]

    def _calc_stats(self, candidates: List[str]) -> pd.DataFrame:
        target = self.df[self.nm_target] if self.nm_target else None
        rows = []
        for col in candidates:
            series = self.df[col]
            rows.append({
                "column": col,
                "missing_rate": float(series.isna().mean()),
                "variance": float(series.var()) if series.notna().any() else 0.0,
                "corr_with_target": float(series.corr(target)) if target is not None else float("nan"),
            })
        return pd.DataFrame(rows)

    def _zip_artefacts(self, stats: pd.DataFrame) -> str:
        """Собирает zip артефактов сама и возвращает путь к нему."""
        tmp_dir = tempfile.mkdtemp()
        artefacts_dir = os.path.join(tmp_dir, "artefacts")
        os.makedirs(artefacts_dir)

        stats.to_csv(os.path.join(artefacts_dir, "selection_stats.csv"), index=False)
        with open(os.path.join(artefacts_dir, "selected_features.json"), "w", encoding="utf-8") as f:
            json.dump({"selected": self.selected}, f, ensure_ascii=False, indent=2)

        zip_path = os.path.join(tmp_dir, "artefacts.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(artefacts_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    zf.write(full_path, arcname=os.path.relpath(full_path, tmp_dir))
        return zip_path
