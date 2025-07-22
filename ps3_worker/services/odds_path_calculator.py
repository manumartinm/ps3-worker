import pandas as pd


class OddsPathCalculator:
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.results = []

    def calculate(self) -> pd.DataFrame:
        for _, row in self.df.iterrows():
            result = self._process_row(row)
            self.results.append(result)
        return pd.DataFrame(self.results)

    def _process_row(self, row: pd.Series) -> dict:
        default_result = {
            # pyrefly: ignore  # invalid-argument
            **row,
            "odds_path": None,
            "category": "Indeterminate",
        }

        try:
            pathogenic = int(row["pathogenicVariants"])
            total = int(row["totalVariants"])
            abnormal = int(row["pathogenicAbnormalVariants"])
        except (KeyError, ValueError, TypeError):
            return default_result

        benign = total - pathogenic
        normal = benign - abnormal

        if (pathogenic + benign) == 0 or (abnormal + normal) == 0:
            return default_result

        P1 = pathogenic / (pathogenic + benign)
        P2 = abnormal / (abnormal + normal)

        if P1 in [0, 1] or P2 in [0, 1]:
            return default_result

        odds_path = (P2 * (1 - P1)) / ((1 - P2) * P1)

        has_replicates = row.get("replicates", 0) is not None and row["replicates"] >= 2
        is_reproducible = row.get("reproducible", False) == True

        validation = str(row.get("validationProcess", "")).lower()
        has_validation = validation != "not specified" and validation != "none"

        stats_analysis = str(row.get("statisticalAnalysis", "")).lower()
        has_stats = "no specific statistical" not in stats_analysis and "not specified" not in stats_analysis

        total_controls = pathogenic + benign

        if not (has_replicates and is_reproducible and has_validation):
            category = "Do not use PS3/BS3"
        else:
            if has_stats:
                category = self._categorize_odds_path(odds_path)
            else:
                if total_controls >= 11:
                    category = "Max PS3_moderate / Max BS3_moderate"
                elif total_controls > 0:
                    category = "Max PS3_supporting / Max BS3_supporting"
                else:
                    category = "Do not use PS3/BS3"

        return {
            # pyrefly: ignore  # invalid-argument
            **row,
            "odds_path": round(odds_path, 3),
            "category": category,
        }

    def _categorize_odds_path(self, odds_path: float) -> str:
        if odds_path < 0.053:
            return "BS3"
        elif odds_path < 0.23:
            return "BS3_moderate"
        elif odds_path < 0.48:
            return "BS3_supporting"
        elif odds_path <= 2.1:
            return "Indeterminate"
        elif odds_path > 350:
            return "PS3_very_strong"
        elif odds_path > 18.7:
            return "PS3"
        elif odds_path > 4.3:
            return "PS3_moderate"
        elif odds_path > 2.1:
            return "PS3_supporting"
        else:
            return "Indeterminate"
