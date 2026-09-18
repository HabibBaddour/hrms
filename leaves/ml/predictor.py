from pathlib import Path

import joblib
import pandas as pd

from leaves.ml.features import build_leave_features


MODEL_PATH = Path(__file__).resolve().parent / "leave_random_forest.joblib"


def predict_leave(leave_request):
    """
    Predict whether a leave request is likely to be approved or rejected.

    Returns:
        {
            "prediction": "APPROVED" or "REJECTED",
            "confidence": float
        }
    """

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Leave prediction model not found: {MODEL_PATH}"
        )

    model = joblib.load(MODEL_PATH)

    features = build_leave_features(leave_request)

    feature_dataframe = pd.DataFrame([features])

    prediction = model.predict(feature_dataframe)[0]

    probabilities = model.predict_proba(feature_dataframe)[0]

    class_probabilities = dict(
        zip(
            model.classes_,
            probabilities,
        )
    )

    confidence = class_probabilities[prediction] * 100

    return {
        "prediction": prediction,
        "confidence": round(float(confidence), 2),
    }