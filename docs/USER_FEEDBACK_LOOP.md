# User Feedback Loop and Tolerance Training

**Current Version:** 1.0
**Source Files:** `backend/tasks/retrain.py`, `backend/services/feedback_service.py`, `backend/services/tolerance_learning.py`, `backend/services/tolerance_storage.py`

---

## Overview

The user feedback loop takes feedback from users and uses it to adjust the current tolerances used for fit score in accordance with the feedback submitted. For each dimension (length, width, toebox length, and toebox width), there are 4 tolerances: min, opt_low, opt_high, and max. The current version of tolerance retraining only adjusts the optimal band (opt_low and opt_high) and maintains a fixed buffer beteween min and max respectively.

## Formula

The formula to calculate the shift for each tolerance:
shift = alpha * K * signal

1. The learning rate, alpha, is used to scale the shift based on how much new feedback there is compared to how much has already been used for training:
    - alpha = new_feedback_count / (old_feedback_count + new_feedback_count + EPSILON)
        - Epsilon is a small constant used to prevent division by 0

2. K is a small constant to control the severity of the shift. The current value is 0.05.

3. There are two signals for length and width, which control the direction of the shift. These are calculated with aggregated and adjusted values for each kind of feedback.
    - Adjusted Values: Value[feedback_type] = feedback_severity + 1/(distance + EPSILON)
        - feedback types are too narrow, too wide, too short, too long, perfect
        - feedback severity ranges from 1-5 with 5 being the most severe discomfort
        - distance is the euclidean distance between the current tolerances and the tolerances values for when the feedback was submitted
        - Epsilon is a small constant used to prevent division by 0
    - Width Signal: Will have a positive value if shoes are generally too narrow and negative value if shoes are generally too wide
        - (too narrow value - too wide value) / (perfect value + too narrow value + too wide value)
    - Length Signal: Will have a positive value if shoes are generally too short and a negative value if shoes are generally too long
        - (too short value - too long value) / (perfect value + too short value + too long value)

## Retraining

To retrain, navigate to the shoe_shopper directory.

### Activate Virtual Environment
```bash
# macOS/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```


### Start Shell
```bash
python manage.py shell
```

### Retrain
```bash
from backend.tasks.retrain import retrain
retrain()
```
