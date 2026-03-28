"""
Diagnostic: opens the 311 form, navigates step by step, and for each step
prints exactly what the model identifies as mandatory fields — WITHOUT filling anything.
Run: python test_model_fields.py
"""
import asyncio
import logging
from filing.agent import open_311_browser, _model_fill_step, _parse_address

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

mock_payload = {
    "first_name": "John",
    "last_name": "Smith",
    "email": "jsmith@abc.com",
    "phone": "9876543210",
    "form_payload": {
        "complaint_type": "UNSANITARY CONDITION",
        "descriptor": "MOLD",
        "address": "2386 VALENTINE AVENUE, #5A",
        "borough": "BRONX",
        "description": (
            "Tenant reports mold. Building has 26 open Class C and "
            "14 open Class B violations. Oldest open violation is 8493 days old."
        ),
    },
}


async def diagnose():
    from playwright.async_api import async_playwright

    fp = mock_payload["form_payload"]
    street_address, apt_number = _parse_address(fp["address"])
    address = street_address

    print(f"\n{'='*60}")
    print(f"Street address : {street_address}")
    print(f"Apartment #    : {apt_number}")
    print(f"{'='*60}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await (await browser.new_context()).new_page()

        # Navigate to form
        await page.goto("https://portal.311.nyc.gov/article/?kanumber=KA-01074", wait_until="domcontentloaded")
        for btn_text in ["Close", "Accept", "Accept All", "I Agree", "OK"]:
            try:
                btn = page.get_by_role("button", name=btn_text, exact=False)
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    break
            except Exception:
                pass

        await page.evaluate("""
            createServiceRequest(
                'af973791-d174-e811-a83a-000d3a33bdbd',
                'fb2c44e2-4590-e811-a95f-000d3a1c53e4',
                '22b8b85e-4817-f111-8341-000d3a4f630d',
                'be973791-d174-e811-a83a-000d3a33bdbd',
                'HPD',
                '3eb8b85e-4817-f111-8341-000d3a4f630d'
            )
        """)
        await page.wait_for_url("**/sr-step/**", timeout=12000)
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(2)

        print(">>> STEP 1 — model diagnosis (dry run, no fills)")
        await _model_fill_step(page, "Step 1", mock_payload, dry_run=True)

        # Complete address popup manually so we can reach Step 2
        print("\n[Pausing 30s — manually complete the address popup and click Next to reach Step 2]")
        await asyncio.sleep(30)

        print("\n>>> STEP 2 — model diagnosis (dry run, no fills)")
        await _model_fill_step(page, "Step 2", mock_payload, dry_run=True)

        print("\n[Pausing 20s — manually click Next to reach Step 3]")
        await asyncio.sleep(20)

        print("\n>>> STEP 3 (Who) — model diagnosis (dry run, no fills)")
        await _model_fill_step(page, "Step 3 - Who", mock_payload, dry_run=True)

        print("\n[Diagnosis complete — closing in 10s]")
        await asyncio.sleep(10)
        await browser.close()


asyncio.run(diagnose())
