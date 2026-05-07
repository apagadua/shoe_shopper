from backend.services.feedback_service import get_feedback_rows

from backend.services.tolerance_learning import (
    compute_dimension_vals,
    compute_signals,
    compute_tolerances
)

from backend.services.tolerance_storage import load_tolerances, save_tolerances

def retrain():
    # load current tolerances and last feedback timestamp
    tolerances = load_tolerances()
    if not tolerances:
        print("No active tolerances found.")
        return
    last_feedback_timestamp = tolerances["last_feedback_timestamp"]

    # fetch new feedback rows since last feedback timestamp
    feedback_rows, new_feedback_timestamp = get_feedback_rows(last_feedback_timestamp)

    if not feedback_rows:
        print("No feedback to train on.")
        return
    
    # compute intermediary values based on feedback
    values = compute_dimension_vals(feedback_rows)

    # compute directional signals for width and length adjustments
    width_signal, length_signal = compute_signals(values)

    # calculate learning rate alpha based on new feedback count and total feedback count
    old_count = tolerances["total_feedback_count"]
    new_count = len(feedback_rows)
    if old_count == 0:
        alpha = 0.05
    else:
        alpha = new_count / (old_count + new_count + 1e-6)

    # compute new tolerances
    new_tolerances = compute_tolerances(
        width_signal,
        length_signal,
        tolerances,
        alpha,
        new_count
    )

    save_tolerances(new_tolerances, old_count + new_count, new_feedback_timestamp)