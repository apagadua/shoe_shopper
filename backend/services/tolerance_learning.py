MAX_SHOE_SCORE = 100  # max shoe fit score
EPSILON = 1e-6  # prevents div by 0
K = 0.05  # helps keeps scale of tolerance shift reasonable

MAX_SEVERITY = 5

# sample feedback row format
'''feedback_rows = [
    {
     "feedback_type": "too wide",
     "fit_score": 72,
     "severity": 3,
    }, etc....
]'''

def compute_dimension_vals(feedback_rows):
    # feedback type: (total fit score, severity, count)

    # Weigh fit score by severity rating for non-perfect feedback, and use max severity for perfect feedback to give it more weight    
    stats = {
        "perfect": {"adjusted_score": 0, "count": 0},
        "too wide": {"adjusted_score": 0, "count": 0},
        "too narrow": {"adjusted_score": 0, "count": 0},
        "too long": {"adjusted_score": 0, "count": 0},
        "too short": {"adjusted_score": 0, "count": 0}
        }
    
    # iterate through feedback rows and aggregate stats
    for feedback in feedback_rows:
        # gather feedback stats
        if feedback["fit_score"] is None:
            continue
        if feedback["feedback_type"] != "perfect" and feedback["severity_rating"] is None:
            continue

        if feedback["feedback_type"] != "perfect":
            stats[feedback["feedback_type"]]["adjusted_score"] += feedback["fit_score"] * feedback["severity_rating"]
            stats[feedback["feedback_type"]]["count"] += 1
        else:
            stats[feedback["feedback_type"]]["adjusted_score"] += feedback["fit_score"] * MAX_SEVERITY
            stats[feedback["feedback_type"]]["count"] += 1

    # average values
    for stat in stats:
        if stats[stat]["count"] > 0:
            stats[stat]["adjusted_score"] /= stats[stat]["count"]

    # compute dimension values for signal calculation
    values = {}
    for stat in stats:
        values[stat] = stats[stat]["count"] * (stats[stat]["adjusted_score"] / MAX_SHOE_SCORE)

    # get last feedback timestamp for future training runs
    last_feedback_timestamp = max([feedback["created_at"] 
                                   for feedback in feedback_rows if feedback["created_at"] is not None], default=None)
    return values, last_feedback_timestamp


def compute_signals(values):
    # width signal is positive if shoe is too wide, negative if shoe is too narrow
    width_signal = ((values["too narrow"] - values["too wide"]) /
                    (values["perfect"] + values["too narrow"] + values["too wide"]
                     + EPSILON))
    
    # length signal is positive if shoe is too short, negative if shoe is too long
    length_signal = ((values["too short"] - values["too long"]) /
                    (values["perfect"] + values["too short"] + values["too long"]
                     + EPSILON))
    return width_signal, length_signal

def compute_tolerances(width_signal, length_signal, tolerances, alpha, count): 
    # currently considers all past feedback
    new_tolerances = {"meta": {"total_feedback_count": 
                               tolerances["meta"]["total_feedback_count"] + count}}
    
    dimension_type = ""
    
    for name, tol in tolerances.items():
        if name == "meta":
            continue

        delta_low = tol["opt_low"] - tol["min"]
        delta_high = tol["max"] - tol["opt_high"]

        if tol["type"] == "width":
            signal = width_signal
            dimension_type = "width"
        else:
            signal = length_signal
            dimension_type = "length"

        opt_low = tol["opt_low"]
        opt_high = tol["opt_high"]

        # print(f"Updating {name}: signal={signal:.4f}, alpha={alpha:.4f}, "
        #         f"old_opt_low={opt_low:.4f}, old_opt_high={opt_high:.4f}, shift={alpha * K * signal:.4f}")
        # Assumes opt_low, shouldn't be the case
        shift = alpha * K * signal
        new_opt_low = opt_low + shift
        new_opt_high = opt_high + shift

        # Ensure we don't flip the optimal range
        if new_opt_low > new_opt_high:
            new_opt_low = new_opt_high = (new_opt_low + new_opt_high) / 2
        
        new_min = new_opt_low - delta_low
        new_max = new_opt_high + delta_high
        new_tolerances[name] = {
            "type": dimension_type,
            "min": new_min,
            "opt_low": new_opt_low,
            "opt_high": new_opt_high,
            "max": new_max
            }
    return new_tolerances