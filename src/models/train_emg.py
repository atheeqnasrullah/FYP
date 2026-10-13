from pathlib import Path
import joblib, pandas as pd
from sklearn.model_selection import LeaveOneGroupOut, GroupKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from src.utils.config import ROOT
from src.features.emg_features import FEATURES

def main():
    path = ROOT / "data/features/emg_features.csv"
    if not path.exists(): raise SystemExit("Build features first with python -m src.features.build_dataset")
    df = pd.read_csv(path).dropna(subset=FEATURES + ["label", "subject_id", "trial_id"])
    y, X = df.label, df[FEATURES]
    groups = df.subject_id.astype(str)
    cv = LeaveOneGroupOut() if groups.nunique() > 1 else GroupKFold(min(5, df.trial_id.nunique()))
    if df.trial_id.nunique() < 2: raise SystemExit("Need at least two trials for grouped evaluation")
    models = {"LDA": make_pipeline(StandardScaler(), LinearDiscriminantAnalysis()),
              "SVM": make_pipeline(StandardScaler(), SVC(C=10, probability=True)),
              "RF": make_pipeline(StandardScaler(), RandomForestClassifier(n_estimators=200, random_state=42))}
    best = None
    for name, model in models.items():
        fold_groups = groups if groups.nunique() > 1 else df.trial_id
        pred = cross_val_predict(model, X, y, groups=fold_groups, cv=cv)
        score = accuracy_score(y, pred); print(f"{name}: accuracy={score:.3f} ({'subject-wise' if groups.nunique()>1 else 'trial-wise'})")
        print(classification_report(y, pred, zero_division=0))
        if best is None or score > best[0]: best = (score, name, model)
    best[2].fit(X, y)
    dest = ROOT / "src/models/saved/emg_model.joblib"; dest.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(best[2], dest); print(f"Saved {best[1]} model to {dest}")

if __name__ == "__main__": main()
