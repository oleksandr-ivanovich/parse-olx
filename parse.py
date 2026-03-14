import asyncio
import json
import time
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim

# Налаштовуємо геокодер (обов'язково змініть user_agent на щось унікальне)
geolocator = Nominatim(user_agent="my_olx_map_parser_v1")

def get_coords(address):
    """Функція для отримання координат за назвою району"""
    try:
        # Додаємо "Київ" для точності
        location = geolocator.geocode(f"Київ, {address}", timeout=10)
        if location:
            return location.latitude, location.longitude
        return None, None
    except Exception as e:
        print(f"Помилка геокодування для {address}: {e}")
        return None, None

async def parse_olx():
    async with async_playwright() as p:
        # Для GitHub Actions обов'язково headless=True (без графічного вікна)
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        url = "https://www.olx.ua/uk/nedvizhimost/kvartiry/dolgosrochnaya-arenda-kvartir/kiev/"
        print("Завантажую сторінку...")
        await page.goto(url, wait_until="networkidle")

        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        listings = soup.select('div[data-cy="l-card"]')

        results = []
        print(f"Знайдено {len(listings)} оголошень. Обробляю...")

        for item in listings[:10]:  # Беремо перші 10 для швидкості/тесту
            title_el = item.select_one('h6')
            price_el = item.select_one('p[data-testid="ad-price"]')
            location_el = item.select_one('p[data-testid="location-date"]')
            link_el = item.select_one('a')

            if not (title_el and price_el and location_el and link_el):
                continue

            title = title_el.get_text(strip=True)
            price = price_el.get_text(strip=True)
            location_full = location_el.get_text(strip=True)
            district = location_full.split(' - ')[0] # Отримуємо "Дарницький" тощо
            link = "https://www.olx.ua" + link_el['href']

            print(f"Шукаю координати для: {district}")
            lat, lng = get_coords(district)
            time.sleep(1.1) # Пауза 1 сек, щоб Nominatim не заблокував

            if lat and lng:
                results.append({
                    "title": title,
                    "price": price,
                    "location": district,
                    "lat": lat,
                    "lng": lng,
                    "link": link
                })

        # Зберігаємо у файл
        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
            
        print("Готово! Дані збережено у data.json")
        await browser.close()

asyncio.run(parse_olx())
