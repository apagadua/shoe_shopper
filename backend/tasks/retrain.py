from backend.services.feedback_service import get_feedback_rows

from backend.tolerance_learning import (
    compute_dimension_vals,
    compute_signals,
    compute_tolerances
)

from backend.tolerances.history.tolerance_storage import load_tolerances, save_tolerances

def retrain():
    feedback_rows = get_feedback_rows()

    if not feedback_rows:
        print("No feedback to train on.")
        return
    
    values = compute_dimension_vals(feedback_rows)
    width_signal, length_signal = compute_signals(values)

    tolerances = load_tolerances()

    old_count = tolerances["meta"]["total_feedback_count"]
    new_count = len(feedback_rows)
    if old_count == 0:
        alpha = 0.1
    else:
        alpha = new_count / (old_count + new_count + 1e-6)

    new_tolerances = compute_tolerances(
        width_signal,
        length_signal,
        tolerances,
        alpha,
        new_count
    )

    save_tolerances(new_tolerances)