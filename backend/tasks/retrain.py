from backend.services.feedback_service import get_feedback_rows

from backend.services.tolerance_learning import (
    compute_dimension_vals,
    compute_signals,
    compute_tolerances
)

from backend.services.tolerance_storage import load_tolerances, save_tolerances

def retrain():
    # load current tolerances and last feedback timestamp
    tolerances_full = load_tolerances()
    if not tolerances_full:
        print("No active tolerances found.")
        return
    last_feedback_timestamp = tolerances_full["last_feedback_timestamp"]

    tolerances = tolerances_full["tolerances"]

    # fetch new feedback rows since last feedback timestamp
    feedback_rows, new_feedback_timestamp = get_feedback_rows(last_feedback_timestamp)

    if not feedback_rows:
        print("No feedback to train on.")
        return
    
    # compute intermediary values based on feedback
    values = compute_dimension_vals(feedback_rows, tolerances)

    # compute directional signals for width and length adjustments
    width_signal, length_signal = compute_signals(values)

    # calculate learning rate alpha based on new feedback count and total feedback count
    old_count = tolerances_full["total_feedback_count"]
    new_count = len(feedback_rows) - old_count
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
        old_count,
        new_count
    )

    save_tolerances(new_tolerances, old_count + new_count, new_feedback_timestamp)