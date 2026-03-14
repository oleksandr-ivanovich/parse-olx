import asyncio
import json
import time
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim

# Налаштовуємо геокодер
geolocator = Nominatim(user_agent="my_olx_map_parser_v2")

def get_coords(address):
    """Отримує координати за назвою району"""
    try:
        location = geolocator.geocode(f"Київ, {address}", timeout=10)
        if location:
            return location.latitude, location.longitude
        return None, None
    except Exception as e:
        print(f"Помилка геокодування для {address}: {e}")
        return None, None

async def parse_olx():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # 1. Маскуємо бота під звичайний браузер Chrome на Windows
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()
        
        url = "https://www.olx.ua/uk/nedvizhimost/kvartiry/dolgosrochnaya-arenda-kvartir/kiev/"
        print("Завантажую сторінку...")
        
        # Переходимо на сайт
        await page.goto(url, wait_until="domcontentloaded")
        
        # 2. РОБИМО СКРІНШОТ для діагностики відразу після завантаження
        await page.screenshot(path="debug_screenshot.png")
        print("Скріншот екрану бота збережено як debug_screenshot.png")

        # 3. Чекаємо, поки з'являться картки (максимум 15 секунд)
        try:
            print("Чекаю на відображення оголошень...")
            await page.wait_for_selector('div[data-cy="l-card"]', timeout=15000)
        except Exception as e:
            print("Помилка: Картки не завантажилися. Подивіться на debug_screenshot.png!")

        # 4. Парсимо HTML
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        listings = soup.select('div[data-cy="l-card"]')

        results = []
        print(f"Знайдено {len(listings)} оголошень. Обробляю...")

        for item in listings[:10]: # Обробляємо перші 10 оголошень
            title_el = item.select_one('h6')
            price_el = item.select_one('p[data-testid="ad-price"]')
            location_el = item.select_one('p[data-testid="location-date"]')
            link_el = item.select_one('a')

            if not (title_el and price_el and location_el and link_el):
                continue

            title = title_el.get_text(strip=True)
            price = price_el.get_text(strip=True)
            location_full = location_el.get_text(strip=True)
            district = location_full.split(' - ')[0]
            link = "https://www.olx.ua" + link_el['href']

            print(f"Шукаю координати для: {district}")
            lat, lng = get_coords(district)
            time.sleep(1.1) # Пауза для геокодера

            if lat and lng:
                results.append({
                    "title": title,
                    "price": price,
                    "location": district,
                    "lat": lat,
                    "lng": lng,
                    "link": link
                })

        # Зберігаємо результат
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
            
        print("Готово! Дані збережено у data.json")
        await browser.close()

asyncio.run(parse_olx())
