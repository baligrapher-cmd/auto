import asyncio
import os
import json
import sys
import argparse
from playwright.async_api import async_playwright


async def _collect_trees_via_api(context, api_headers_template, all_trees, custom_keyword=None):
    if not api_headers_template:
        print("⚠️ Header API belum tertangkap dari browser, lanjut fallback ke scan UI.")
        return 0

    print("🛰️ Header API browser tertangkap. Menarik data lokasi langsung via request template...")
    direct_hits = 0
    headers = {
        k: v for k, v in api_headers_template.items()
        if not k.startswith(":")
    }

    if custom_keyword:
        print("ℹ️ Mode keyword aktif, tetapi server saat ini terlihat memakai pola bbox. Menjalankan scan area agar data tetap terbarui.")

    grid_boxes = [
        [[94, -12], [102, -4]],
        [[102, -12], [110, -4]],
        [[110, -12], [118, -4]],
        [[118, -12], [126, -4]],
        [[94, -4], [102, 4]],
        [[102, -4], [110, 4]],
        [[110, -4], [118, 4]],
        [[118, -4], [126, 4]],
        [[94, 4], [102, 8]],
        [[102, 4], [110, 8]],
        [[110, 4], [118, 8]],
        [[118, 4], [126, 8]],
    ]

    async def scan_bbox(bbox, depth=0):
        nonlocal direct_hits
        try:
            zoom_level = 10 + depth
            bbox_url = f"https://api.fotoyu.com/tree/v2/trees?bbox={json.dumps(bbox)}&zoom_level={zoom_level}"
            response = await context.request.get(bbox_url, headers=headers)
            if not response.ok:
                print(f"   ⚠️ API bbox gagal {bbox}: {response.status}")
                return

            data = await response.json()
            results = data.get("result", []) if isinstance(data, dict) else []
            for tree in results:
                tree_id = tree.get("id")
                name = str(tree.get("name", "")).strip()
                if tree_id and name:
                    if tree_id not in all_trees:
                        direct_hits += 1
                    all_trees[tree_id] = tree

            print(f"   API bbox depth={depth} {bbox}: {len(results)} hasil, total {len(all_trees)}")

            # Jika area terlalu padat, pecah jadi 4 kotak lebih kecil agar event padat tidak hilang.
            # Kedalaman lebih besar dibutuhkan untuk area sangat ramai seperti Jawa/Solo/Jogja.
            if len(results) >= 100 and depth < 5:
                (min_lon, min_lat), (max_lon, max_lat) = bbox
                mid_lon = (min_lon + max_lon) / 2
                mid_lat = (min_lat + max_lat) / 2
                sub_boxes = [
                    [[min_lon, min_lat], [mid_lon, mid_lat]],
                    [[mid_lon, min_lat], [max_lon, mid_lat]],
                    [[min_lon, mid_lat], [mid_lon, max_lat]],
                    [[mid_lon, mid_lat], [max_lon, max_lat]],
                ]
                for sub_bbox in sub_boxes:
                    await scan_bbox(sub_bbox, depth + 1)
        except Exception as bbox_err:
            print(f"   ⚠️ API bbox gagal {bbox}: {bbox_err}")

    for bbox in grid_boxes:
        await scan_bbox(bbox, 0)

    return direct_hits


async def _search_trees_by_keyword(context, api_headers_template, keyword):
    if not api_headers_template or not keyword:
        return []

    headers = {
        k: v for k, v in api_headers_template.items()
        if not k.startswith(":")
    }
    
    results = []
    # Coba beberapa endpoint search yang mungkin ada (v2 dan v3)
    endpoints = [
        f"https://api.fotoyu.com/tree/v2/trees/search?q={keyword}&limit=500",
        f"https://api.fotoyu.com/tree/v3/trees/search?q={keyword}&limit=500",
        f"https://api.fotoyu.com/tree/v2/trees?q={keyword}&limit=500"
    ]
    
    for url in endpoints:
        try:
            response = await context.request.get(url, headers=headers)
            if response.ok:
                data = await response.json()
                items = data.get("result", []) if isinstance(data, dict) else []
                if isinstance(items, list):
                    results.extend(items)
                    print(f"🎯 API '{url}' menemukan {len(items)} hasil.")
        except Exception as e:
            print(f"⚠️ Gagal akses {url}: {e}")
            
    return results


async def _extract_ui_search_results(page, limit=50):
    try:
        script = f"""() => {{
            const limit = {int(limit)};
            const seen = new Set();
            const results = [];

            // Cari semua elemen yang mengandung teks dan kemungkinan besar adalah item list
            const elements = document.querySelectorAll("div, a, button, li, [role='option']");
            
            for (const el of elements) {{
                // Kriteria item FotoTree: punya teks, tidak terlalu panjang, dan biasanya punya struktur nama & lokasi
                const text = el.innerText || "";
                if (!text || text.length > 200 || text.length < 3) continue;
                
                // Lewati elemen navigasi umum
                if (["Peta", "Map", "Upload", "Masuk", "Login", "Home"].includes(text.trim())) continue;

                const lines = text.split("\\n").map(s => s.trim()).filter(Boolean);
                if (lines.length >= 1) {{
                    const name = lines[0];
                    const subtitle = lines.length > 1 ? lines.slice(1).join(" | ") : "";
                    const key = name.toLowerCase() + "|" + subtitle.toLowerCase();
                    
                    if (!seen.has(key)) {{
                        // Cek apakah elemen ini terlihat di layar (ukuran minimal)
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 50 && rect.height > 10) {{
                            seen.add(key);
                            results.push({{ name, subtitle }});
                        }}
                    }}
                }}

                if (results.length >= limit) break;
            }}

            return results;
        }}"""
        results = await page.evaluate(script)
        return results if isinstance(results, list) else []
    except Exception as ui_err:
        print(f"⚠️ UI search extraction error: {ui_err}")
        return []


async def search_fototrees_live(user_data_dir, keyword, limit=100):
    keyword = (keyword or "").strip()
    if not user_data_dir or not os.path.exists(user_data_dir):
        return {"success": False, "results": [], "message": "Profile akun tidak ditemukan."}
    if not keyword:
        return {"success": False, "results": [], "message": "Keyword pencarian kosong."}

    try:
        async with async_playwright() as p:
            try:
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-extensions",
                        "--mute-audio",
                        "--disable-http-cache"
                    ]
                )
            except Exception as e:
                error_msg = str(e)
                if "user data directory is already in use" in error_msg.lower():
                    return {
                        "success": False,
                        "results": [],
                        "message": "Profile akun sedang dipakai browser lain. Tutup browser AutoYu dulu."
                    }
                return {"success": False, "results": [], "message": error_msg}

            page = await context.new_page()
            api_headers_template = {}
            captured_from_network = [] # List untuk menampung data mentah dari network

            async def handle_response(response):
                nonlocal api_headers_template, captured_from_network
                try:
                    url = response.url.lower()
                    # Tangkap header untuk manual API call nanti
                    if response.status == 200 and "/tree/v2/trees" in url and not api_headers_template:
                        api_headers_template = await response.request.all_headers()
                    
                    # Tangkap DATA MENTAH dari setiap response JSON yang lewat
                    if response.status == 200 and ("application/json" in response.headers.get("content-type", "")):
                        try:
                            data = await response.json()
                            # Cari objek yang punya pola FotoTree (id dan name)
                            def find_trees(obj):
                                found = []
                                if isinstance(obj, list):
                                    for item in obj:
                                        found.extend(find_trees(item))
                                elif isinstance(obj, dict):
                                    if "id" in obj and "name" in obj:
                                        found.append(obj)
                                    for v in obj.values():
                                        if isinstance(v, (dict, list)):
                                            found.extend(find_trees(v))
                                return found
                            
                            trees = find_trees(data)
                            if trees:
                                captured_from_network.extend(trees)
                        except:
                            pass
                except Exception:
                    pass

            page.on("response", handle_response)

            try:
                await page.goto("https://www.fotoyu.com/tree", wait_until="domcontentloaded", timeout=60000)
                
                # Persistence Loop: Coba beberapa kali sampai data API tertangkap atau timeout
                normalized = []
                seen = set()
                
                for attempt in range(3):
                    print(f"🔍 Attempt {attempt+1} to sync live data for: {keyword}")
                    
                    # 1. Masukkan data yang tertangkap otomatis dari network
                    for tree in captured_from_network:
                        name = str(tree.get("name", "")).strip()
                        if not name: continue
                        key = name.lower()
                        if key in seen: continue
                        seen.add(key)
                        loc = tree.get("location") or {}
                        normalized.append({
                            "name": name,
                            "subtitle": str(loc.get("name") or "").strip(),
                            "id": tree.get("id")
                        })

                    # 2. Coba via API Manual (Jika header sudah tertangkap)
                    structured_results = await _search_trees_by_keyword(context, api_headers_template, keyword)
                    if structured_results:
                        for tree in structured_results:
                            name = str(tree.get("name", "")).strip()
                            if not name: continue
                            key = name.lower()
                            if key in seen: continue
                            seen.add(key)
                            loc = tree.get("location") or {}
                            normalized.append({
                                "name": name,
                                "subtitle": str(loc.get("name") or "").strip(),
                                "id": tree.get("id")
                            })
                    
                    # 3. Coba interaksi UI jika belum cukup hasil
                    if len(normalized) < limit:
                        input_selectors = [
                            page.get_by_placeholder("Ketik nama FotoTree"),
                            page.locator("input[placeholder*='FotoTree']"),
                            page.locator("input[placeholder*='Cari']"),
                            page.locator("input[type='text']").first
                        ]
                        for search_input in input_selectors:
                            try:
                                if await search_input.is_visible(timeout=2000):
                                    await search_input.fill("")
                                    await asyncio.sleep(0.3)
                                    await search_input.type(keyword, delay=100) # Lebih lambat agar web sempat merespon
                                    await page.keyboard.press("Enter")
                                    await asyncio.sleep(4) # Tunggu hasil muncul lebih lama
                                    break
                            except:
                                continue

                        ui_results = await _extract_ui_search_results(page, limit=limit)
                        for item in ui_results:
                            name = str(item.get("name", "")).strip()
                            if not name: continue
                            # Cek keyword di dalam nama/subtitle untuk akurasi UI scraping
                            if keyword.lower() not in name.lower() and keyword.lower() not in str(item.get("subtitle", "")).lower():
                                continue
                            key = name.lower()
                            if key in seen: continue
                            seen.add(key)
                            normalized.append({
                                "name": name,
                                "subtitle": str(item.get("subtitle", "")).strip(),
                                "id": None
                            })
                    
                    if len(normalized) >= limit:
                        break
                    
                    # Jika belum ada hasil, tunggu sebentar dan coba lagi
                    await asyncio.sleep(2)

                await context.close()

                if normalized:
                    # Sort agar yang mengandung keyword di awal nama muncul paling atas
                    def sort_key(x):
                        n = x['name'].lower()
                        if n.startswith(keyword.lower()): return 0
                        if keyword.lower() in n: return 1
                        return 2
                    
                    normalized.sort(key=sort_key)
                    
                    return {
                        "success": True,
                        "results": normalized[:limit * 2], # Berikan lebih banyak hasil ke UI
                        "message": f"{len(normalized)} hasil ditemukan langsung dari server FotoYu."
                    }
                return {"success": False, "results": [], "message": "Tidak ada hasil untuk keyword ini di server FotoYu."}
            except Exception as live_err:
                try:
                    await context.close()
                except Exception:
                    pass
                return {"success": False, "results": [], "message": str(live_err)}
    except Exception as outer_err:
        return {"success": False, "results": [], "message": str(outer_err)}

async def sync_fototrees(user_data_dir=None, custom_keyword=None):
    # Detect Application Data Directory (Safe for Installation)
    if sys.platform == 'darwin':
        base_app_data = os.path.expanduser("~/Library/Application Support/AutoYuPro")
    else:
        base_app_data = os.path.join(os.getenv("APPDATA") or os.path.expanduser("~"), "AutoYuPro")
    
    # Ensure app data directory exists
    if not os.path.exists(base_app_data):
        os.makedirs(base_app_data, exist_ok=True)

    # Detect default profile path if not provided
    if not user_data_dir:
        base_accounts = os.path.join(base_app_data, "accounts")
        # Try to find the first available profile
        if os.path.exists(base_accounts):
            accounts = [d for d in os.listdir(base_accounts) if os.path.isdir(os.path.join(base_accounts, d))]
            if accounts:
                user_data_dir = os.path.join(base_accounts, accounts[0], "profile")
    
    if not user_data_dir or not os.path.exists(user_data_dir):
        print(f"❌ Error: Profile path not found: {user_data_dir}")
        return

    # Path output (Stored in AppData/Application Support for safety)
    json_output = os.path.join(base_app_data, "full_fototree_list.json")
    db_json_output = os.path.join(base_app_data, "autoyu_tree_location_db.json")
    db_txt_output = os.path.join(base_app_data, "autoyu_tree_location_db.txt")

    # PENGHAPUSAN DATABASE LOKAL - Sesuai permintaan user untuk 100% Real-time
    all_trees = {}
    print("ℹ️ Mode Murni Server Aktif: Mengabaikan database lokal dan menarik data segar dari FotoYu.")

    keyword_match_count = 0

    async with async_playwright() as p:
        print(f"🚀 Memulai sinkronisasi FotoTree menggunakan profile: {user_data_dir}")
        
        # Launch persistent context
        try:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=True,
                args=[
                    "--no-sandbox", 
                    "--disable-setuid-sandbox",
                    "--disable-extensions",
                    "--mute-audio",
                    "--disable-http-cache" # Paksa ambil data baru
                ]
            )
        except Exception as e:
            error_msg = str(e)
            if "user data directory is already in use" in error_msg.lower():
                print("❌ GAGAL: Browser AutoYu sedang terbuka. Tutup dulu browser otomasi sebelum SYNC WEB.")
            else:
                print(f"❌ Gagal membuka browser: {error_msg}")
            return

        page = await context.new_page()
        
        api_headers_template = {}

        async def handle_response(response):
            nonlocal api_headers_template
            url = response.url.lower()
            # Tangkap semua respon JSON yang mengandung data lokasi (Pola API lebih luas)
            patterns = ["/tree", "/search", "/creations", "/trees", "/v2/trees", "/v3/trees", "/gs/v2"]
            if any(p in url for p in patterns) and response.status == 200:
                try:
                    if "/tree/v2/trees?bbox=" in url and not api_headers_template:
                        api_headers_template = await response.request.all_headers()
                    data = await response.json()
                    
                    # Fungsi rekursif untuk mencari objek yang punya 'id' dan 'name'
                    def find_trees(obj):
                        found = []
                        if isinstance(obj, list):
                            for item in obj:
                                if isinstance(item, dict) and "id" in item and "name" in item:
                                    found.append(item)
                                else:
                                    found.extend(find_trees(item))
                        elif isinstance(obj, dict):
                            # Deteksi struktur FotoTree (biasanya ada id, name, dan location)
                            if "id" in obj and "name" in obj:
                                found.append(obj)
                            # Cek nested objects
                            for v in obj.values():
                                if isinstance(v, (list, dict)):
                                    found.extend(find_trees(v))
                        return found

                    results = find_trees(data)
                    if results:
                        for t in results:
                            tree_id = t.get("id")
                            name = t.get("name", "").strip()
                            if tree_id and name:
                                # Selalu simpan yang terbaru jika dalam sesi sinkronisasi aktif
                                all_trees[tree_id] = t
                except: pass

        page.on("response", handle_response)

        print("🌐 Membuka FotoTree & Menunggu Sesi...")
        try:
            # Step 1: Buka halaman Tree
            await page.goto("https://www.fotoyu.com/tree", wait_until="networkidle", timeout=60000)
            await asyncio.sleep(3)

            if custom_keyword:
                keyword_results = await _search_trees_by_keyword(context, api_headers_template, custom_keyword)
                for tree in keyword_results:
                    tree_id = tree.get("id")
                    name = str(tree.get("name", "")).strip()
                    if tree_id and name:
                        all_trees[tree_id] = tree

            direct_hits = await _collect_trees_via_api(context, api_headers_template, all_trees, custom_keyword)
            if direct_hits:
                print(f"✨ API langsung menambahkan {direct_hits} lokasi baru/lebih segar.")
            
            # Step 2: Buka halaman Upload (Seringkali API di sini lebih fresh/update)
            print("🔍 Memeriksa jalur Upload untuk data real-time...")
            await page.goto("https://www.fotoyu.com/upload", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            # Kembali ke Tree untuk scanning jika diperlukan
            await page.goto("https://www.fotoyu.com/tree", wait_until="domcontentloaded")
            await asyncio.sleep(2)
            
            # Pencarian Agresif & Mandiri (Power Scan)
            print("🔍 Menjalankan Pengujian Mandiri & Pencarian Mendalam...")
            search_input = page.get_by_placeholder("Ketik nama FotoTree")
            if await search_input.count() > 0:
                if custom_keyword:
                    keywords = [custom_keyword]
                    print(f"🎯 Mencari keyword spesifik: '{custom_keyword}'")
                else:
                    # Keyword default yang lebih luas
                    keywords = ["2026", "2025", "2024", "Marathon", "Run", "Bali", "Jakarta", "Bandung", "Jogja", "Fun", "Race"]
                
                for kw in keywords:
                    print(f"   > Mencari secara mendalam: '{kw}'...")
                    await search_input.fill("")
                    await asyncio.sleep(0.2)
                    await search_input.fill(kw)
                    await asyncio.sleep(5) # Waktu tunggu agar API merespon
                    
                    # SCROLL PANEL KIRI (FotoTree List)
                    for i in range(15):
                        # FotoYu panel list biasanya di sebelah kiri
                        await page.mouse.move(250, 400)
                        await page.mouse.wheel(0, 5000)
                        await asyncio.sleep(0.6)
                        if i % 4 == 0:
                            await page.mouse.wheel(0, -1000)
                            await asyncio.sleep(0.2)
                            await page.mouse.wheel(0, 1000)
                    
                    print(f"   📊 Progres: {len(all_trees)} lokasi terkumpul.")
                
                await search_input.fill("") 
            else:
                print("ℹ️ Input pencarian UI tidak tersedia di sesi ini. Menggunakan data API langsung.")
        except Exception as e:
            print(f"⚠️ Warning during sync: {e}")

        await context.close()
        
        if not all_trees:
            print("❌ Sinkronisasi Gagal: Tidak ada data ditemukan.")
            return {"success": False, "message": "Tidak ada data ditemukan", "count": 0}

        # SIMPAN KE DUA LOKASI (AppData & Project Folder)
        try:
            sorted_trees = sorted(list(all_trees.values()), key=lambda x: str(x.get("name", "")).lower())

            if custom_keyword:
                keyword_lower = custom_keyword.lower()
                keyword_match_count = sum(
                    1 for item in sorted_trees
                    if keyword_lower in str(item.get("name", "")).lower()
                )
                print(f"🔎 Kecocokan keyword '{custom_keyword}': {keyword_match_count} event.")
            
            # List path yang akan diupdate
            target_files = [
                json_output, # AppData
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "full_fototree_list.json") # Project
            ]
            
            for fpath in target_files:
                with open(fpath, "w", encoding="utf-8") as f:
                    json.dump(sorted_trees, f, indent=4)
                
            db_entries = []
            for t in sorted_trees:
                loc = t.get("location", {})
                db_entries.append({
                    "name": t.get("name"),
                    "id": t.get("id"),
                    "location_name": loc.get("name", ""),
                    "latitude": loc.get("latitude"),
                    "longitude": loc.get("longitude")
                })
            
            # Update DB JSON di dua lokasi
            db_json_targets = [
                db_json_output, # AppData
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "autoyu_tree_location_db.json") # Project
            ]
            for fpath in db_json_targets:
                with open(fpath, "w", encoding="utf-8") as f:
                    json.dump(db_entries, f, indent=4)
                
            # Update TXT DB di dua lokasi
            db_txt_targets = [
                db_txt_output, # AppData
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "autoyu_tree_location_db.txt") # Project
            ]
            for fpath in db_txt_targets:
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(f"{'FOTOTREE NAME':<50} | {'LATITUDE':<12} | {'LONGITUDE':<12} | {'LOCATION NAME'}\n")
                    f.write("-" * 120 + "\n")
                    for m in db_entries:
                        f.write(f"{m['name'][:50]:<50} | {str(m['latitude']):<12} | {str(m['longitude']):<12} | {m['location_name']}\n")

            print(f"\n✅ SUKSES! Total {len(sorted_trees)} lokasi telah disinkronkan ke sistem dan database lokal.")
            return {
                "success": True,
                "message": (
                    f"Sinkronisasi berhasil. Keyword '{custom_keyword}' menemukan {keyword_match_count} event"
                    if custom_keyword else
                    "Sinkronisasi berhasil"
                ),
                "count": len(sorted_trees),
            }
        except Exception as e:
            print(f"❌ Gagal menyimpan data: {e}")
            return {"success": False, "message": str(e), "count": 0}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", help="Path to Chrome user data directory")
    parser.add_argument("--keyword", help="Custom keyword to search")
    args = parser.parse_args()
    
    asyncio.run(sync_fototrees(args.profile, args.keyword))
