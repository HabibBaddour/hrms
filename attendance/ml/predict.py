from pathlib import Path

import joblib
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "attendance_random_forest.joblib"


def predict_total_deduction(
    basic_salary,
    working_days,
    present_days,
    late_days,
    absent_days,
    late_minutes,
    late_hours,
):
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model not found: {MODEL_PATH}"
        )

    saved_model = joblib.load(MODEL_PATH)

    model = saved_model["model"]
    features = saved_model["features"]

    data = pd.DataFrame(
        [
            {
                "basic_salary": basic_salary,
                "working_days": working_days,
                "present_days": present_days,
                "late_days": late_days,
                "absent_days": absent_days,
                "late_minutes": late_minutes,
                "late_hours": late_hours,
            }
        ]
    )

    prediction = model.predict(
        data[features]
    )[0]

    return round(float(prediction), 2)


if __name__ == "__main__":
    dataset_path = (
        BASE_DIR
        / "data"
        / "attendance_dataset.csv"
    )

    df = pd.read_csv(dataset_path)

    sample = df.iloc[0]

    predicted = predict_total_deduction(
        basic_salary=sample["basic_salary"],
        working_days=sample["working_days"],
        present_days=sample["present_days"],
        late_days=sample["late_days"],
        absent_days=sample["absent_days"],
        late_minutes=sample["late_minutes"],
        late_hours=sample["late_hours"],
    )

    actual = round(
        float(sample["total_deduction"]),
        2,
    )

    print("Sample employee ID:", int(sample["employee_id"]))
    print(
        "Month:",
        int(sample["month"]),
        "/",
        int(sample["year"]),
    )
    print("Actual deduction:", actual)
    print("Predicted deduction:", predicted)
    print(
        "Difference:",
        round(abs(actual - predicted), 2),
    )