"""Native editor acceptance, using only the fixed synthetic localhost lab."""

import os
from urllib.parse import urlsplit

from mock_suggestions import PROPOSAL
from playwright.sync_api import expect
from playwright.sync_api import sync_playwright
from smoke import api
from smoke import fixture_document
from smoke import wait_for_api


def main():
    wait_for_api()
    document_id = fixture_document()
    path = f"/api/documents/{document_id}/"
    original = api(path)["title"]
    api(path, {"title": "Upstream fixture"}, method="PATCH")
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE"),
                headless=True,
            )
            context = browser.new_context(viewport={"width": 1440, "height": 1000})

            def local_only(route):
                target = urlsplit(route.request.url)
                if (
                    target.hostname in {"localhost", "127.0.0.1"}
                    and target.port == 18080
                ):
                    route.continue_()
                else:
                    route.abort()

            context.route("**/*", local_only)
            page = context.new_page()
            page.goto("http://localhost:18080/", wait_until="networkidle")
            page.locator('input[name="login"]').fill("reviewer")
            page.locator('input[name="password"]').fill("synthetic-review-only")
            page.get_by_role("button", name="Sign in", exact=True).click()
            page.wait_for_url("**/dashboard**")
            page.goto(f"http://localhost:18080/documents/{document_id}/details")
            title = page.locator('pngx-input-text[formcontrolname="title"]')
            expect(title.locator("input")).to_have_value("Upstream fixture")
            page.get_by_role("button", name="Suggest", exact=True).click()
            title.get_by_text(PROPOSAL["title"], exact=True).click()
            expect(title.locator("input")).to_have_value(PROPOSAL["title"])
            assert api(path)["title"] == "Upstream fixture"
            with page.expect_response(
                lambda response: (
                    response.request.method in {"PATCH", "PUT"}
                    and urlsplit(response.url).path == path
                ),
            ) as saved:
                page.get_by_role("button", name="Save", exact=True).first.click()
            assert saved.value.ok
            assert api(path)["title"] == PROPOSAL["title"]
            page.set_viewport_size({"width": 390, "height": 844})
            expect(title.locator("input")).to_be_visible()
            browser.close()
        print("PASS: native title suggestion selection, explicit Save, mobile editor")  # noqa: T201
    finally:
        api(path, {"title": original}, method="PATCH")


if __name__ == "__main__":
    main()
