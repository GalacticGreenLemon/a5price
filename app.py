import csv
import io
import json
import os
import re
import zipfile

import streamlit as st
from streamlit_local_storage import LocalStorage
from PIL import Image, ImageDraw, ImageFont
import barcode
from barcode.writer import ImageWriter

# ---------------------------------------------------------------------------
# Font paths — these two .ttf files must sit next to this app.py in the repo
# ---------------------------------------------------------------------------
FONT_REGULAR = "Roboto-Regular.ttf"
FONT_BOLD = "Roboto-Bold.ttf"

# ---------------------------------------------------------------------------
# Persistence for the manual product list — stored in the *browser's* local
# storage (not on the server), so a page refresh brings your list back, but
# it's private to your own browser/PC. A colleague working from another PC
# has their own separate local storage, so you two never overwrite each
# other's in-progress list.
# ---------------------------------------------------------------------------
localS = LocalStorage()
LS_KEY = "manual_products_cache"


def load_cached_products():
    raw = localS.getItem(LS_KEY, key="get_manual_products_cache")
    # The browser component needs a round trip to resolve; if it hasn't
    # come back yet, rerun once so we don't miss data that's actually there.
    if raw is None and not st.session_state.get("_ls_checked"):
        st.session_state["_ls_checked"] = True
        st.rerun()
    try:
        return json.loads(raw) if raw else []
    except (json.JSONDecodeError, TypeError):
        return []


def save_cached_products(products):
    localS.setItem(
        LS_KEY, json.dumps(products, ensure_ascii=False), key="set_manual_products_cache"
    )


def get_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except IOError:
        return ImageFont.load_default()


def create_barcode(number):
    ean = barcode.get('ean13', number, writer=ImageWriter())
    fp = io.BytesIO()
    ean.write(fp, options={"write_text": False, "module_height": 10.0, "quiet_zone": 2.0})
    fp.seek(0)
    return Image.open(fp)


def draw_wrapped_text(draw, text, font, max_width, x_center, start_y):
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        current_line.append(word)
        line_w = draw.textlength(" ".join(current_line), font=font)
        if line_w > max_width:
            if len(current_line) == 1:
                lines.append(current_line[0])
                current_line = []
            else:
                current_line.pop()
                lines.append(" ".join(current_line))
                current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))

    y = start_y
    line_spacing = font.size * 1.2
    for line in lines:
        w = draw.textlength(line, font=font)
        draw.text((x_center - w / 2, y), line, fill=(0, 0, 0), font=font)
        y += line_spacing
    return y


def draw_label(draw, img, data, offset_x):
    RED = (227, 24, 45)
    BLACK = (0, 0, 0)
    WHITE = (255, 255, 255)

    draw.rectangle([offset_x, 0, offset_x + 800, 400], fill=RED)

    font_pct = get_font(FONT_BOLD, 260)
    percentage_text = f"-{data['Percentage']}%"
    text_bbox = draw.textbbox((0, 0), percentage_text, font=font_pct)
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]
    draw.text((offset_x + 400 - text_w / 2, 200 - text_h / 2 - 50), percentage_text, fill=WHITE, font=font_pct)

    font_title = get_font(FONT_BOLD, 50)
    full_text = data['Name']
    title_y_start = 420
    draw_wrapped_text(draw, full_text, font_title, max_width=750, x_center=offset_x + 400, start_y=title_y_start)

    font_old = get_font(FONT_BOLD, 55)
    font_small = get_font(FONT_BOLD, 35)
    font_new = get_font(FONT_BOLD, 170)
    font_new_unit = get_font(FONT_BOLD, 45)
    font_box = get_font(FONT_BOLD, 45)
    font_box_unit = get_font(FONT_BOLD, 35)

    has_m2 = bool(data.get('OldPrice_m2', '').strip())

    if not has_m2:
        old_price_text = data.get('OldPrice_piece', '')
        old_unit = " lei/buc"

        old_w = draw.textlength(old_price_text, font=font_old)
        start_x = offset_x + 750 - (old_w + draw.textlength(old_unit, font=font_small))
        draw.text((start_x, 590), old_price_text, fill=BLACK, font=font_old)
        draw.text((start_x + old_w, 610), old_unit, fill=BLACK, font=font_small)
        draw.line([start_x - 10, 635, start_x + old_w + 10, 595], fill=BLACK, width=6)

        new_price_text = data.get('NewPrice_piece', '')
        new_unit = " lei/buc"
        new_w = draw.textlength(new_price_text, font=font_new)
        start_x_new = offset_x + 750 - (new_w + draw.textlength(new_unit, font=font_new_unit))
        draw.text((start_x_new, 650), new_price_text, fill=BLACK, font=font_new)
        draw.text((start_x_new + new_w, 750), new_unit, fill=BLACK, font=font_new_unit)

    else:
        old_price_text = data['OldPrice_m2']
        old_unit = " lei/m2"
        old_w = draw.textlength(old_price_text, font=font_old)
        start_x = offset_x + 750 - (old_w + draw.textlength(old_unit, font=font_small))
        draw.text((start_x, 590), old_price_text, fill=BLACK, font=font_old)
        draw.text((start_x + old_w, 610), old_unit, fill=BLACK, font=font_small)
        draw.line([start_x - 10, 635, start_x + old_w + 10, 595], fill=BLACK, width=6)

        new_price_text = data.get('NewPrice_m2', '')
        new_unit = " lei/m2"
        new_w = draw.textlength(new_price_text, font=font_new)
        start_x_new = offset_x + 750 - (new_w + draw.textlength(new_unit, font=font_new_unit))
        draw.text((start_x_new, 650), new_price_text, fill=BLACK, font=font_new)
        draw.text((start_x_new + new_w, 750), new_unit, fill=BLACK, font=font_new_unit)

        box_price_text = data.get('NewPrice_piece', '')
        if box_price_text:
            box_unit = " lei/cutie"
            box_w = draw.textlength(box_price_text, font=font_box)
            start_x_box = offset_x + 750 - (box_w + draw.textlength(box_unit, font=font_box_unit))
            draw.text((start_x_box, 830), box_price_text, fill=BLACK, font=font_box)
            draw.text((start_x_box + box_w, 840), box_unit, fill=BLACK, font=font_box_unit)

    bc_img = create_barcode(data['BarcodeNum'])
    bc_img = bc_img.resize((300, 100))
    img.paste(bc_img, (int(offset_x + 50), 900))

    font_code = get_font(FONT_REGULAR, 22)
    text_bbox = draw.textbbox((0, 0), data['BarcodeNum'], font=font_code)
    text_w = text_bbox[2] - text_bbox[0]
    draw.text((offset_x + 50 + 150 - text_w / 2, 1000), data['BarcodeNum'], fill=BLACK, font=font_code)

    font_prod = get_font(FONT_BOLD, 27)
    text_bbox = draw.textbbox((0, 0), data['ProductCode'], font=font_prod)
    text_w = text_bbox[2] - text_bbox[0]
    draw.text((offset_x + 50 + 150 - text_w / 2, 1030), data['ProductCode'], fill=BLACK, font=font_prod)

    font_status = get_font(FONT_REGULAR, 35)
    text_bbox = draw.textbbox((0, 0), data['StatusText'], font=font_status)
    text_w = text_bbox[2] - text_bbox[0]
    draw.text((offset_x + 750 - text_w, 1000), data['StatusText'], fill=BLACK, font=font_status)


def generate_zip(data_rows):
    """Builds all label images in memory and returns zip bytes + count."""
    zip_buffer = io.BytesIO()
    count = 0
    with zipfile.ZipFile(zip_buffer, "w") as zipf:
        for i in range(0, len(data_rows), 2):
            img = Image.new('RGB', (1600, 1100), color=(255, 255, 255))
            draw = ImageDraw.Draw(img)
            draw_label(draw, img, data_rows[i], 0)

            output_filename = data_rows[i]['BarcodeNum'][-4:]

            if i + 1 < len(data_rows):
                draw_label(draw, img, data_rows[i + 1], 800)
                draw.line([800, 0, 800, 1100], fill=(200, 200, 200), width=2)
                output_filename += f"-{data_rows[i + 1]['BarcodeNum'][-4:]}"

            output_filename += ".png"

            img_buffer = io.BytesIO()
            img.save(img_buffer, format="PNG")
            zipf.writestr(output_filename, img_buffer.getvalue())
            count += 1

    zip_buffer.seek(0)
    return zip_buffer, count


# A4 landscape at 300 DPI. The label is drawn upright (as normal), then rotated
# 90° so the red banner ends up on the left edge and all text reads bottom-to-top —
# matching a shelf-strip style tag meant to be read with the page turned sideways.
# (A5 isn't a separate format here: the normal 2-up layout already IS A5-sized once
# an A4 sheet is cut in half down the middle — that's the whole reason it's 2-per-page.)
PAGE_SIZES_PX = {
    "a4": (3508, 2481),
}
PAGE_MARGIN_PX = 100

try:
    RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:  # older Pillow versions
    RESAMPLE = Image.LANCZOS


def render_single_page(row, fmt):
    """Draws one product's label, rotates it 90°, and centers it on an A4 landscape page."""
    label_img = Image.new('RGB', (800, 1100), color=(255, 255, 255))
    draw = ImageDraw.Draw(label_img)
    draw_label(draw, label_img, row, 0)

    rotated = label_img.rotate(90, expand=True)

    page_w, page_h = PAGE_SIZES_PX[fmt]
    max_w = page_w - 2 * PAGE_MARGIN_PX
    max_h = page_h - 2 * PAGE_MARGIN_PX
    scale = min(max_w / rotated.width, max_h / rotated.height)
    new_size = (int(rotated.width * scale), int(rotated.height * scale))
    resized = rotated.resize(new_size, RESAMPLE)

    page = Image.new('RGB', (page_w, page_h), color=(255, 255, 255))
    paste_x = (page_w - new_size[0]) // 2
    paste_y = (page_h - new_size[1]) // 2
    page.paste(resized, (paste_x, paste_y))
    return page


def get_row_format(row):
    """Reads the optional 'Format' column: 'a4' means one rotated page for that row;
    anything else (blank, 'normal', missing column entirely) means the normal 2-up layout."""
    fmt = (row.get("Format") or "").strip().lower()
    if fmt == "a4":
        return fmt
    return "normal"


def generate_zip_from_csv(data_rows):
    """
    Builds the output zip respecting each row's own 'Format' column, so a single CSV
    can mix normal 2-up labels with A4 single-page labels in the same file.
    """
    zip_buffer = io.BytesIO()
    count = 0
    used_names = {}

    def _unique_name(base_name):
        """Appends -2, -3, ... if base_name was already used, so duplicate labels
        (e.g. from a Quantity > 1) don't overwrite each other inside the zip."""
        if base_name not in used_names:
            used_names[base_name] = 1
            return base_name
        used_names[base_name] += 1
        stem, ext = os.path.splitext(base_name)
        return f"{stem}-{used_names[base_name]}{ext}"

    with zipfile.ZipFile(zip_buffer, "w") as zipf:
        i = 0
        n = len(data_rows)
        while i < n:
            row = data_rows[i]
            fmt = get_row_format(row)

            if fmt == "a4":
                page = render_single_page(row, fmt)
                output_filename = _unique_name(f"{row['BarcodeNum'][-4:]}_{fmt.upper()}.png")
                buf = io.BytesIO()
                page.save(buf, format="PNG")
                zipf.writestr(output_filename, buf.getvalue())
                count += 1
                i += 1
            else:
                img = Image.new('RGB', (1600, 1100), color=(255, 255, 255))
                draw = ImageDraw.Draw(img)
                draw_label(draw, img, row, 0)
                output_filename = row['BarcodeNum'][-4:]

                # Only pair with the next row if it's also a "normal" row —
                # an A4 row never gets combined onto a shared page.
                if i + 1 < n and get_row_format(data_rows[i + 1]) == "normal":
                    draw_label(draw, img, data_rows[i + 1], 800)
                    draw.line([800, 0, 800, 1100], fill=(200, 200, 200), width=2)
                    output_filename += f"-{data_rows[i + 1]['BarcodeNum'][-4:]}"
                    i += 2
                else:
                    i += 1

                output_filename = _unique_name(output_filename + ".png")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                zipf.writestr(output_filename, buf.getvalue())
                count += 1

    zip_buffer.seek(0)
    return zip_buffer, count


def generate_single_format_zip(data_rows, fmt):
    """Used by the manual tab: renders every product as its own rotated A4 page."""
    zip_buffer = io.BytesIO()
    count = 0
    with zipfile.ZipFile(zip_buffer, "w") as zipf:
        for row in data_rows:
            page = render_single_page(row, fmt)
            output_filename = f"{row['BarcodeNum'][-4:]}_{fmt.upper()}.png"
            buf = io.BytesIO()
            page.save(buf, format="PNG")
            zipf.writestr(output_filename, buf.getvalue())
            count += 1
    zip_buffer.seek(0)
    return zip_buffer, count



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def normalize_percentage(text):
    """Accepts '20', '20%', '-20', '-20%' and returns a plain number string like '20'."""
    if not text:
        return ""
    cleaned = text.strip().replace(",", ".").replace("%", "").replace("-", "").strip()
    return cleaned


def parse_m2_per_box(name):
    """
    Looks for a box area written into the product name. Handles messy real-world
    formatting: '1.59 m2/cutie', '1,59mp', '1.59 mp', '1.59m2', 'mp 1.59', etc.
    Requires the number to sit directly next to an mp/m2/m² unit — a bare number
    (like the '60' in '60 x 60') is deliberately NOT matched, since there's no
    reliable way to tell it apart from a dimension.
    Returns the number as a float, or None if no such pattern is found.
    """
    if not name:
        return None

    # number followed by unit: "1.59 m2/cutie", "1,59mp", "1.59m2"
    match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:mp|m2|m²)\b(?:\s*/\s*(?:cutie|buc))?', name, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1).replace(",", "."))
        except ValueError:
            pass

    # unit followed by number: "mp 1.59"
    match = re.search(r'\b(?:mp|m2|m²)\s*(\d+(?:[.,]\d+)?)', name, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1).replace(",", "."))
        except ValueError:
            pass

    return None


# ---------------------------------------------------------------------------
# Validation for manually-entered products
# ---------------------------------------------------------------------------
def validate_product(p, pricing_type):
    errors = []

    if not p["Name"].strip():
        errors.append("Numele produsului este obligatoriu.")

    if not p["Percentage"].strip():
        errors.append("Procentul de reducere este obligatoriu.")
    else:
        cleaned = normalize_percentage(p["Percentage"])
        try:
            pct = float(cleaned)
            if pct <= 0 or pct >= 100:
                errors.append("Procentul trebuie să fie un număr între 1 și 99 (ex: 20, 20% sau -20).")
        except ValueError:
            errors.append("Procentul trebuie să fie un număr, fără text (ex: 20, 20% sau -20).")

    if pricing_type == "Preț pe bucată":
        if not p["OldPrice_piece"].strip():
            errors.append("Prețul vechi (lei/buc) este obligatoriu.")
        if not p["NewPrice_piece"].strip():
            errors.append("Prețul nou (lei/buc) este obligatoriu.")
    else:
        if not p["OldPrice_m2"].strip():
            errors.append("Prețul vechi (lei/m²) este obligatoriu.")
        if not p["NewPrice_m2"].strip():
            errors.append("Prețul nou (lei/m²) este obligatoriu.")

    barcode_num = p["BarcodeNum"].strip()
    if not barcode_num:
        errors.append("Codul de bare este obligatoriu.")
    elif not barcode_num.isdigit():
        errors.append("Codul de bare trebuie să conțină DOAR cifre (fără spații, litere sau liniuțe).")
    elif len(barcode_num) not in (12, 13):
        errors.append(f"Codul de bare trebuie să aibă 12 sau 13 cifre — cel introdus are {len(barcode_num)}.")

    if not p["ProductCode"].strip():
        errors.append("Codul produsului este obligatoriu.")

    return errors


# ---------------------------------------------------------------------------
# Sample CSV, for people who don't have one yet
# ---------------------------------------------------------------------------
CSV_FIELDNAMES = [
    "Name", "Percentage", "OldPrice_m2", "NewPrice_m2",
    "OldPrice_piece", "NewPrice_piece", "BarcodeNum", "ProductCode",
    "StatusText", "Format",
]

SAMPLE_ROWS = [
    {
        "Name": "Robinet Bucătărie Model X",
        "Percentage": "20",
        "OldPrice_m2": "",
        "NewPrice_m2": "",
        "OldPrice_piece": "45,00",
        "NewPrice_piece": "36,00",
        "BarcodeNum": "5901234123457",
        "ProductCode": "ROB-1001",
        "StatusText": "Stoc limitat",
        "Format": "normal",
    },
    {
        "Name": "Chiuvetă Baie Ceramică",
        "Percentage": "15",
        "OldPrice_m2": "",
        "NewPrice_m2": "",
        "OldPrice_piece": "129,99",
        "NewPrice_piece": "110,49",
        "BarcodeNum": "5901234987654",
        "ProductCode": "CHI-2050",
        "StatusText": "",
        "Format": "normal",
    },
    {
        "Name": "Parchet Laminat Zambak, 10mm, ac4, 1.59 m2/cutie",
        "Percentage": "30",
        "OldPrice_m2": "89,00",
        "NewPrice_m2": "62,30",
        "OldPrice_piece": "",
        "NewPrice_piece": "99,06",
        "BarcodeNum": "5904762005199",
        "ProductCode": "PAR-4521",
        "StatusText": "Lichidare de stoc",
        "Format": "A4",
    },
    {
        "Name": "Gresie Porțelanată 60x60",
        "Percentage": "25",
        "OldPrice_m2": "69,00",
        "NewPrice_m2": "51,75",
        "OldPrice_piece": "",
        "NewPrice_piece": "186,30",
        "BarcodeNum": "5901112223334",
        "ProductCode": "GRE-3311",
        "StatusText": "",
        "Format": "normal",
    },
]


def build_sample_csv():
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDNAMES)
    writer.writeheader()
    writer.writerows(SAMPLE_ROWS)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Generator etichete preț", page_icon="🏷️")

st.title("🏷️ Generator etichete preț")

tab_csv, tab_manual, tab_calc = st.tabs(["📄 Din fișier CSV", "✍️ Adaugă manual", "🧮 Calculator reducere"])

# ---- Tab 1: existing CSV upload flow --------------------------------------
with tab_csv:
    st.write("Pentru cine primește fișierul cu toate produsele deja pregătit.")

    st.download_button(
        label="⬇️ Descarcă un exemplu de data.csv",
        data=build_sample_csv(),
        file_name="sample_data.csv",
        mime="text/csv",
        key="download_sample_csv",
    )

    with st.expander("ℹ️ Ce trebuie să conțină fișierul CSV"):
        st.markdown(
            """
Coloanele așteptate: `Name`, `Percentage`, `OldPrice_m2`, `NewPrice_m2`, `OldPrice_piece`,
`NewPrice_piece`, `BarcodeNum`, `ProductCode`, `StatusText`, `Format`.

**Coloana `Format`** decide cum arată pagina pentru fiecare produs în parte — poți amesteca
tipuri diferite în același fișier:
- **goală sau `normal`** — eticheta obișnuită, 2 pe o pagină A4 (comportamentul de până acum). Dacă tai pagina în două, fiecare jumătate e deja mărime A5 — nu e nevoie de un format separat pentru asta.
- **`A4`** — o singură etichetă mare, rotită, pe toată pagina A4 (ca eticheta tip "raft").

Rândurile cu `A4` primesc mereu o pagină doar pentru ele; doar rândurile `normal`
consecutive se combină câte două pe o pagină.
            """
        )

    uploaded_file = st.file_uploader("Alege fișierul CSV", type=["csv"])

    if uploaded_file is not None:
        try:
            text_data = uploaded_file.getvalue().decode("utf-8")
            reader = csv.DictReader(io.StringIO(text_data))
            data_rows = list(reader)
            st.success(f"Fișier încărcat — {len(data_rows)} produse găsite.")

            if st.button("Generează etichetele", type="primary", key="generate_csv"):
                with st.spinner("Se generează imaginile..."):
                    zip_buffer, count = generate_zip_from_csv(data_rows)
                st.success(f"Gata! {count} imagini generate.")
                st.download_button(
                    label="⬇️ Descarcă arhiva ZIP",
                    data=zip_buffer,
                    file_name="generated_labels.zip",
                    mime="application/zip",
                    key="download_csv",
                )
        except Exception as e:
            st.error(f"A apărut o eroare la citirea fișierului: {e}")
    else:
        st.info("Aștept fișierul CSV.")

# ---- Tab 2: manual entry, for a handful of products by hand ---------------
with tab_manual:
    st.write("Pentru cine are doar câteva produse (până la 20) și vrea să le introducă direct aici.")

    with st.expander("ℹ️ Instrucțiuni completare — citește înainte de a adăuga produse"):
        st.markdown(
            """
- **Nume produs** — scrie numele complet; dacă e lung, se va rupe automat pe două rânduri pe etichetă. Pentru produsele la m², dacă numele conține suprafața cutiei lângă „mp”, „m2” sau „m²” (ex: „1.59 m2/cutie”, „1,59mp”, „mp 1.59”), prețul pe cutie se calculează automat. Dacă e doar un număr fără unitate (ex: doar „1.59”, care s-ar putea confunda cu o dimensiune ca „60 x 60”), nu se calculează automat — se completează manual.
- **Procent reducere** — scrie numărul; sunt acceptate toate variantele: `20`, `20%`, `-20`, `-20%`.
- **Tip preț** — alege una din variante:
    - *Preț pe bucată* — pentru produse vândute la bucată (robinete, chiuvete, obiecte sanitare etc.); acolo unde ai deja un preț vechi pe bucată, acest flux merge direct.
    - *Preț pe m² + cutie* — pentru produse vândute la m² (gresie, faianță, parchet), atunci când sistemul dă doar prețul pe m² (nu și pe cutie), de obicei pentru că are deja o mică reducere aplicată intern.
- **Calcul automat preț cutie** — dacă numele conține suprafața cutiei (ex: „1.59 m2/cutie”), prețul cutiei se calculează automat din suprafață × prețul nou pe m². Dacă nu găsește acest text în nume, sau bifezi „Prefer să calculez eu prețul pe cutie”, poți completa prețul manual.
- **Prețuri** — scrie doar cifre; virgula sau punctul pentru zecimale sunt ambele acceptate. Exemplu: `129,99`
- **Cod de bare (EAN)** — EXACT 12 sau 13 cifre, fără spații și fără litere. Îl găsești sub barele de pe produs/ambalaj.
- **Cod produs** — codul intern (SKU) al produsului, ca să poată fi găsit ulterior.
- **Text status** — opțional; de exemplu "Stoc limitat" sau "Ofertă specială". Poate rămâne gol.

Dacă un câmp e completat greșit, aplicația îți va arăta exact ce trebuie corectat înainte să adauge produsul în listă.
            """
        )

    if "manual_products" not in st.session_state:
        st.session_state.manual_products = load_cached_products()

    MAX_PRODUCTS = 20
    remaining = MAX_PRODUCTS - len(st.session_state.manual_products)

    def _compute_new_price(old_text, pct_text):
        """Returns the discounted price as a Romanian-style string, or None if inputs aren't valid numbers yet."""
        try:
            old_val = float(old_text.strip().replace(",", "."))
            pct_val = float(normalize_percentage(pct_text))
            new_val = old_val * (1 - pct_val / 100)
            return f"{new_val:.2f}".replace(".", ",")
        except (ValueError, AttributeError):
            return None

    if remaining > 0:
        st.subheader(f"Adaugă produs ({len(st.session_state.manual_products)}/{MAX_PRODUCTS})")

        name = st.text_input("Nume produs *", key="m_name")
        percentage = st.text_input("Procent reducere (%) *", placeholder="ex: 20", key="m_percentage")
        pricing_type = st.radio("Tip preț *", ["Preț pe bucată", "Preț pe m² + cutie"], key="m_pricing_type")

        page_format = st.radio(
            "Format pagină *",
            [
                "Normal (2 pe pagină A4 — devine A5 dacă tai pagina în două)",
                "A4 (o etichetă mare, rotită, pe toată pagina)",
            ],
            key="m_page_format",
        )

        manual_calc = st.checkbox(
            "Prefer să calculez eu prețul nou (fără calcul automat)", key="m_manual_calc"
        )
        auto_calc = not manual_calc

        col1, col2 = st.columns(2)
        if pricing_type == "Preț pe bucată":
            old_piece = col1.text_input("Preț vechi (lei/buc) *", placeholder="ex: 45,00", key="m_old_piece")
            old_m2 = ""
            new_m2 = ""

            if auto_calc:
                computed = _compute_new_price(old_piece, percentage)
                if computed:
                    col2.text_input(
                        "Preț nou (lei/buc) — calculat automat", value=computed, disabled=True
                    )
                    new_piece = computed
                else:
                    col2.info("Completează prețul vechi și procentul pentru calcul automat.")
                    new_piece = ""
            else:
                new_piece = col2.text_input(
                    "Preț nou (lei/buc) *", placeholder="ex: 36,00", key="m_new_piece_manual"
                )
        else:
            old_m2 = col1.text_input("Preț vechi (lei/m²) *", placeholder="ex: 89,00", key="m_old_m2")
            old_piece = ""

            if auto_calc:
                computed = _compute_new_price(old_m2, percentage)
                if computed:
                    col2.text_input(
                        "Preț nou (lei/m²) — calculat automat", value=computed, disabled=True
                    )
                    new_m2 = computed
                else:
                    col2.info("Completează prețul vechi și procentul pentru calcul automat.")
                    new_m2 = ""
            else:
                new_m2 = col2.text_input(
                    "Preț nou (lei/m²) *", placeholder="ex: 69,00", key="m_new_m2_manual"
                )

            m2_per_box = parse_m2_per_box(name)
            manual_box = st.checkbox(
                "Prefer să calculez eu prețul pe cutie", key="m_manual_box"
            )

            if not manual_box and m2_per_box and new_m2:
                try:
                    box_val = float(new_m2.strip().replace(",", ".")) * m2_per_box
                    box_computed = f"{box_val:.2f}".replace(".", ",")
                    st.text_input(
                        f"Preț cutie (lei/cutie) — calculat automat ({m2_per_box:g} m²/cutie × preț nou/m²)",
                        value=box_computed,
                        disabled=True,
                    )
                    new_piece = box_computed
                except ValueError:
                    new_piece = st.text_input(
                        "Preț cutie (lei/cutie) — opțional", placeholder="ex: 249,00", key="m_new_piece_box"
                    )
            else:
                if not manual_box and not m2_per_box:
                    st.info(
                        "Nu am găsit o suprafață clară (mp/m2/m²) în numele produsului, așa că "
                        "prețul cutiei rămâne de completat manual mai jos."
                    )
                new_piece = st.text_input(
                    "Preț cutie (lei/cutie) — opțional", placeholder="ex: 249,00", key="m_new_piece_box"
                )

        if auto_calc:
            st.caption("💡 Prețul nou este calculat automat din prețul vechi și procentul de reducere.")

        barcode_num = st.text_input("Cod de bare (EAN) *", placeholder="ex: 5901234123457", key="m_barcode")
        product_code = st.text_input("Cod produs *", placeholder="ex: GRE-4521", key="m_product_code")
        status_text = st.text_input("Text status — opțional", placeholder="ex: Stoc limitat", key="m_status")
        quantity = st.number_input(
            "Câte etichete identice? (ex: 4 dacă vrei aceeași etichetă de 4 ori)",
            min_value=1, max_value=100, value=1, step=1, key="m_quantity",
        )

        if st.button("➕ Adaugă în listă", key="add_product_btn"):
            candidate = {
                "Name": name,
                "Percentage": normalize_percentage(percentage),
                "OldPrice_m2": old_m2.strip(),
                "NewPrice_m2": new_m2.strip(),
                "OldPrice_piece": old_piece.strip(),
                "NewPrice_piece": new_piece.strip(),
                "BarcodeNum": barcode_num.strip(),
                "ProductCode": product_code.strip(),
                "StatusText": status_text.strip(),
                "Format": "a4" if page_format.startswith("A4") else "normal",
                "Quantity": int(quantity),
            }
            errors = validate_product(candidate, pricing_type)
            if errors:
                st.error(
                    "Nu am putut adăuga produsul din cauza următoarelor erori:\n\n"
                    + "\n".join(f"- {e}" for e in errors)
                )
            else:
                st.session_state.manual_products.append(candidate)
                save_cached_products(st.session_state.manual_products)
                for k in [
                    "m_name", "m_percentage", "m_old_piece", "m_new_piece_manual",
                    "m_old_m2", "m_new_m2_manual", "m_new_piece_box", "m_manual_box",
                    "m_barcode", "m_product_code", "m_status", "m_quantity",
                ]:
                    if k in st.session_state:
                        del st.session_state[k]
                st.success(f"„{name}” a fost adăugat în listă.")
                st.rerun()
    else:
        st.warning(f"Ai atins limita de {MAX_PRODUCTS} produse. Șterge unul mai jos dacă vrei să adaugi altul.")

    if st.session_state.manual_products:
        st.subheader("Produse adăugate")

        def _select_all_callback():
            val = st.session_state.get("chk_select_all", False)
            for i in range(len(st.session_state.manual_products)):
                st.session_state[f"chk_{i}"] = val

        n_products = len(st.session_state.manual_products)

        def _select_range_callback():
            lo = min(st.session_state.get("m_range_start", 1), st.session_state.get("m_range_end", n_products))
            hi = max(st.session_state.get("m_range_start", 1), st.session_state.get("m_range_end", n_products))
            for i in range(n_products):
                st.session_state[f"chk_{i}"] = lo <= (i + 1) <= hi

        top_cols = st.columns([1.3, 1.5, 1.5, 2])
        top_cols[0].checkbox("Selectează tot", key="chk_select_all", on_change=_select_all_callback)
        range_start = top_cols[1].number_input(
            "De la #", min_value=1, max_value=n_products, value=1, step=1, key="m_range_start"
        )
        range_end = top_cols[2].number_input(
            "Până la #", min_value=1, max_value=n_products, value=n_products, step=1, key="m_range_end"
        )
        top_cols[3].button("Selectează intervalul", on_click=_select_range_callback)

        def _make_qty_callback(index):
            def _cb():
                new_qty = st.session_state.get(f"qty_{index}")
                if new_qty and 1 <= new_qty <= 100:
                    st.session_state.manual_products[index]["Quantity"] = int(new_qty)
                    save_cached_products(st.session_state.manual_products)
            return _cb

        for idx, p in enumerate(st.session_state.manual_products):
            cols = st.columns([0.4, 0.4, 3.5, 0.9, 1])
            cols[0].write(f"**{idx + 1}.**")
            cols[1].checkbox("", key=f"chk_{idx}", label_visibility="collapsed")
            if p["OldPrice_piece"]:
                price_label = f"{p['NewPrice_piece']} lei/buc"
            else:
                price_label = f"{p['NewPrice_m2']} lei/m²"
            format_tag = " 📄 A4" if p.get("Format") == "a4" else ""
            cols[2].write(
                f"**{p['Name']}** — {price_label} (-{p['Percentage']}%) — cod: {p['ProductCode']}{format_tag}"
            )
            cols[3].number_input(
                "Buc.",
                min_value=1, max_value=100,
                value=int(p.get("Quantity", 1)),
                step=1,
                key=f"qty_{idx}",
                on_change=_make_qty_callback(idx),
                label_visibility="collapsed",
            )
            if cols[4].button("🗑️", key=f"del_{idx}"):
                st.session_state.manual_products.pop(idx)
                save_cached_products(st.session_state.manual_products)
                for i in range(n_products):
                    key = f"chk_{i}"
                    if key in st.session_state:
                        del st.session_state[key]
                if "chk_select_all" in st.session_state:
                    del st.session_state["chk_select_all"]
                for k in ("m_range_start", "m_range_end"):
                    if k in st.session_state:
                        del st.session_state[k]
                st.rerun()

        selected_indices = [i for i in range(n_products) if st.session_state.get(f"chk_{i}", False)]

        bulk_cols = st.columns(2)
        if bulk_cols[0].button(
            f"🗑️ Șterge selectate ({len(selected_indices)})",
            disabled=not selected_indices,
            key="delete_selected",
        ):
            for i in sorted(selected_indices, reverse=True):
                st.session_state.manual_products.pop(i)
            save_cached_products(st.session_state.manual_products)
            for i in range(n_products):
                key = f"chk_{i}"
                if key in st.session_state:
                    del st.session_state[key]
            if "chk_select_all" in st.session_state:
                del st.session_state["chk_select_all"]
            for k in ("m_range_start", "m_range_end"):
                if k in st.session_state:
                    del st.session_state[k]
            st.success(f"{len(selected_indices)} produse șterse.")
            st.rerun()
        def _deselect_all_callback():
            for i in range(n_products):
                st.session_state[f"chk_{i}"] = False
            st.session_state["chk_select_all"] = False

        bulk_cols[1].button("Deselectează tot", key="deselect_all", on_click=_deselect_all_callback)

        st.divider()
        if st.button("Generează etichetele", type="primary", key="generate_manual"):
            expanded_rows = []
            for p in st.session_state.manual_products:
                expanded_rows.extend([p] * int(p.get("Quantity", 1)))
            with st.spinner("Se generează imaginile..."):
                zip_buffer, count = generate_zip_from_csv(expanded_rows)
            st.success(f"Gata! {count} imagini generate.")
            st.download_button(
                label="⬇️ Descarcă arhiva ZIP",
                data=zip_buffer,
                file_name="generated_labels.zip",
                mime="application/zip",
                key="download_manual",
            )
    else:
        st.info("Nu ai adăugat încă niciun produs.")

# ---- Tab 3: quick discount calculator --------------------------------------
with tab_calc:
    st.write(
        "Pune prețul curent și procentul de reducere — vezi imediat prețul nou "
        "și cât scade. Folosește rezultatul ca să completezi câmpurile de preț "
        "din CSV sau din formularul manual."
    )

    col1, col2 = st.columns(2)
    current_price = col1.number_input(
        "Preț curent (lei)", min_value=0.0, step=0.01, format="%.2f", key="calc_current_price"
    )
    percent = col2.number_input(
        "Procent reducere (%)", min_value=0.0, max_value=100.0, step=1.0, format="%.0f", key="calc_percent"
    )

    if current_price > 0 and percent > 0:
        discount_amount = current_price * percent / 100
        new_price = current_price - discount_amount

        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("Preț curent", f"{current_price:.2f} lei")
        c2.metric("Reducere", f"-{discount_amount:.2f} lei")
        c3.metric("Preț nou", f"{new_price:.2f} lei")
    else:
        st.info("Completează ambele câmpuri pentru a vedea rezultatul.")
