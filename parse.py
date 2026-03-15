import asyncio
import json
import time
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim

# Налаштовуємо геокодер
geolocator = Nominatim(user_agent="my_olx_premium_parser_v3")

def get_coords(address):
    """Отримує координати"""
    try:
        location = geolocator.geocode(f"{address}, Україна", timeout=10)
        if location:
            return location.latitude, location.longitude
        return None, None
    except Exception as e:
        print(f"Помилка геокодування для {address}: {e}")
        return None, None

async def parse_olx_filtered():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()
        
        results = []
        current_page = 1
        coords_cache = {}
        
        while True:
            url = f"https://www.olx.ua/uk/nedvizhimost/doma/prodazha-domov/?currency=USD&search%5Bfilter_enum_communications%5D%5B0%5D=sewerage_septic_tank&search%5Bfilter_float_price%3Afrom%5D=5000&search%5Bfilter_float_price%3Ato%5D=14000&search%5Border%5D=created_at%3Adesc&page={current_page}"
            
            print(f"\n--- Завантажую сторінку {current_page} ---")
            await page.goto(url, wait_until="domcontentloaded")
            
            # Даємо 3 секунди на відмальовку або проходження перевірки Cloudflare
            await asyncio.sleep(3)
            
            # Робимо скріншот поточної сторінки для дебагу (якщо впаде - будемо бачити чому)
            await page.screenshot(path="debug_screenshot.png")
            print("Зроблено знімок екрана: debug_screenshot.png")

            try:
                # Шукаємо першу картку оголошення
                await page.wait_for_selector('div[data-cy="l-card"]', timeout=10000)
            except Exception:
                print(f"КРИТИЧНА ПОМИЛКА: Картки не знайдено на сторінці {current_page}.")
                html_content = await page.content()
                print(f"Отриманий HTML (перші 500 символів): {html_content[:500]}")
                break # Виходимо з циклу, якщо карток немає

            # Скролимо сторінку вниз, щоб підвантажити всі 40+ оголошень
            print("Скролю сторінку для підвантаження оголошень...")
            for _ in range(5):
                await page.evaluate("window.scrollBy(0, 1500)")
                await asyncio.sleep(1) # Використовуємо асинхронний sleep для Playwright

            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            listings = soup.select('div[data-cy="l-card"]')

            if not listings:
                print(f"Оголошень на сторінці {current_page} немає. Завершуємо парсинг.")
                break

            print(f"Знайдено {len(listings)} оголошень на сторінці {current_page}. Парсимо...")

            for item in listings:
                title_el = item.select_one('h4') or item.select_one('h6') or item.select_one('div[data-cy="ad-title"]')
                price_el = item.select_one('[data-testid="ad-price"]')
                location_el = item.select_one('[data-testid="location-date"]')
                link_el = item.select_one('a')

                if not link_el:
                    continue

                title = title_el.get_text(strip=True) if title_el else "Без назви"
                price = price_el.get_text(separator=" ", strip=True) if price_el else "Ціна не вказана"
                location_full = location_el.get_text(strip=True) if location_el else "Невідомо"
                
                village = location_full.split(' - ')[0] if ' - ' in location_full else location_full
                
                link = link_el['href']
                if link.startswith('/'):
                    link = "https://www.olx.ua" + link

                # Кешування координат, щоб не блокував Nominatim
                if village in coords_cache:
                    lat, lng = coords_cache[village]
                else:
                    lat, lng = get_coords(village)
                    coords_cache[village] = (lat, lng)
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

            # Перевіряємо, чи є кнопка "Наступна сторінка"
            next_button = soup.select_one('[data-cy="pagination-forward"]')
            if not next_button:
                print(f"Кнопку 'Наступна сторінка' не знайдено. Сторінка {current_page} - остання.")
                break

            current_page += 1

        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
            
        print(f"\nГотово! Всього збережено {len(results)} карток у data.json")
        await browser.close()

asyncio.run(parse_olx_filtered())
