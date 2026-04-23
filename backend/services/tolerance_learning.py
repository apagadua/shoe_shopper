MAX_SHOE_SCORE = 100  # max shoe fit score
EPSILON = 1e-6  # prevents div by 0
K = 0.05  # helps keeps scale of tolerance shift reasonable

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
    stats = {
        "perfect": {"score": 0, "severity": 0, "count": 0},
        "too wide": {"score": 0, "severity": 0, "count": 0},
        "too narrow": {"score": 0, "severity": 0, "count": 0},
        "too long": {"score": 0, "severity": 0, "count": 0},
        "too short": {"score": 0, "severity": 0, "count": 0}
        }
    
    # gather feedback
    for feedback in feedback_rows:
        if feedback["fit_score"] is None or feedback["severity"] is None:
            continue
        stats[feedback["feedback_type"]]["score"] += feedback["fit_score"]
        stats[feedback["feedback_type"]]["count"] += 1
        if feedback["feedback_type"] != "perfect":
            stats[feedback["feedback_type"]]["severity"] += feedback["severity"]
    
    # average values
    for s in stats:
        if stats[s]["count"] > 0:
            stats[s]["score"] /= stats[s]["count"]
            if s != "perfect":
                stats[s]["severity"] /= stats[s]["count"]

    # value = count * average severity * (average shoe score / max shoe score)
    values = {}
    values["perfect"] = (stats["perfect"]["count"] *
                         stats["perfect"]["score"] / MAX_SHOE_SCORE)
    for s in stats:
        if s != "perfect":
            values[s] = stats[s]["count"] * stats[s]["severity"] * (stats[s]["score"] /
                                                                    MAX_SHOE_SCORE)
    return values

def compute_signals(values):
    width_signal = ((values["too narrow"] - values["too wide"]) /
                    (values["perfect"] + values["too narrow"] + values["too wide"]
                     + EPSILON))
    length_signal = ((values["too short"] - values["too long"]) /
                    (values["perfect"] + values["too short"] + values["too long"]
                     + EPSILON))
    return width_signal, length_signal

def compute_tolerances(width_signal, length_signal, tolerances, alpha, count):
    # currently considers all past feedback
    new_tolerances = {"meta": {"total_feedback_count": 
                               tolerances["meta"]["total_feedback_count"] + count}}
    
    type = ""
    
    for name, tol in tolerances.items():
        if name == "meta":
            continue

        delta_low = tol["opt_low"] - tol["min"]
        delta_high = tol["max"] - tol["opt_high"]

        if tol["type"] == "width":
            signal = width_signal
            type = "width"
        else:
            signal = length_signal
            type = "length"

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
            "type": type,
            "min": new_min,
            "opt_low": new_opt_low,
            "opt_high": new_opt_high,
            "max": new_max
            }
    return new_tolerances