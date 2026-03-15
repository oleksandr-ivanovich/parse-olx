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
            
            print(f"--- Завантажую сторінку {current_page} ---")
            await page.goto(url, wait_until="domcontentloaded")

            try:
                await page.wait_for_selector('div[data-cy="l-card"]', timeout=15000)
            except Exception:
                print(f"Картки не знайдено. Завершуємо парсинг.")
                break

            # 1. ФІКС ДЛЯ 40 ОГОЛОШЕНЬ: Імітуємо скрол вниз, щоб підвантажити всі картки
            print("Скролю сторінку для підвантаження всіх карток...")
            for _ in range(4): # 4 рази прокручуємо вниз потроху
                await page.evaluate("window.scrollBy(0, 1000)")
                time.sleep(1) # Даємо час скриптам OLX відмалювати картки

            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            listings = soup.select('div[data-cy="l-card"]')

            print(f"Знайдено {len(listings)} оголошень на сторінці {current_page}. Обробляю...")

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

            # 2. ФІКС ДЛЯ НЕСКІНЧЕННОГО ЦИКЛУ: Шукаємо кнопку "Наступна сторінка"
            next_button = soup.select_one('[data-cy="pagination-forward"]')
            
            # Якщо кнопки "Вперед" немає, значить ми дійшли до останньої сторінки
            if not next_button:
                print(f"Кнопку 'Наступна сторінка' не знайдено. Сторінка {current_page} - остання.")
                break

            current_page += 1

        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
            
        print(f"Готово! Всього збережено {len(results)} карток у data.json")
        await browser.close()
