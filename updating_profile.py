import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import Playwright, sync_playwright
from dotenv import load_dotenv

# Load .env file for local development (ignored in GitHub Actions)
load_dotenv()


# Read credentials from environment variables (set via GitHub Secrets)
NAUKRI_EMAIL    = os.environ["NAUKRI_EMAIL"]
NAUKRI_PASSWORD = os.environ["NAUKRI_PASSWORD"]

# Gmail credentials for sending notification
GMAIL_USER     = os.environ["GMAIL_USER"]
GMAIL_APP_PASS = os.environ["GMAIL_APP_PASSWORD"]

# Resume path — relative to repo root (place your PDF as resume/resume.pdf in the repo)
RESUME_PATH = os.path.join(os.path.dirname(__file__), "Vijeth E_Resume2.pdf")


def send_email(success: bool, detail: str = ""):
    """Send a notification email after the Naukri update attempt."""
    subject = "✅ Naukri Resume Updated!" if success else "❌ Naukri Update Failed"
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    if success:
        body = f"""
        <h2 style="color:green;">✅ Resume Updated Successfully</h2>
        <p>Your Naukri resume was automatically updated at <strong>{now}</strong>.</p>
        <p>This keeps your profile fresh and boosts visibility to recruiters!</p>
        """
    else:
        body = f"""
        <h2 style="color:red;">❌ Naukri Update Failed</h2>
        <p>The automated update attempted at <strong>{now}</strong> encountered an error.</p>
        <pre>{detail}</pre>
        <p>Please check your GitHub Actions logs for more info.</p>
        """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = GMAIL_USER  # send to yourself
    msg.attach(MIMEText(body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASS)
        server.sendmail(GMAIL_USER, GMAIL_USER, msg.as_string())
    print(f"📧 Notification email sent to {GMAIL_USER}")


def run(playwright: Playwright) -> None:
    # Auto-detect: headless in GitHub Actions (CI=true), visible locally
    is_ci = os.environ.get("CI", "false").lower() == "true"

    browser = playwright.chromium.launch(
        headless=is_ci,
        slow_mo=0 if is_ci else 500,
        args=[
            "--disable-blink-features=AutomationControlled",  # hide headless flag
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ]
    )

    # Use a real browser user-agent so Naukri doesn't detect automation
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 800},
        locale="en-IN",
    )
    page = context.new_page()

    # Hide webdriver property to avoid bot detection
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    # 1. Go to login page
    page.goto("https://www.naukri.com/nlogin/login", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)  # wait for JS to render login form

    # Take screenshot to debug what CI sees
    page.screenshot(path="login_page.png")
    print(f"📸 Screenshot saved: login_page.png")
    print(f"🌐 Current URL: {page.url}")

    # 2. Wait for email field then fill credentials
    email_input = page.locator("input[placeholder*='Email'], input[type='email'], input[name*='email'], input[id*='email']").first
    email_input.wait_for(state="visible", timeout=30000)
    email_input.fill(NAUKRI_EMAIL)


    password_input = page.locator("input[placeholder*='Password'], input[type='password']").first
    password_input.wait_for(state="visible", timeout=15000)
    password_input.fill(NAUKRI_PASSWORD)

    # 3. Click Login button
    page.locator("button[type='submit'], button:has-text('Login')").first.click()

    # 4. Wait for login to complete
    page.wait_for_load_state("domcontentloaded", timeout=20000)
    page.wait_for_timeout(2000)  # let session cookie settle
    print("✅ Logged in successfully")

    # 5. Navigate directly to profile page
    page.goto("https://www.naukri.com/mnjuser/profile", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)  # let the page render fully

    # 6. Wait for the "Update resume" button
    update_btn = page.locator("button:has-text('Update resume'), input[value='Update resume']").first
    update_btn.wait_for(state="visible", timeout=20000)

    # 7. Click "Update resume" and intercept the file chooser popup
    with page.expect_file_chooser() as fc_info:
        update_btn.click()

    # 8. Upload the resume file from the repo
    file_chooser = fc_info.value
    file_chooser.set_files(RESUME_PATH)
    print(f"📄 Resume file set: {RESUME_PATH}")

    # 9. Wait for upload to complete
    page.wait_for_timeout(6000)

    context.close()
    browser.close()
    print("✅ Resume updated successfully on Naukri!")


try:
    with sync_playwright() as playwright:
        run(playwright)
    send_email(success=True)
except Exception as e:
    print(f"❌ Error: {e}")
    send_email(success=False, detail=str(e))
    raise
