import os
import re
from playwright.sync_api import Playwright, sync_playwright  # ✅ Capital P for Playwright


def run(playwright: Playwright) -> None:  # ✅ Capital P as type hint
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    # 1. Go to login page
    page.goto("https://www.naukri.com/nlogin/login")

    # 2. Fill in credentials
    page.get_by_role("textbox", name="Enter Email ID / Username").fill("vijeth.work774@gmail.com")
    page.get_by_role("textbox", name="Enter Password").fill("Vijeth@1234")

    # 3. Click Login button
    page.get_by_role("button", name="Login", exact=True).click()

    # 4. Wait for login to complete (profile image confirms we are logged in)
    page.get_by_role("img", name="naukri user profile img").wait_for(state="visible", timeout=15000)

    # 5. Navigate directly to profile page (avoids flaky dropdown clicks)
    page.goto("https://www.naukri.com/mnjuser/profile")

    # 6. Wait for the "Update resume" button to appear on the profile page
    page.get_by_role("button", name="Update resume").wait_for(state="visible", timeout=15000)

    # 7. Click "Update resume" and intercept the file chooser popup
    with page.expect_file_chooser() as fc_info:
        page.get_by_role("button", name="Update resume").click()

    # 8. Set your resume file path here
    file_chooser = fc_info.value
    file_chooser.set_files(r"C:\Users\Vijeth Gowda\Desktop\MY RESUME\Vijeth E_Resume2.pdf")

    # 9. Wait 5 seconds to let the file upload complete over the network
    page.wait_for_timeout(5000)

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:  # ✅ lowercase playwright here is fine (it's the instance)
    run(playwright)
