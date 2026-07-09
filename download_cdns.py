import urllib.request
import os

js_dir = r"c:\Users\Lenovo\.gemini\antigravity-ide\scratch\echo\apps\core\static\core\js"

files = {
    "tailwind.min.js": "https://cdn.tailwindcss.com",
    "htmx.min.js": "https://unpkg.com/htmx.org@1.9.12/dist/htmx.min.js",
    "alpine.min.js": "https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"
}

opener = urllib.request.build_opener()
opener.addheaders = [('User-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')]
urllib.request.install_opener(opener)

for filename, url in files.items():
    filepath = os.path.join(js_dir, filename)
    print(f"Downloading {url} to {filepath}...")
    try:
        urllib.request.urlretrieve(url, filepath)
        print("Done.")
    except Exception as e:
        print(f"Failed to download {filename}: {e}")
