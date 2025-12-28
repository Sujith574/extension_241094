from fastapi import FastAPI, UploadFile, File, Form
from pydantic import BaseModel
from PIL import Image
import pytesseract
import io
import os
from openai import OpenAI

# -------------------------------------------------
# TESSERACT PATH (Render/Linux safe)
# -------------------------------------------------
# On Render, tesseract is usually available as `tesseract`
pytesseract.pytesseract.tesseract_cmd = "tesseract"

# -------------------------------------------------
# OPENAI CLIENT (READ FROM ENV)
# -------------------------------------------------
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

app = FastAPI()

# -------------------------------------------------
# LICENSED MACHINE IDS
# -------------------------------------------------
ALLOWED_IDS = {
    "6b4590568865aa31c3d16c219bf64a925ef7b67ab3de1afaeb888345d5f256410",
    # add friend device IDs here
}

# -------------------------------------------------
# VERIFY MACHINE ID
# -------------------------------------------------
class VerifyRequest(BaseModel):
    machine_id: str

@app.post("/verify")
def verify(req: VerifyRequest):
    return {"allowed": req.machine_id in ALLOWED_IDS}

# -------------------------------------------------
# IMAGE PREPROCESSING (OCR ACCURACY)
# -------------------------------------------------
def preprocess_image(img: Image.Image) -> Image.Image:
    img = img.convert("L")
    img = img.point(lambda x: 0 if x < 140 else 255, "1")
    return img

# -------------------------------------------------
# OCR
# -------------------------------------------------
def extract_text(img: Image.Image) -> str:
    return pytesseract.image_to_string(img, config="--oem 3 --psm 6")

# -------------------------------------------------
# ANALYZE SCREENSHOT
# -------------------------------------------------
@app.post("/analyze")
async def analyze(
    image: UploadFile = File(...),
    machine_id: str = Form(...)
):
    # LICENSE CHECK
    if machine_id not in ALLOWED_IDS:
        return {"answer": "Unauthorized device"}

    # READ IMAGE
    img_bytes = await image.read()
    img = Image.open(io.BytesIO(img_bytes))

    # OCR
    img = preprocess_image(img)
    extracted_text = extract_text(img)

    if not extracted_text.strip():
        return {"answer": "No readable text found"}

    # -------------------------------------------------
    # AI PROMPT
    # -------------------------------------------------
    prompt = f"""
Follow these rules STRICTLY:
- Question → short clear answer
- MCQs → ONLY correct option
- Code → ONLY correct code
- Math → FINAL answer only

SCREEN TEXT:
{extracted_text}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are precise and concise."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )

        answer = response.choices[0].message.content.strip()
        return {"answer": answer}

    except Exception as e:
        return {"answer": f"AI error: {str(e)}"}


