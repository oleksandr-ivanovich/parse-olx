import asyncio
import json
import time
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim

# Налаштовуємо геокодер
geolocator = Nominatim(user_agent="my_olx_houses_parser_v1")

def get_coords(address):
    """Отримує координати. Додаємо 'Україна', щоб уникнути пошуку по всьому світу"""
    try:
        location = geolocator.geocode(f"{address}, Україна", timeout=10)
        if location:
            return location.latitude, location.longitude
        return None, None
    except Exception as e:
        print(f"Помилка геокодування для {address}: {e}")
        return None, None

async def parse_olx_houses():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()
        
        # Оновлене посилання на будинки в доларах
        url = "https://www.olx.ua/uk/nedvizhimost/doma/prodazha-domov/?currency=USD"
        print("Завантажую сторінку з будинками...")
        
        await page.goto(url, wait_until="domcontentloaded")
        await page.screenshot(path="debug_screenshot.png")

        try:
            print("Чекаю на відображення оголошень...")
            await page.wait_for_selector('div[data-cy="l-card"]', timeout=15000)
        except Exception as e:
            print("Помилка: Картки не завантажилися. Подивіться на debug_screenshot.png")

        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        listings = soup.select('div[data-cy="l-card"]')

        results = []
        print(f"Знайдено {len(listings)} оголошень. Обробляю...")

        for item in listings[:10]:
            # Розширили пошук заголовка (тепер шукає і h4, який використовується в будинках)
            title_el = item.select_one('h4') or item.select_one('h6') or item.select_one('div[data-cy="ad-title"]')
            price_el = item.select_one('[data-testid="ad-price"]')
            location_el = item.select_one('[data-testid="location-date"]')
            link_el = item.select_one('a')

            if not link_el:
                print("Едж-кейс: пропущено картку без посилання")
                continue

            title = title_el.get_text(strip=True) if title_el else "Без назви"
            # Використовуємо separator, щоб відділити ціну від слова "Договірна"
            price = price_el.get_text(separator=" ", strip=True) if price_el else "Ціна не вказана"
            location_full = location_el.get_text(strip=True) if location_el else "Невідомо"
            
            village = location_full.split(' - ')[0] if ' - ' in location_full else location_full
            
            link = link_el['href']
            if link.startswith('/'):
                link = "https://www.olx.ua" + link

            print(f"Знайдено об'єкт: {title} | {village}")
            print(f"Шукаю координати для: {village}, Україна")
            
            lat, lng = get_coords(village)
            time.sleep(1.1)

            if lat and lng:
                results.append({
                    "title": title,
                    "price": price,
                    "location": village,
                    "lat": lat,
                    "lng": lng,
                    "link": link
                })

        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
            
        print("Готово! Дані збережено у data.json")
        await browser.close()

asyncio.run(parse_olx_houses())
