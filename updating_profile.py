import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import Playwright, sync_playwright

# Read credentials from environment variables (set via GitHub Secrets)
NAUKRI_EMAIL    = os.environ["NAUKRI_EMAIL"]
NAUKRI_PASSWORD = os.environ["NAUKRI_PASSWORD"]

# Gmail credentials for sending notification
GMAIL_USER     = os.environ["GMAIL_USER"]
GMAIL_APP_PASS = os.environ["GMAIL_APP_PASSWORD"]

# Resume path — relative to repo root (place your PDF as resume/resume.pdf in the repo)
RESUME_PATH = os.path.join(os.path.dirname(__file__), "resume", "resume.pdf")


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
    # headless=True is required for GitHub Actions (no display)
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    # 1. Go to login page
    page.goto("https://www.naukri.com/nlogin/login")

    # 2. Fill in credentials from environment variables
    page.get_by_role("textbox", name="Enter Email ID / Username").fill(NAUKRI_EMAIL)
    page.get_by_role("textbox", name="Enter Password").fill(NAUKRI_PASSWORD)

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

    # 8. Upload the resume file from the repo
    file_chooser = fc_info.value
    file_chooser.set_files(RESUME_PATH)

    # 9. Wait 5 seconds to let the file upload complete over the network
    page.wait_for_timeout(5000)

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
