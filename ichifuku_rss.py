import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
import hashlib
import re

URL = "https://www.edu.city.fukuyama.hiroshima.jp/kou-ichifuku/"
OUTPUT = Path(__file__).parent / "ichifuku.xml"

response = requests.get(URL, timeout=30)
response.raise_for_status()
response.encoding = response.apparent_encoding

soup = BeautifulSoup(response.text, "html.parser")

new_items = []
seen = set()

jst = timezone(timedelta(hours=9))

# 現在の年度から年を決める
now = datetime.now(jst)
current_year = now.year

for text_node in soup.find_all(string=re.compile(r"\d+\s*月\s*\d+\s*日")):

    parent = text_node.parent

    if not parent:
        continue

    full_text = parent.get_text(" ", strip=True)

    date_match = re.search(
        r"(\d+)\s*月\s*(\d+)\s*日",
        full_text
    )

    if not date_match:
        continue

    month = int(date_match.group(1))
    day = int(date_match.group(2))

    a = parent.find("a", href=True)

    if not a:
        a = parent.find_next("a", href=True)

    if not a:
        continue

    title = a.get_text(" ", strip=True)

    if not title:
        continue

    # 「学校行事」欄は除外
    if title == "学校行事":
        continue

    article_url = urljoin(URL, a["href"])

    # 年度をまたぐ場合にも対応
    year = current_year

    # 現在が1～3月で、掲載月が4～12月なら前年
    if now.month <= 3 and month >= 4:
        year -= 1

    dt = datetime(
        year,
        month,
        day,
        0,
        0,
        tzinfo=jst
    )

    pub_date = format_datetime(dt)

    # 日付＋タイトル＋URLを固有IDにする
    guid_source = f"{year}-{month:02d}-{day:02d}|{title}|{article_url}"
    guid = hashlib.sha256(
        guid_source.encode("utf-8")
    ).hexdigest()

    if guid in seen:
        continue

    seen.add(guid)

    new_items.append({
        "title": title,
        "link": article_url,
        "description": "福山市立福山中・高等学校 新着情報",
        "date": pub_date,
        "guid": guid
    })

# 以前のRSSを読み込む
old_items = []

if OUTPUT.exists():
    try:
        old_tree = ET.parse(OUTPUT)
        old_root = old_tree.getroot()

        for item in old_root.findall("./channel/item"):
            old_items.append({
                "title": item.findtext("title", ""),
                "link": item.findtext("link", ""),
                "description": item.findtext("description", ""),
                "date": item.findtext("pubDate", ""),
                "guid": item.findtext("guid", "")
            })
    except Exception:
        old_items = []

# 新着＋過去記事を合体して重複除去
all_items = []
seen_guids = set()

for item in new_items + old_items:
    if item["guid"] in seen_guids:
        continue

    seen_guids.add(item["guid"])
    all_items.append(item)

# 最大300件保存
all_items = all_items[:300]

# RSS作成
rss = ET.Element("rss", version="2.0")
channel = ET.SubElement(rss, "channel")

ET.SubElement(channel, "title").text = "福山市立福山中・高等学校 新着情報"
ET.SubElement(channel, "link").text = URL
ET.SubElement(channel, "description").text = "福山市立福山中・高等学校の新着情報"
ET.SubElement(channel, "language").text = "ja"

for item in all_items:
    element = ET.SubElement(channel, "item")

    ET.SubElement(element, "title").text = item["title"]
    ET.SubElement(element, "link").text = item["link"]
    ET.SubElement(element, "description").text = item["description"]
    ET.SubElement(element, "pubDate").text = item["date"]

    guid_element = ET.SubElement(element, "guid")
    guid_element.set("isPermaLink", "false")
    guid_element.text = item["guid"]

tree = ET.ElementTree(rss)
ET.indent(tree, space="  ")

tree.write(
    OUTPUT,
    encoding="utf-8",
    xml_declaration=True
)

print("RSS作成成功")
print("今回取得:", len(new_items), "件")
print("RSS保存件数:", len(all_items), "件")
print("保存先:", OUTPUT)

print()
print("取得記事:")
for item in new_items:
    print(item["date"], item["title"])