MAX_SHOE_SCORE = 100  # max shoe fit score
EPSILON = 1e-6  # prevents div by 0
K = 0.05  # helps keeps scale of tolerance shift reasonable

MAX_SEVERITY = 5
META = ["total_feedback_count"]

# sample feedback row format
'''feedback_rows = [
    {
     "feedback_type": "too wide",
     "severity_rating": 3,
     "tolerances": { "width": {"max": ...}, ... }
    }, etc....
]'''

def compute_tolerance_euclidean_difference(old_tolerances, current_tolerances, dimension):
    # Compute the Euclidean difference between old and new tolerances
    # For length and width feedback focus on relevant tolerances
    dimensions = ["width", "length", "tb_width", "tb_len"]
    if dimension == "width":
        dimensions = ["width", "tb_width"]
    elif dimension == "length":
        dimensions = ["length", "tb_len"]
    
    final = 0
    for dim in dimensions:
        min_delta = current_tolerances[dim]["min"] - old_tolerances[dim]["min"]
        opt_low_delta = current_tolerances[dim]["opt_low"] - old_tolerances[dim]["opt_low"]
        opt_high_delta = current_tolerances[dim]["opt_high"] - old_tolerances[dim]["opt_high"]
        max_delta = current_tolerances[dim]["max"] - old_tolerances[dim]["max"]
        squared_diffs = (min_delta ** 2) + (opt_low_delta ** 2) + (opt_high_delta ** 2) + (max_delta ** 2)
        final += squared_diffs ** 0.5
    return final


def compute_dimension_vals(feedback_rows, tolerances):
    # Weigh fit score by severity rating for non-perfect feedback, and use max severity for perfect feedback to give it more weight    
    stats = {
        "perfect": {"value": 0.0, "count": 0},
        "too wide": {"value": 0.0, "count": 0},
        "too narrow": {"value": 0.0, "count": 0},
        "too long": {"value": 0.0, "count": 0},
        "too short": {"value": 0.0, "count": 0}
        }
    
    # iterate through feedback rows and aggregate stats
    for feedback in feedback_rows:
        # gather feedback stats
        if feedback["tolerances"] is None:
            continue
        if feedback["feedback_type"] != "perfect" and feedback["severity_rating"] is None:
            continue

        if feedback["feedback_type"] == "too wide" or feedback["feedback_type"] == "too narrow":
            dimension = "width"
        elif feedback["feedback_type"] == "too long" or feedback["feedback_type"] == "too short":
            dimension = "length"
        else:
            dimension = None  # perfect feedback has no dimension
        
        difference = compute_tolerance_euclidean_difference(feedback["tolerances"], tolerances, dimension)
        if feedback["feedback_type"] != "perfect":
            stats[feedback["feedback_type"]]["value"] += feedback["severity_rating"] * (1 / (difference + EPSILON))
            stats[feedback["feedback_type"]]["count"] += 1
        else:  # if feedback is perfect
            stats[feedback["feedback_type"]]["value"] += MAX_SEVERITY * (1 / (difference + EPSILON))
            stats[feedback["feedback_type"]]["count"] += 1

    # compute dimension values for signal calculation
    values = {}
    for stat in stats:
        values[stat] = stats[stat]["value"]
    return values


def compute_signals(values):
    # width signal is positive if shoes are too narrow, negative if shoes are too wide
    width_signal = ((values["too narrow"] - values["too wide"]) /
                    (values["perfect"] + values["too narrow"] + values["too wide"]
                     + EPSILON))
    
    # length signal is positive if shoe is too short, negative if shoe is too long
    length_signal = ((values["too short"] - values["too long"]) /
                    (values["perfect"] + values["too short"] + values["too long"]
                     + EPSILON))
    return width_signal, length_signal

def compute_tolerances(width_signal, length_signal, tolerances, alpha, old_feedback_count, new_feedback_count):
    new_tolerances = {}
    new_tolerances["total_feedback_count"] = old_feedback_count + new_feedback_count

    dimension_type = ""
    for name in tolerances.keys():
        if name in META:
            continue
        # Keep same delta between optimal and min/max
        delta_low = tolerances[name]["opt_low"] - tolerances[name]["min"]
        delta_high = tolerances[name]["max"] - tolerances[name]["opt_high"]

        # Determine which signal to use based on tolerance type
        if tolerances[name]["type"] == "width":
            signal = width_signal
            dimension_type = "width"
        elif tolerances[name]["type"] == "length":
            signal = length_signal
            dimension_type = "length"
        else:
            # if no tol type, error
            raise ValueError(f"Invalid tolerance type for {name}: {tolerances[name]['type']}")

        opt_low = tolerances[name]["opt_low"]
        opt_high = tolerances[name]["opt_high"]

        # Shift optimal range
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