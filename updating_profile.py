import os
import time
import random
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import Playwright, sync_playwright, TimeoutError as PlaywrightTimeoutError
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


def find_and_fill_email(page, email: str) -> bool:
    """
    Try multiple strategies to find and fill the email/username input.
    Returns True on success, False if none found.
    """
    strategies = [
        # Exact placeholder used by Naukri (most reliable)
        "input[placeholder='Enter Email ID / Username']",
        "input[placeholder*='Email ID']",
        "input[placeholder*='Username']",
        # Attribute-based fallbacks
        "input[type='email']",
        "input[name*='email' i]",
        "input[id*='email' i]",
        "input[name*='user' i]",
        "input[id*='user' i]",
        # Last resort: first text/email input on page
        "input[type='text']:visible",
    ]
    for selector in strategies:
        try:
            loc = page.locator(selector).first
            loc.wait_for(state="visible", timeout=5000)
            loc.click()
            time.sleep(random.uniform(0.2, 0.6))
            loc.fill(email)
            print(f"✅ Email filled via selector: {selector}")
            return True
        except Exception:
            continue
    return False


def run(playwright: Playwright) -> None:
    # Auto-detect: headless in GitHub Actions (CI=true), visible locally
    is_ci = os.environ.get("CI", "false").lower() == "true"

    browser = playwright.chromium.launch(
        headless=is_ci,
        slow_mo=0 if is_ci else 500,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--window-size=1280,800",
        ]
    )

    # Mimic a real Chrome session as closely as possible
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 800},
        locale="en-IN",
        timezone_id="Asia/Kolkata",
        # Simulate a real device with media features
        color_scheme="light",
    )
    page = context.new_page()

    # Comprehensive bot-detection evasion scripts
    page.add_init_script("""
        // Hide webdriver property
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

        // Spoof plugins array (headless has 0, real Chrome has several)
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });

        // Spoof languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-IN', 'en-US', 'en'],
        });

        // Remove headless Chrome traces
        window.chrome = { runtime: {} };
    """)

    # ── STEP 1: Open the login page ──────────────────────────────────────────
    print("🌐 Navigating to Naukri login page...")
    page.goto(
        "https://www.naukri.com/nlogin/login",
        wait_until="networkidle",   # wait until network is truly idle
        timeout=45000,
    )

    # Extra wait for JS-heavy login form to fully render
    page.wait_for_timeout(4000)

    # ── DIAGNOSTICS ──────────────────────────────────────────────────────────
    print(f"🌐 Current URL : {page.url}")
    print(f"📄 Page title  : {page.title()}")
    all_inputs = page.locator("input").all()
    print(f"🔍 Input fields found: {len(all_inputs)}")
    for i, inp in enumerate(all_inputs):
        try:
            print(
                f"   [{i}] type={inp.get_attribute('type')} "
                f"| name={inp.get_attribute('name')} "
                f"| placeholder={inp.get_attribute('placeholder')} "
                f"| id={inp.get_attribute('id')}"
            )
        except Exception:
            pass
    page.screenshot(path="login_page.png", full_page=True)
    print("📸 Screenshot saved: login_page.png")
    # ── END DIAGNOSTICS ──────────────────────────────────────────────────────

    # ── STEP 2: Fill email ────────────────────────────────────────────────────
    if not find_and_fill_email(page, NAUKRI_EMAIL):
        page.screenshot(path="error_email_not_found.png", full_page=True)
        raise RuntimeError(
            "❌ Could not locate the email/username input field. "
            "Check error_email_not_found.png in the Actions artifacts."
        )

    # ── STEP 3: Fill password ─────────────────────────────────────────────────
    pwd_selectors = [
        "input[placeholder='Enter Password']",
        "input[placeholder*='Password' i]",
        "input[type='password']",
    ]
    pwd_filled = False
    for sel in pwd_selectors:
        try:
            pwd_loc = page.locator(sel).first
            pwd_loc.wait_for(state="visible", timeout=8000)
            time.sleep(random.uniform(0.2, 0.5))
            pwd_loc.fill(NAUKRI_PASSWORD)
            print(f"✅ Password filled via selector: {sel}")
            pwd_filled = True
            break
        except Exception:
            continue

    if not pwd_filled:
        raise RuntimeError("❌ Could not locate the password input field.")

    # Small human-like pause before clicking login
    time.sleep(random.uniform(0.5, 1.2))

    # ── STEP 4: Click Login ───────────────────────────────────────────────────
    login_btn_selectors = [
        "button[type='submit']",
        "button:has-text('Login')",
        "input[value='Login']",
        "input[type='submit']",
    ]
    login_clicked = False
    for sel in login_btn_selectors:
        try:
            btn = page.locator(sel).first
            btn.wait_for(state="visible", timeout=5000)
            btn.click()
            login_clicked = True
            print(f"✅ Login button clicked via: {sel}")
            break
        except Exception:
            continue

    if not login_clicked:
        raise RuntimeError("❌ Could not find or click the Login button.")

    # ── STEP 5: Wait for successful login ────────────────────────────────────
    page.wait_for_load_state("domcontentloaded", timeout=20000)
    page.wait_for_timeout(3000)   # let session cookie settle
    print(f"✅ Logged in | URL: {page.url}")

    # Sanity-check: if still on login page, login failed
    if "nlogin" in page.url or "login" in page.url:
        page.screenshot(path="error_login_failed.png", full_page=True)
        raise RuntimeError(
            "❌ Login may have failed — still on login page after submit. "
            "Check error_login_failed.png in the Actions artifacts."
        )

    # ── STEP 6: Navigate to profile page ─────────────────────────────────────
    page.goto(
        "https://www.naukri.com/mnjuser/profile",
        wait_until="domcontentloaded",
        timeout=30000,
    )
    page.wait_for_timeout(3000)

    # ── STEP 7: Wait for & click "Update resume" ──────────────────────────────
    update_btn_selectors = [
        "button:has-text('Update resume')",
        "input[value='Update resume']",
        "button:has-text('Update Resume')",
        "span:has-text('Update resume')",
    ]
    update_btn = None
    for sel in update_btn_selectors:
        try:
            loc = page.locator(sel).first
            loc.wait_for(state="visible", timeout=15000)
            update_btn = loc
            print(f"✅ 'Update resume' button found via: {sel}")
            break
        except Exception:
            continue

    if update_btn is None:
        page.screenshot(path="error_update_btn.png", full_page=True)
        raise RuntimeError(
            "❌ Could not find the 'Update resume' button. "
            "Check error_update_btn.png in the Actions artifacts."
        )

    # ── STEP 8: Upload resume via file chooser ────────────────────────────────
    with page.expect_file_chooser() as fc_info:
        update_btn.click()

    file_chooser = fc_info.value
    file_chooser.set_files(RESUME_PATH)
    print(f"📄 Resume file set: {RESUME_PATH}")

    # ── STEP 9: Wait for upload to complete ───────────────────────────────────
    page.wait_for_timeout(8000)

    page.screenshot(path="success.png", full_page=True)
    print("📸 Post-upload screenshot saved: success.png")

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

