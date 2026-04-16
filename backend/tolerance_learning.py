MAX_SHOE_SCORE = 100  # max shoe fit score
EPSILON = 1e-6  # prevents div by 0
K = 0.2  # helps keeps scale of tolerance shift reasonable

# sample feedback row format
'''feedback_rows = [
    {
     "feedback_type": "too wide",
     "total_score": 72,
     "severity": 3
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
        stats[feedback["feedback_type"]]["score"] += feedback["total_score"]
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
    
    for name, tol in tolerances.items():
        if name == "meta":
            continue

        delta_low = tol["opt_low"] - tol["min"]
        delta_high = tol["max"] - tol["opt_high"]

        signal = width_signal if tol["type"] == "width" else length_signal

        opt_low = tol["opt_low"]
        opt_high = tol["opt_high"]

        # Assumes opt_low will never be 0, which should be the case
        new_opt_low = opt_low + alpha * K * signal * opt_low
        new_opt_high = opt_high - alpha * K * signal * opt_high

        # Ensure we don't flip the optimal range
        if new_opt_low > new_opt_high:
            new_opt_low = new_opt_high = (new_opt_low + new_opt_high) / 2
        
        new_min = new_opt_low - delta_low
        new_max = new_opt_high + delta_high
        new_tolerances[name] = {
            "min": new_min,
            "opt_low": new_opt_low,
            "opt_high": new_opt_high,
            "max": new_max
            }
    return new_tolerances