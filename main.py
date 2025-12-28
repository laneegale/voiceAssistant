import time
from playwright.sync_api import sync_playwright

def add_calendar_event():
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            'session', 
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        page = context.new_page()
        page.goto('https://calendar.google.com')

        print("Please log in manually if prompted.")
        try:
            page.wait_for_selector('[aria-label="Switch to tasks"]', timeout=10000)
        except:
            print("Timeout trigger, problems encountered during login")

        page.goto('https://calendar.google.com/calendar/r/eventedit')

        print("Start filling information")
        page.fill('input[aria-label="Title"]', "Playwright Automation Meeting")
        page.fill('input[aria-label="Start date"]', "12/31/2025")
        page.fill('input[aria-label="Start time"]', "9am")
        page.fill('input[aria-label="End date"]', "12/31/2025")
        page.fill('input[aria-label="End time"]', "11am")
        page.fill('input[aria-label="Add location"]', "Dummy place")
        page.fill('div[aria-label="Description"]', "Dummy place")
        page.get_by_label("Save").click()

        print("✅ Event added")
        context.close()

if __name__ == "__main__":
    add_calendar_event()