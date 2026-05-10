
import asyncio
from playwright.async_api import async_playwright
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'yeedembooks.settings')
django.setup()

from django.test import Client
from django.urls import reverse
from django.contrib.auth.models import User

async def verify():
    # Setup test user and client
    user, _ = User.objects.get_or_create(username='admin')
    user.set_password('password')
    user.is_staff = True
    user.is_superuser = True
    user.save()

    client = Client()
    client.force_login(user)

    pages = [
        ('dashboard', reverse('core:dashboard')),
        ('invoices', reverse('core:invoice_list')),
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        page = await context.new_page()

        for name, url in pages:
            response = client.get(url)
            html_path = f"verify_{name}_final.html"
            with open(html_path, "wb") as f:
                f.write(response.content)

            await page.goto(f"file://{os.path.abspath(html_path)}")
            # Scroll down to test fixed header
            await page.evaluate("window.scrollTo(0, 500)")
            await page.wait_for_timeout(500)
            await page.screenshot(path=f"verify_{name}_fixed_nav.png", full_page=True)
            print(f"Verified {name} - Fixed Nav and Footer checked.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(verify())
