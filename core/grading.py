def assessment_average(assessment_marks, weights):
    """Return (mark, weighted) using a complete 100% policy when available."""
    if not assessment_marks:
        return None, False
    complete = (
        bool(weights)
        and round(sum(float(value) for value in weights.values()), 2) == 100
        and set(assessment_marks).issubset(weights)
        and all(name in assessment_marks for name in weights)
    )
    if complete:
        mark = sum(
            (sum(marks) / len(marks)) * float(weights[name]) / 100
            for name, marks in assessment_marks.items()
        )
        return mark, True
    marks = [mark for values in assessment_marks.values() for mark in values]
    return sum(marks) / len(marks), False
