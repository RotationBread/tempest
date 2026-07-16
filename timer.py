import argparse
from datetime import datetime, timedelta
from decimal import Decimal, getcontext, ROUND_FLOOR
import tkinter as tk
from tkinter import font as tkfont
import math

getcontext().prec =100


def parse_datetime(date_str):
    return datetime.strptime(date_str, "%b %d %Y %I:%M%p")


def decimal_total_seconds(td):
    return (
        Decimal(td.days) * Decimal(86400)
        + Decimal(td.seconds)
        + Decimal(td.microseconds) / Decimal(1000000)
    )


def format_timedelta(td, subsecond=False):
    if isinstance(td, timedelta):
        total_seconds = decimal_total_seconds(td)
    else:
        total_seconds = Decimal(td)

    if total_seconds <= 0:
        return "00:00:00"

    total_seconds_int = int(total_seconds)
    days, remainder = divmod(total_seconds_int, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    if days > 0:
        return f"{days}d {hours:02}:{minutes:02}:{seconds:02}"

    if subsecond and total_seconds < Decimal("10"):
        milliseconds = int((total_seconds - total_seconds_int) * Decimal(1000))
        return f"{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}"

    return f"{hours:02}:{minutes:02}:{seconds:02}"


def first_sig_decimal_place(value):
    """
    Returns decimal places needed to display the first significant digit.

    Examples:
    0.00009577 -> 5
    0.0000000239 -> 8
    0.42 -> 1
    """

    value = to_decimal(value)
    if value == 0:
        return 0

    # use Decimal.log10 for high precision on very small values
    magnitude = int(value.copy_abs().log10().to_integral_value(rounding=ROUND_FLOOR))

    return max(0, -magnitude)


def display_decimal_places_for_step(value, step):
    value = to_decimal(value)
    step = abs(to_decimal(step))
    if step == 0:
        return first_sig_decimal_place(value) + 2
    return first_sig_decimal_place(step)


def to_decimal(value):
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def get_percentage(seconds):
    """Return percentage based on seconds remaining using
    P(s) = 100 * (0.9 * e^(-0.02 * s) + 0.1 * e^(-0.0005 * s)).

    This increases the end-of-countdown speed by giving the fast term
    a steeper decay rate near x=0 while preserving a slow long tail.
    """
    seconds = to_decimal(seconds)
    if seconds <= 0:
        return Decimal(100)

    a = Decimal('0.99') * (Decimal('-0.2') * seconds).exp()
    b = Decimal('0.01') * (Decimal('-0.0005') * seconds).exp()
    return Decimal(100) * (a + b)


def get_rate(seconds):
    seconds = to_decimal(seconds)
    if seconds <= Decimal(1):
        return Decimal(0)

    return abs(
        get_percentage(seconds - Decimal(1))
        -
        get_percentage(seconds)
    )


def get_acceleration(seconds):
    seconds = to_decimal(seconds)
    if seconds <= Decimal(2):
        return Decimal(0)

    return abs(
        get_rate(seconds - Decimal(1))
        -
        get_rate(seconds)
    )


def get_jerk(seconds):
    seconds = to_decimal(seconds)
    if seconds <= Decimal(3):
        return Decimal(0)

    return abs(
        get_acceleration(seconds - Decimal(1))
        -
        get_acceleration(seconds)
    )


def time_until_next_percentage_digit(seconds, percentage):
    seconds = to_decimal(seconds)
    percentage = to_decimal(percentage)
    if percentage <= 0 or percentage >= 100 or seconds <= 0:
        return Decimal(0)

    magnitude = int(percentage.log10().to_integral_value(rounding=ROUND_FLOOR))
    step = Decimal(10) ** magnitude

    target = (
        (percentage // step) + Decimal(1)
    ) * step

    if target > Decimal(100):
        target = Decimal(100)

    # find seconds where get_percentage(s) == target
    event_s = find_seconds_for_threshold(target, seconds, get_percentage, Decimal(0))

    return seconds - event_s


def time_until_next_percentage_magnitude(seconds, percentage):
    seconds = to_decimal(seconds)
    percentage = to_decimal(percentage)
    if percentage <= 0 or percentage >= 100 or seconds <= 0:
        return Decimal(0)

    magnitude = int(percentage.log10().to_integral_value(rounding=ROUND_FLOOR))
    target = Decimal(10) ** (magnitude + 1)

    if target > Decimal(100):
        target = Decimal(100)

    event_s = find_seconds_for_threshold(target, seconds, get_percentage, Decimal(0))

    return seconds - event_s


def time_until_next_rate_digit(seconds, rate):
    seconds = to_decimal(seconds)
    rate = to_decimal(rate)
    if rate <= 0 or seconds <= Decimal(2):
        return Decimal(0)
    magnitude = int(rate.log10().to_integral_value(rounding=ROUND_FLOOR))
    target = Decimal(10) ** (magnitude + 1)

    low = Decimal(2)
    high = seconds

    for _ in range(80):
        mid = (low + high) / Decimal(2)
        if get_rate(mid) < target:
            high = mid
        else:
            low = mid

    return seconds - ((low + high) / Decimal(2))


def time_until_next_accel_digit(seconds, accel):
    seconds = to_decimal(seconds)
    accel = to_decimal(accel)
    if accel <= 0 or seconds <= Decimal(2):
        return Decimal(0)
    magnitude = int(accel.log10().to_integral_value(rounding=ROUND_FLOOR))
    target = Decimal(10) ** (magnitude + 1)

    low = Decimal(2)
    high = seconds

    for _ in range(80):
        mid = (low + high) / Decimal(2)
        if get_acceleration(mid) < target:
            high = mid
        else:
            low = mid

    return seconds - ((low + high) / Decimal(2))


def time_until_next_jerk_digit(seconds, jerk):
    seconds = to_decimal(seconds)
    jerk = to_decimal(jerk)
    if jerk <= 0 or seconds <= Decimal(3):
        return Decimal(0)
    magnitude = int(jerk.log10().to_integral_value(rounding=ROUND_FLOOR))
    target = Decimal(10) ** (magnitude + 1)

    low = Decimal(3)
    high = seconds

    for _ in range(80):
        mid = (low + high) / Decimal(2)
        if get_jerk(mid) < target:
            high = mid
        else:
            low = mid

    return seconds - ((low + high) / Decimal(2))


def format_event_value(value):
    value = to_decimal(value)
    if value == 0:
        return "0"
    magnitude = int(value.copy_abs().log10().to_integral_value(rounding=ROUND_FLOOR))
    decimal_places = max(0, -magnitude)
    return f"{value:.{decimal_places}f}"


def find_seconds_for_threshold(target, current_seconds, func, domain):
    low = domain
    high = current_seconds

    for _ in range(120):
        mid = (low + high) / Decimal(2)
        if func(mid) < target:
            high = mid
        else:
            low = mid

    return (low + high) / Decimal(2)


def generate_percentage_events(current_seconds, now):
    events = []
    if current_seconds <= 0:
        return events

    current_percentage = min(
        Decimal(100),
        get_percentage(current_seconds)
    )
    percentage = current_percentage

    while percentage < Decimal(100):
        if percentage <= 0:
            percentage = Decimal("0.000001")
        magnitude = int(percentage.log10().to_integral_value(rounding=ROUND_FLOOR))
        step = Decimal(10) ** magnitude
        target = ((percentage // step) + Decimal(1)) * step
        if target > Decimal(100):
            target = Decimal(100)

        # compute seconds until the target percentage by numeric search
        event_seconds = find_seconds_for_threshold(target, current_seconds, get_percentage, Decimal(0))
        if event_seconds <= 0 or event_seconds >= current_seconds:
            break

        elapsed = current_seconds - event_seconds
        event_time = now + timedelta(seconds=float(elapsed))
        events.append(
            (event_time, f"Percentage reaches {format_event_value(target)}")
        )

        if target == Decimal(100):
            break

        percentage = target

    return events


def generate_magnitude_events(current_seconds, now, func, domain, label, max_events=20):
    events = []
    if current_seconds <= domain:
        return events

    current_value = func(current_seconds)
    if current_value <= 0:
        return events

    magnitude = int(current_value.copy_abs().log10().to_integral_value(rounding=ROUND_FLOOR))
    threshold = Decimal(10) ** (magnitude + 1)

    for _ in range(max_events):
        event_seconds = find_seconds_for_threshold(
            threshold,
            current_seconds,
            func,
            domain
        )

        if event_seconds <= domain or event_seconds >= current_seconds:
            break

        elapsed = current_seconds - event_seconds
        event_time = now + timedelta(seconds=float(elapsed))
        events.append(
            (event_time, f"{label} reaches {format_event_value(threshold)}")
        )

        threshold *= 10

    return events


class CountdownWidget:
    def __init__(self, target_time):
        self.target_time = target_time

        self.root = tk.Tk()
        self.root.title("Countdown")

        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.85)
        self.root.configure(bg="#111111")

        self.main_label = tk.Label(
            self.root,
            # font size stored on the instance so it can be adjusted when needed
            font=("Consolas", 22, "bold"),
            fg="white",
            bg="#111111"
        )
        self.main_label.pack()
        self.main_font_original_size = 22

        self.next_label = tk.Label(
            self.root,
            # keep next label font locked at 8 as requested
            font=("Consolas", 8),
            fg="white",
            bg="#111111",
            justify="center"
        )
        self.next_label.pack()

        self.offset_x = 0
        self.offset_y = 0

        for label in (self.main_label, self.next_label):
            label.bind("<Button-1>", self.start_move)
            label.bind("<B1-Motion>", self.do_move)

        self.root.update_idletasks()
        self.resize_window(center=True)
        self.update()
        # start console updater (prints status block every second)
        self.update_console()


    def resize_window(self, center=False):
        self.root.update_idletasks()

        # adjust main label font size if the calculated width exceeds screen width
        screen_width = self.root.winfo_screenwidth()

        if not hasattr(self, 'main_font_original_size'):
            self.main_font_original_size = 22
        if not hasattr(self, 'main_font_size'):
            self.main_font_size = self.main_font_original_size

        current_size = int(self.main_font_size)
        target_size = int(self.main_font_original_size)

        # first, see if the original size fits without applying it
        while target_size > current_size:
            test_font = tkfont.Font(family="Consolas", size=target_size, weight="bold")
            main_width = max(
                test_font.measure(line)
                for line in self.main_label.cget("text").split("\n")
            )
            width = max(main_width, self.next_label.winfo_reqwidth()) + 30
            if width <= screen_width:
                break
            target_size -= 1

        # then shrink from the target size if needed
        while target_size > 8:
            test_font = tkfont.Font(family="Consolas", size=target_size, weight="bold")
            main_width = max(
                test_font.measure(line)
                for line in self.main_label.cget("text").split("\n")
            )
            width = max(main_width, self.next_label.winfo_reqwidth()) + 30
            if width <= screen_width:
                break
            target_size -= 1

        if target_size != current_size:
            self.main_font_size = target_size
            self.main_label.config(font=("Consolas", target_size, "bold"))

        width = max(
            self.main_label.winfo_reqwidth(),
            self.next_label.winfo_reqwidth()
        ) + 30

        # compute final height after font adjustments
        height = (
            self.main_label.winfo_reqheight()
            +
            self.next_label.winfo_reqheight()
        )

        if center:
            x = (self.root.winfo_screenwidth() - width) // 2
            y = 0
        else:
            x = self.root.winfo_x()
            y = self.root.winfo_y()

        self.root.geometry(
            f"{width}x{height}+{x}+{y}"
        )


    def start_move(self, event):
        self.offset_x = event.x
        self.offset_y = event.y


    def do_move(self, event):
        self.root.geometry(
            f"+{event.x_root - self.offset_x}+{event.y_root - self.offset_y}"
        )


    def update(self):
        remaining = self.target_time - datetime.now()
        seconds = decimal_total_seconds(remaining)

        if seconds > 0:
            percentage = get_percentage(seconds)
        else:
            percentage = Decimal(100)

        percentage = min(Decimal(100), percentage)

        rate = get_rate(seconds)
        accel = get_acceleration(seconds)
        jerk = get_jerk(seconds)

        percent_dp = first_sig_decimal_place(rate)
        rate_dp = first_sig_decimal_place(rate - get_rate(seconds - Decimal(1)))
        accel_step = abs(accel - get_acceleration(seconds - Decimal(1)))
        accel_dp = display_decimal_places_for_step(accel, accel_step)
        jerk_step = abs(jerk - get_jerk(seconds - Decimal(1)))
        jerk_dp = display_decimal_places_for_step(jerk, jerk_step)

        # store values for console updater
        self._console_seconds = int(seconds if seconds > 0 else 0)
        self._console_percentage = percentage
        self._console_percent_dp = percent_dp
        self._console_rate = rate
        self._console_rate_dp = rate_dp
        self._console_accel = accel
        self._console_accel_dp = accel_dp
        self._console_jerk = jerk
        self._console_jerk_dp = jerk_dp

        next_percent = time_until_next_percentage_digit(seconds, percentage)
        next_percent_magnitude = time_until_next_percentage_magnitude(seconds, percentage)
        next_rate = time_until_next_rate_digit(seconds, rate)
        next_accel = time_until_next_accel_digit(seconds, accel)
        next_jerk = time_until_next_jerk_digit(seconds, jerk)

        if seconds <= 0:
            main_text = "00:00:00 (100%)"
            secondary_text = ""
        else:
            formatted_remaining = format_timedelta(remaining, subsecond=seconds < Decimal("10"))

            main_text = (
                f"{formatted_remaining} "
                f"({percentage:.{percent_dp}f}%)"
            )

            secondary_text = (
                f"Next digit: "
                f"{format_timedelta(next_percent)} "
                f"({format_timedelta(next_percent_magnitude)})\n"
                f"Rate: "
                f"{rate:.{rate_dp}f}%/s "
                f"({format_timedelta(next_rate)})\n"
                f"Accel: "
                f"{accel:.{accel_dp}f}%/s² "
                f"({format_timedelta(next_accel)})\n"
                f"Jerk: "
                f"{jerk:.{jerk_dp}f}%/s³ "
                f"({format_timedelta(next_jerk)})"
            )

        self.main_label.config(text=main_text)
        self.next_label.config(text=secondary_text)

        self.resize_window()

        self.root.after(100, self.update)

    def update_console(self):
        # print a compact block, clearing the console so lines are reused
        try:
            # clear screen and move cursor home
            print('\x1b[2J\x1b[H', end='')

            # Seconds (whole number)
            print(f"Seconds: {self._console_seconds}")

            # Percentage in scientific notation, rounded to shown dp
            pct = self._console_percentage
            pct_dp = max(0, min(int(self._console_percent_dp), 8))
            print(f"Percentage: {format(pct, f'.{pct_dp}E')}")

            # Rate, Accel, Jerk in scientific notation
            r = self._console_rate
            rdp = max(0, min(int(self._console_rate_dp), 8))
            print(f"Rate: {format(r, f'.{rdp}E')} %/s")

            a = self._console_accel
            adp = max(0, min(int(self._console_accel_dp), 8))
            print(f"Accel: {format(a, f'.{adp}E')} %/s^2")

            j = self._console_jerk
            jdp = max(0, min(int(self._console_jerk_dp), 8))
            print(f"Jerk: {format(j, f'.{jdp}E')} %/s^3")

            # flush to ensure immediate console update
            import sys
            sys.stdout.flush()
        except Exception:
            pass

        # schedule next console update in 1s
        self.root.after(1000, self.update_console)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--date",
        nargs="+",
        required=True,
        help="Example: Jul 12 2026 1:00pm"
    )

    args = parser.parse_args()

    try:
        target_time = parse_datetime(" ".join(args.date))
    except ValueError:
        print("Invalid format. Use: Jul 12 2026 1:00pm")
        return

    CountdownWidget(target_time)
    tk.mainloop()


if __name__ == "__main__":
    main()