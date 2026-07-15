import csv
import io
import os
import zipfile

import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import barcode
from barcode.writer import ImageWriter

# ---------------------------------------------------------------------------
# Font paths — these two .ttf files must sit next to this app.py in the repo
# ---------------------------------------------------------------------------
FONT_REGULAR = "Roboto-Regular.ttf"
FONT_BOLD = "Roboto-Bold.ttf"


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


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Generator etichete preț", page_icon="🏷️")

st.title("🏷️ Generator etichete preț")
st.write("Încarcă fișierul CSV cu produsele și apasă butonul pentru a genera etichetele.")

uploaded_file = st.file_uploader("Alege fișierul CSV", type=["csv"])

if uploaded_file is not None:
    try:
        text_data = uploaded_file.getvalue().decode("utf-8")
        reader = csv.DictReader(io.StringIO(text_data))
        data_rows = list(reader)
        st.success(f"Fișier încărcat — {len(data_rows)} produse găsite.")

        if st.button("Generează etichetele", type="primary"):
            with st.spinner("Se generează imaginile..."):
                zip_buffer, count = generate_zip(data_rows)
            st.success(f"Gata! {count} imagini generate.")
            st.download_button(
                label="⬇️ Descarcă arhiva ZIP",
                data=zip_buffer,
                file_name="generated_labels.zip",
                mime="application/zip",
            )
    except Exception as e:
        st.error(f"A apărut o eroare la citirea fișierului: {e}")
else:
    st.info("Aștept fișierul CSV.")
