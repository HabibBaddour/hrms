import random
from pathlib import Path

import pandas as pd


RANDOM_SEED = 42
SAMPLE_COUNT = 500

random.seed(RANDOM_SEED)

# Real department/position combinations found in the HRMS database.
DEPARTMENT_POSITION_PAIRS = [
    (6, 24),
    (5, 19),
    (4, 16),
    (5, 18),
    (3, 12),
    (1, 3),
    (1, 1),
    (6, 22),
    (5, 17),
    (2, 5),
    (2, 6),
    (3, 9),
    (3, 11),
    (6, 21),
    (4, 14),
    (1, 4),
    (4, 15),
    (5, 20),
    (6, 23),
    (4, 13),
    (2, 8),
    (1, 2),
    (2, 7),
    (3, 10),
]


def generate_sample():
    department_id, position_id = random.choice(
        DEPARTMENT_POSITION_PAIRS
    )

    leave_type = random.choice(["SICK", "ANNUAL"])

    duration_days = random.randint(1, 10)

    previous_requests = random.randint(0, 8)

    if previous_requests == 0:
        previous_approved = 0
        previous_rejected = 0
    else:
        previous_approved = random.randint(
            0,
            previous_requests,
        )

        previous_rejected = (
            previous_requests - previous_approved
        )

    approval_rate = (
        previous_approved / previous_requests
        if previous_requests > 0
        else 0.5
    )

    attendance_total = random.randint(10, 60)

    late_count = random.randint(
        0,
        min(15, attendance_total),
    )

    on_time_count = attendance_total - late_count

    on_time_rate = on_time_count / attendance_total

    same_department_leave_count = random.randint(0, 5)

    # ---------------------------------------------------------
    # Synthetic target rule
    # ---------------------------------------------------------
    #
    # This is NOT real HR policy.
    # It creates a consistent synthetic dataset so that
    # Random Forest can be demonstrated without using the
    # project's experimental leave records.
    # ---------------------------------------------------------

    score = 0

    if leave_type == "ANNUAL":
        score += 1

    if duration_days <= 5:
        score += 1
    elif duration_days >= 8:
        score -= 1

    if previous_requests == 0:
        score += 0
    elif approval_rate >= 0.75:
        score += 2
    elif approval_rate >= 0.50:
        score += 1
    elif approval_rate < 0.25:
        score -= 2

    if on_time_rate >= 0.90:
        score += 2
    elif on_time_rate >= 0.75:
        score += 1
    elif on_time_rate < 0.50:
        score -= 1

    if late_count >= 10:
        score -= 1

    if same_department_leave_count >= 4:
        score -= 2
    elif same_department_leave_count >= 2:
        score -= 1

    # Small random component prevents the synthetic dataset
    # from being perfectly deterministic.
    score += random.choice([-1, 0, 0, 0, 1])

    approval_probability = 1 / (1 + pow(2.71828, -score))

    approved = random.random() < approval_probability

    return {
        "leave_type": leave_type,
        "duration_days": duration_days,
        "department_id": str(department_id),
        "position_id": str(position_id),
        "previous_requests": previous_requests,
        "previous_approved": previous_approved,
        "previous_rejected": previous_rejected,
        "approval_rate": round(approval_rate, 4),
        "on_time_rate": round(on_time_rate, 4),
        "late_count": late_count,
        "same_department_leave_count": same_department_leave_count,
        "target": "APPROVED" if approved else "REJECTED",
    }


def main():
    output_path = Path(__file__).resolve().parent / "leave_training.csv"

    rows = [
        generate_sample()
        for _ in range(SAMPLE_COUNT)
    ]

    dataframe = pd.DataFrame(rows)

    dataframe.to_csv(
        output_path,
        index=False,
        encoding="utf-8",
    )

    print(f"Created: {output_path}")
    print(f"Rows: {len(dataframe)}")
    print("\nTarget distribution:")
    print(dataframe["target"].value_counts())

    print("\nPreview:")
    print(dataframe.head())


if __name__ == "__main__":
    main()