import time
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright



def get_google_calendar_datekey(date_str):
    """ Calcualte the Google datekey for webscrapping, from https://stackoverflow.com/questions/58080616/googlecalendar-datekey
        Formula = (Current_Year - 1970) * 512 + month * 32 + day
    """
    date_obj = datetime.strptime(date_str, "%d%m%Y")
    y = date_obj.year
    m = date_obj.month
    d = date_obj.day

    datekey = ((y - 1970) << 9) + (m << 5) + d

    return datekey


def check_if_google_calendar_login():
    """ Check if 
    """

    selector = '[aria-label="Switch to Tasks"],[data-g-action="sign in"]'

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context("session", headless=True)
        page = context.new_page()

        page.goto("https://calendar.google.com")
        try:
            element = page.wait_for_selector(selector, timeout=0)
            label = element.get_attribute("aria-label")

            if label == "Switch to Tasks":
                context.close()
                return True

            elif label == "sign in":
                context.close()
                return True

        except Exception as e:
            context.close()
            return False


def parse_google_timestr_to_24h_range(time_str):
    """
    Parses Google Calendar time strings extracted from web scraping into range pair (start_24h, end_24h) in 24-hours format .

    Examples:
    - 'All day' -> (00:00, 23:59)
    - '10am' -> (10:00, 23:59)
    - 'until 10am' -> (00:00, 10:00)
    - '10 – 11am' -> (10:00, 11:00)
    """
    t_clean = time_str.lower().replace("–", "-").strip()

    if t_clean == "all day":
        return "00:00", "23:59"

    def to_24h(t, force_p=None):
        p = "pm" if "pm" in t else ("am" if "am" in t else force_p)
        digits = t.replace("am", "").replace("pm", "").strip()
        # Handle "10" vs "10:30"
        fmt = "%I:%M" if ":" in digits else "%I"
        dt = datetime.strptime(digits, fmt)
        h = dt.hour
        if p == "pm" and h != 12:
            h += 12
        elif p == "am" and h == 12:
            h = 0
        return f"{h:02d}:{dt.minute:02d}"

    try:
        # Pattern: "until 10am"
        if t_clean.startswith("until"):
            time_part = t_clean.replace("until", "").strip()
            return "00:00", to_24h(time_part)

        # Pattern: "10am - 11am" or "10-11am"
        if "-" in t_clean:
            start_p, end_p = [x.strip() for x in t_clean.split("-")]
            is_end_pm = "pm" in end_p

            # Logic for start period (e.g., 11-1pm)
            start_p_final = (
                "pm"
                if "pm" in start_p
                else ("am" if "am" in start_p else ("pm" if is_end_pm else "am"))
            )

            # Cross-over check for 11-1pm
            if not any(x in start_p for x in ["am", "pm"]):
                s_val = int(start_p.split(":")[0])
                e_val = int(end_p.replace("am", "").replace("pm", "").split(":")[0])
                if is_end_pm and s_val > e_val and s_val != 12:
                    start_p_final = "am"

            return to_24h(start_p, start_p_final), to_24h(end_p)

        # Pattern: "10am" (Single time means starting then until end of day)
        else:
            return to_24h(t_clean), "23:59"

    except Exception:
        return None, None


def validate_meeting_time(meeting):
    """
    Validates a meeting dictionary for:
    1. Valid date/time formats.
    2. end_date not being before start_date.
    3. end_time not being before start_time on the same day.
    """
    try:
        # 1. Parse strings into datetime objects
        # Format: 31/12/2025 and 01:00pm
        start_dt = datetime.strptime(
            f"{meeting['start_date']} {meeting['start_time']}", "%d/%m/%Y %I:%M%p"
        )
        end_dt = datetime.strptime(
            f"{meeting['end_date']} {meeting['end_time']}", "%d/%m/%Y %I:%M%p"
        )

        # 2. Check: Is the end after the start?
        if end_dt <= start_dt:
            # Specific check for your example: same day but 12:00am (00:00) vs 01:00pm (13:00)
            if meeting["start_date"] == meeting["end_date"]:
                return (
                    False,
                    "End time is earlier than or equal to start time on the same day.",
                )
            return False, "End date/time cannot be before start date/time."

        return True, "Valid meeting time."

    except ValueError as e:
        # This catches invalid dates (e.g., 32/12/2025) or bad formatting
        return False, f"Your date is likely invalid."


def parse_calendar_time(time_str):
    """
    All day -> 00:00-23:59
    10 – 10:30am -> 10:00-10:30
    10:30am – 5:21pm -> 10:30-17:21
    11 – 1pm -> 11:00-13:00

    """
    if time_str.lower() == "all day":
        return "00:00-23:59"

    clean_str = time_str.replace("–", "-").replace(" ", "")

    try:
        start_part, end_part = clean_str.split("-")

        # Determine if the whole range is AM or PM based on the end_part
        # e.g., in "10-11am", both are am. In "10:30am-5:21pm", they are different.
        is_pm = "pm" in end_part.lower()
        is_am = "am" in end_part.lower()

        def to_24h(t_part, force_period=None):
            # Remove am/pm labels for calculation
            label = (
                "pm"
                if "pm" in t_part.lower()
                else ("am" if "am" in t_part.lower() else force_period)
            )
            time_digits = t_part.lower().replace("am", "").replace("pm", "")

            # Handle formats like "10" vs "10:30"
            if ":" in time_digits:
                dt = datetime.strptime(time_digits, "%I:%M")
            else:
                dt = datetime.strptime(time_digits, "%I")

            # Adjust for PM if necessary
            hour = dt.hour
            if label == "pm" and hour != 12:
                hour += 12
            elif label == "am" and hour == 12:
                hour = 0

            return f"{hour:02d}:{dt.minute:02d}"

        # If the start part doesn't have its own am/pm, it usually shares the end part's period
        # Example: "10-11am" -> 10 is am. "10-1pm" -> 10 is am (most calendars)
        start_period = (
            "pm"
            if "pm" in start_part.lower()
            else ("am" if "am" in start_part.lower() else ("pm" if is_pm else "am"))
        )

        # Edge case: 11-1pm (11 is am, 1 is pm)
        if not ("am" in start_part.lower() or "pm" in start_part.lower()):
            start_val = int(start_part.split(":")[0])
            end_val = int(end_part.replace("am", "").replace("pm", "").split(":")[0])
            if is_pm and start_val > end_val and start_val != 12:
                start_period = "am"

        formatted_start = to_24h(start_part, start_period)
        formatted_end = to_24h(end_part)

        return f"{formatted_start}-{formatted_end}"

    except Exception as e:
        return f"Error parsing: {time_str}"


def split_time_period(appointment):
    """
    {
        'start_date': '31/12/2025', 'end_date': '02/01/2026',
        'start_time': '09:00pm', 'end_time': '10:00pm'
    }
    => ['31122025,21:00-23:59', '01012026,00:00-23:59', '02012026,00:00-22:00']

    """
    # 1. Parse dates and times into datetime objects for calculation
    # Format: 31/12/2025 09:00pm
    start_dt = datetime.strptime(
        f"{appointment['start_date']} {appointment['start_time']}", "%d/%m/%Y %I:%M%p"
    )
    end_dt = datetime.strptime(
        f"{appointment['end_date']} {appointment['end_time']}", "%d/%m/%Y %I:%M%p"
    )

    # 2. If it's the same day, handle simply
    if start_dt.date() == end_dt.date():
        return [
            f"{start_dt.strftime('%d%m%Y')},{start_dt.strftime('%H:%M')}-{end_dt.strftime('%H:%M')}"
        ]

    result = []
    current_date = start_dt.date()

    # 3. Iterate through each day from start to end
    while current_date <= end_dt.date():
        date_str = current_date.strftime("%d%m%Y")

        if current_date == start_dt.date():
            # First day: starts at user's start_time, goes until the end of that day
            result.append(f"{date_str},{start_dt.strftime('%H:%M')}-23:59")

        elif current_date == end_dt.date():
            # Last day: starts at midnight, goes until user's end_time
            result.append(f"{date_str},00:00-{end_dt.strftime('%H:%M')}")

        else:
            # Middle day(s): full 24-hour block
            result.append(f"{date_str},00:00-23:59")

        # Move to the next calendar day
        current_date += timedelta(days=1)

    return result


def find_conflicting_events(scheduled_str, existing_events):
    """Given a scheduled time like '31/12/2025,09:00-11:00' and the list of events during that day, return the list of time conflicted events.

    The list of event looks like this:
    [['10 – 10:30am', 'Meeting', 'tom abc, Accepted'], ['10:30am – 5:21pm', 'Meeting', 'tom abc, Accepted'], ['until 1pm', 'M', ''], ["10am", "M", ""]]

    scheduled_str: '31122025,13:00-14:00'

    existing_events:
    [(('00:00', '23:59'), 'Meeting with Tim'),
    (('00:00', '23:59'), "New Year's Eve"),
    (('00:00', '23:59'), 'New Year’s Eve'),
    (('10:00', '10:30'), 'Meeting'),
    (('10:30', '17:21'), 'Meeting')]
    """

    conflicted_items = []

    try:
        # Expected format from split_time_period: 'DDMMYYYY,HH:MM-HH:MM'
        _, time_part = scheduled_str.split(",")
        s_start, s_end = time_part.split("-")
    except ValueError:
        return "Error: Invalid scheduled_time format."

    for event in existing_events:
        e_time_str = event[0]
        e_name = event[1]

        e_start, e_end = event[0]
        if not e_start:
            continue

        # Overlap Check: (StartA < EndB) and (EndA > StartB)
        if s_start < e_end and s_end > e_start:
            conflicted_items.append((e_time_str, e_name))

    return conflicted_items


def generate_conflict_message(conflict_data):
    convert_t_str = (
        lambda t_str: datetime.strptime(t_str, "%H:%M")
        .strftime("%I:%M%p")
        .lower()
        .lstrip("0")
    )
    to_ampm = (
        lambda time_tuple: f"{convert_t_str(time_tuple[0])} to {convert_t_str(time_tuple[1])}"
    )

    if not conflict_data:
        return "No conflicts found."

    lines = ["Below are the conflicted events:"]

    for date, events in conflict_data.items():
        # Add the date as a bolded or distinct header
        lines.append(f"\n{date}:")

        for time_range_str, event_name in events:
            # Normalize dashes and strip whitespace
            # clean_time = time_str.replace('–', '-').strip()
            clean_time = to_ampm(time_range_str)
            # Indent events for better scannability
            lines.append(f"  - {event_name} ({clean_time})")

    return "\n".join(lines)


def find_conflicting_events_old(scheduled_str, existing_events):
    """Given a scheduled time like '31/12/2025,09:00-11:00' and the list of events during that day, return the list of time conflicted events.

    The list of event looks like this:
    [['10 – 10:30am', 'Meeting', 'tom abc, Accepted'], ['10:30am – 5:21pm', 'Meeting', 'tom abc, Accepted'], ['until 1pm', 'M', ''], ["10am", "M", ""]]

    """

    def parse_to_range(time_str):
        """
        Parses various Google Calendar time strings into (start_24h, end_24h).
        Handles:
        - 'All day' -> 00:00, 23:59
        - '10am' -> 10:00, 23:59
        - 'until 10am' -> 00:00, 10:00
        - '10 – 11am' -> 10:00, 11:00
        """
        t_clean = time_str.lower().replace("–", "-").strip()

        if t_clean == "all day":
            return "00:00", "23:59"

        def to_24h(t, force_p=None):
            p = "pm" if "pm" in t else ("am" if "am" in t else force_p)
            digits = t.replace("am", "").replace("pm", "").strip()
            # Handle "10" vs "10:30"
            fmt = "%I:%M" if ":" in digits else "%I"
            dt = datetime.strptime(digits, fmt)
            h = dt.hour
            if p == "pm" and h != 12:
                h += 12
            elif p == "am" and h == 12:
                h = 0
            return f"{h:02d}:{dt.minute:02d}"

        try:
            # Pattern: "until 10am"
            if t_clean.startswith("until"):
                time_part = t_clean.replace("until", "").strip()
                return "00:00", to_24h(time_part)

            # Pattern: "10am - 11am" or "10-11am"
            if "-" in t_clean:
                start_p, end_p = [x.strip() for x in t_clean.split("-")]
                is_end_pm = "pm" in end_p

                # Logic for start period (e.g., 11-1pm)
                start_p_final = (
                    "pm"
                    if "pm" in start_p
                    else ("am" if "am" in start_p else ("pm" if is_end_pm else "am"))
                )

                # Cross-over check for 11-1pm
                if not any(x in start_p for x in ["am", "pm"]):
                    s_val = int(start_p.split(":")[0])
                    e_val = int(end_p.replace("am", "").replace("pm", "").split(":")[0])
                    if is_end_pm and s_val > e_val and s_val != 12:
                        start_p_final = "am"

                return to_24h(start_p, start_p_final), to_24h(end_p)

            # Pattern: "10am" (Single time means starting then until end of day)
            else:
                return to_24h(t_clean), "23:59"

        except Exception:
            return None, None

    conflicted_items = []

    try:
        # Expected format from split_time_period: 'DDMMYYYY,HH:MM-HH:MM'
        _, time_part = scheduled_str.split(",")
        s_start, s_end = time_part.split("-")
    except ValueError:
        return "Error: Invalid scheduled_time format."

    for event in existing_events:
        e_time_str = event[0]
        e_name = event[1]

        e_start, e_end = parse_to_range(e_time_str)
        if not e_start:
            continue

        # Overlap Check: (StartA < EndB) and (EndA > StartB)
        if s_start < e_end and s_end > e_start:
            conflicted_items.append((e_time_str, e_name))

    return conflicted_items


async def add_calendar_event(schedule_detail: dict):
    if schedule_detail["meeting_name"] == "":
        schedule_detail["meeting_name"] = "Meeting"
    # Use the async_playwright context manager
    async with async_playwright() as p:
        # Launching persistent context is also an async action
        context = await p.chromium.launch_persistent_context(
            "session",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )

        page = await context.new_page()

        try:
            await page.goto("https://calendar.google.com")

            # Wait for the login state/main grid
            # Use a long timeout instead of 0 to prevent the API from hanging forever
            await page.wait_for_selector(
                '[aria-label="Switch to Tasks"]', timeout=60000
            )

            # Navigate to the event creation page
            await page.goto("https://calendar.google.com/calendar/r/eventedit")
            await page.wait_for_selector('[aria-label="Save"]', timeout=10000)

            print("Start filling information...")

            format_date = lambda d: datetime.strptime(d, "%d/%m/%Y").strftime(
                "%m/%d/%Y"
            )

            # Every action (fill, click, etc.) must be awaited
            await page.fill(
                'input[aria-label="Title"]', schedule_detail["meeting_name"]
            )
            await page.fill(
                'input[aria-label="Start date"]',
                format_date(schedule_detail["start_date"]),
            )
            await page.fill(
                'input[aria-label="Start time"]', schedule_detail["start_time"]
            )
            await page.fill(
                'input[aria-label="End date"]', format_date(schedule_detail["end_date"])
            )
            await page.fill('input[aria-label="End time"]', schedule_detail["end_time"])
            await page.fill(
                'input[aria-label="Add location"]', schedule_detail["location"]
            )
            await page.fill(
                'div[aria-label="Description"]', schedule_detail["description"]
            )

            # Click save and wait for the network to settle to ensure the save completes
            await page.get_by_label("Save").click()
            await page.wait_for_load_state("networkidle")

            print("✅ Event added")
            assistant_response = "Great! I've added that to your calendar."
            success = True

        except Exception as e:
            print(f"❌ Error adding event: {e}")
            assistant_response = (
                "I ran into an issue saving the event. Please check the browser window."
            )
            success = False
        finally:
            # Closing the context is also async
            await context.close()

    return {"reply": assistant_response, "success": success}


async def get_event_from_date(dateStr) -> list[list[str]]:
    """
    Check schedule conflict using Async Playwright
    """
    date_obj = datetime.strptime(dateStr, "%d%m%Y")
    formatted_date = date_obj.strftime("%b %d, %Y")
    events = []

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            "session",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = await context.new_page()
        await page.goto("https://calendar.google.com")

        # Await the selector
        await page.wait_for_selector('div[role="main"]')

        # Use Schedule view
        await page.keyboard.press("a")
        await page.wait_for_timeout(1000)  # Async replacement for time.sleep

        # Toggle "Go to date"
        await page.keyboard.press("g")
        await page.wait_for_selector('input[aria-label="Date"]')
        await page.wait_for_timeout(1000)

        await page.keyboard.type(formatted_date, delay=100)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(2000)  # Wait for view to update

        target_key = get_google_calendar_datekey(dateStr)
        day_container = page.locator(f'div[data-datekey="{target_key}"]')

        # .all() is an async method in the async API
        rows = await day_container.locator('div[role="row"]').all()

        for row in rows:
            second_div = row.locator("xpath=./div[2]")
            # .count() is async
            if await second_div.count() > 0:
                # .all_inner_texts() is async
                nested_texts = await second_div.locator("div").all_inner_texts()

                clean_row_list = [text.strip() for text in nested_texts if text.strip()]
                unique_row_list = list(dict.fromkeys(clean_row_list))

                if unique_row_list:
                    events.append(unique_row_list)

        await context.close()

    return events



if __name__ == "__main__":
    add_calendar_event()
    # print(get_google_calendar_datekey("02142026"))
    # events = get_event_from_date("31122025")
    # print(events)

    # assistant = Gemini()

    # print(assistant.ask_a_question("what, do you know mocking bird?"))
