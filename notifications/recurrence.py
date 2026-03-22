"""
Compute next run time for recurring notification schedules (Google Meet–style).
"""

from datetime import date, datetime, time, timedelta

from django.utils import timezone


def get_next_run_at(schedule) -> datetime | None:
    """
    Compute the next run datetime for a RecurringNotificationSchedule.
    - schedule: instance with frequency, interval, time_of_day, weekdays, month_day,
                year_month, year_month_day, start_date, end_date, end_after_occurrences,
                last_run_at, occurrence_count.
    Returns timezone-aware datetime or None if no more runs.
    """
    tz = timezone.get_current_timezone() if timezone.is_naive(datetime.now()) else None
    now = timezone.now()
    if tz:
        now = timezone.make_aware(now, tz) if timezone.is_naive(now) else now
    today = now.date()
    send_time = schedule.time_of_day

    # End conditions
    if schedule.end_date and today > schedule.end_date:
        return None
    if (
        schedule.end_after_occurrences is not None
        and schedule.occurrence_count >= schedule.end_after_occurrences
    ):
        return None

    freq = schedule.frequency
    interval = schedule.interval or 1
    is_first = schedule.last_run_at is None

    if schedule.last_run_at:
        base = schedule.last_run_at
        if tz and timezone.is_naive(base):
            base = timezone.make_aware(base, tz)
        base_date = base.date()
    else:
        base_date = schedule.start_date

    if freq == "DAILY":
        if is_first:
            next_date = base_date
        else:
            next_date = base_date + timedelta(days=interval)
    elif freq == "WEEKLY":
        weekdays = schedule.weekdays
        if not weekdays or not isinstance(weekdays, list):
            weekdays = [base_date.weekday()]
        if is_first:
            next_date = _first_weekday_on_or_after(base_date, weekdays)
        else:
            next_date = _next_weekday_after(base_date, weekdays, interval)
    elif freq == "MONTHLY":
        day = schedule.month_day or (base_date.day if is_first else 1)
        day = min(day, 28)
        if is_first:
            next_date = _first_month_day_on_or_after(base_date, day)
        else:
            next_date = _next_month_date(base_date, day, interval)
    elif freq == "YEARLY":
        m = schedule.year_month or base_date.month
        d = schedule.year_month_day or base_date.day
        if is_first:
            next_date = _first_yearly_on_or_after(base_date, m, d)
        else:
            next_date = _next_year_date(base_date, m, d, interval)
    else:
        next_date = base_date if is_first else base_date + timedelta(days=1)

    if schedule.end_date and next_date > schedule.end_date:
        return None
    if (
        schedule.end_after_occurrences is not None
        and schedule.occurrence_count + 1 > schedule.end_after_occurrences
    ):
        return None

    next_dt = datetime.combine(next_date, send_time)
    if tz:
        next_dt = timezone.make_aware(next_dt, tz)
    return next_dt


def _first_weekday_on_or_after(from_date, weekdays):
    """First date on or after from_date whose weekday is in weekdays (0=Mon, 6=Sun)."""
    w = from_date.weekday()
    for _ in range(7):
        if w in weekdays:
            return from_date
        from_date += timedelta(days=1)
        w = from_date.weekday()
    return from_date


def _next_weekday_after(from_date, weekdays, interval_weeks):
    """Next occurrence of one of weekdays, at least interval_weeks after from_date."""
    target = from_date + timedelta(weeks=interval_weeks)
    w = target.weekday()
    for _ in range(7):
        if w in weekdays and target > from_date:
            return target
        target += timedelta(days=1)
        w = target.weekday()
    return target


def _first_month_day_on_or_after(from_date, day_of_month):
    """First date on or after from_date that has day of month = day_of_month."""
    import calendar

    y, m = from_date.year, from_date.month
    _, last = calendar.monthrange(y, m)
    d = min(day_of_month, last)
    cand = date(y, m, d)
    if cand >= from_date:
        return cand
    # Next month
    if m == 12:
        y, m = y + 1, 1
    else:
        m += 1
    _, last = calendar.monthrange(y, m)
    return date(y, m, min(day_of_month, last))


def _first_yearly_on_or_after(from_date, month, day_of_month):
    """First (month, day) on or after from_date."""
    import calendar

    y = from_date.year
    _, last = calendar.monthrange(y, month)
    d = min(day_of_month, last)
    cand = date(y, month, d)
    if cand >= from_date:
        return cand
    return date(y + 1, month, min(day_of_month, calendar.monthrange(y + 1, month)[1]))


def _next_month_date(from_date, day_of_month, interval_months):
    """Next date that is day_of_month in a month >= interval_months from from_date."""
    year, month = from_date.year, from_date.month
    month += interval_months
    while month > 12:
        month -= 12
        year += 1
    # Last day of month cap
    try:
        return date(year, month, min(day_of_month, 28))
    except ValueError:
        import calendar

        _, last = calendar.monthrange(year, month)
        return date(year, month, min(day_of_month, last))


def _next_year_date(from_date, month, day_of_month, interval_years):
    """Next date that is (month, day) at least interval_years after from_date."""
    year = from_date.year + interval_years
    try:
        return date(year, month, min(day_of_month, 28))
    except ValueError:
        import calendar

        _, last = calendar.monthrange(year, month)
        return date(year, month, min(day_of_month, last))
