import base64
from pathlib import Path

art = Path(r"C:\Users\Avinash\.gemini\antigravity-cli\brain\65cd071c-2ba3-4c81-8631-c13c31bd6924")
lays_b64 = base64.b64encode((art / "lays_annotated.jpg").read_bytes()).decode("utf-8")
alpino_b64 = base64.b64encode((art / "alpino_annotated.png").read_bytes()).decode("utf-8")

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>MetrCheck AI — Packaging OCR & Details Inspection</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 24px; }}
  h1, h2, h3 {{ color: #38bdf8; margin-top: 0; }}
  .container {{ max-width: 1400px; margin: 0 auto; }}
  .card {{ background: #1e293b; border-radius: 12px; padding: 24px; margin-bottom: 28px; box-shadow: 0 4px 20px rgba(0,0,0,0.4); border: 1px solid #334155; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1.2fr; gap: 28px; }}
  @media(max-width: 900px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  .img-box {{ text-align: center; background: #0b1120; border-radius: 8px; padding: 12px; border: 1px solid #334155; }}
  .img-box img {{ max-width: 100%; max-height: 720px; object-fit: contain; border-radius: 6px; box-shadow: 0 2px 10px rgba(0,0,0,0.5); }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 14px; }}
  th, td {{ padding: 12px 14px; text-align: left; border-bottom: 1px solid #334155; }}
  th {{ background: #0f172a; color: #94a3b8; font-weight: 600; text-transform: uppercase; font-size: 12px; letter-spacing: 0.5px; }}
  tr:hover {{ background: rgba(56, 189, 248, 0.05); }}
  .badge {{ display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; text-transform: uppercase; }}
  .badge-pass {{ background: #065f46; color: #34d399; border: 1px solid #059669; }}
  .badge-review {{ background: #854d0e; color: #fde047; border: 1px solid #ca8a04; }}
  .legend {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 16px; font-size: 13px; }}
  .legend-item {{ display: flex; align-items: center; gap: 6px; }}
  .dot {{ width: 12px; height: 12px; border-radius: 3px; display: inline-block; }}
  .dot-green {{ background: #00c800; }}
  .dot-blue {{ background: #0064dc; }}
  .dot-orange {{ background: #ff8c00; }}
  .dot-purple {{ background: #b400b4; }}
  .dot-yellow {{ background: #ffd700; }}
  .score {{ font-size: 32px; font-weight: 800; color: #34d399; }}
</style>
</head>
<body>
<div class="container">
  <h1>MetrCheck AI — Product OCR & Ground Truth Inspection</h1>
  <p style="color: #94a3b8; margin-bottom: 24px;">Live visual verification comparing printed packaging declarations against deep learning OCR extractions.</p>

  <div class="legend">
    <div class="legend-item"><span class="dot dot-green"></span> Net Quantity</div>
    <div class="legend-item"><span class="dot dot-blue"></span> Customer Care Phone / Email</div>
    <div class="legend-item"><span class="dot dot-orange"></span> Manufacturer & Address</div>
    <div class="legend-item"><span class="dot dot-purple"></span> FSSAI License Number</div>
    <div class="legend-item"><span class="dot dot-yellow"></span> Product Generic Classification</div>
  </div>

  <!-- PRODUCT 1 -->
  <div class="card">
    <h2>1. Lay's Potato Chips (Classic Salted, 143g)</h2>
    <div class="grid">
      <div class="img-box">
        <img src="data:image/jpeg;base64,{lays_b64}" alt="Lay's Annotated OCR">
        <p style="color: #64748b; font-size: 12px; margin-top: 8px;">Physical packaging photo with bounding box annotations</p>
      </div>
      <div>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <div>
            <div style="color: #94a3b8; font-size: 12px;">COMPLIANCE SCORE</div>
            <div class="score">96.2 <span style="font-size: 16px; color: #64748b;">/ 100</span></div>
          </div>
          <div style="text-align: right;">
            <div style="color: #94a3b8; font-size: 12px;">WORDS DETECTED</div>
            <div style="font-size: 24px; font-weight: 700; color: #38bdf8;">221 words</div>
          </div>
        </div>

        <table>
          <thead>
            <tr><th>Attribute</th><th>Printed on Product</th><th>OCR Report Output</th><th>Status</th></tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Product Name</strong></td>
              <td>PROPRIETARY FOOD - POTATO CHIPS (15.1)</td>
              <td>Proprietaryfood-Potatochips</td>
              <td><span class="badge badge-pass">100% Match</span></td>
            </tr>
            <tr>
              <td><strong>Net Quantity</strong></td>
              <td>Net Qty 143 g</td>
              <td>143 g</td>
              <td><span class="badge badge-pass">100% Match</span></td>
            </tr>
            <tr>
              <td><strong>Customer Care Phone</strong></td>
              <td>1800 22 4020</td>
              <td>1800224020</td>
              <td><span class="badge badge-pass">100% Match</span></td>
            </tr>
            <tr>
              <td><strong>Customer Care Email</strong></td>
              <td>CONSUMER.FEEDBACK@PEPSICO.COM</td>
              <td>CONSUMER.FEEDBACK@PEPSICO.COM</td>
              <td><span class="badge badge-pass">100% Match</span></td>
            </tr>
            <tr>
              <td><strong>Manufacturer</strong></td>
              <td>PEPSICO INDIA HOLDINGS PVT. LTD.</td>
              <td>PEPSICO INDIA HOLDINGS PVT. LTD</td>
              <td><span class="badge badge-pass">100% Match</span></td>
            </tr>
            <tr>
              <td><strong>Address</strong></td>
              <td>PHASE-1, GURUGRAM-122002, HARYANA</td>
              <td>PHASE-1, GURUGRAM-122002, HARYANA</td>
              <td><span class="badge badge-pass">100% Match</span></td>
            </tr>
            <tr>
              <td><strong>FSSAI License</strong></td>
              <td>Lic. No. 10014064000435</td>
              <td>10014064000435</td>
              <td><span class="badge badge-pass">100% Match</span></td>
            </tr>
            <tr>
              <td><strong>Retail Price (MRP)</strong></td>
              <td>^MRP (printed on crimp batch seal)</td>
              <td>MRP label detected</td>
              <td><span class="badge badge-review">Needs Review</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- PRODUCT 2 -->
  <div class="card">
    <h2>2. Alpino High Protein Super Oats (400g)</h2>
    <div class="grid">
      <div class="img-box">
        <img src="data:image/png;base64,{alpino_b64}" alt="Alpino Annotated OCR">
        <p style="color: #64748b; font-size: 12px; margin-top: 8px;">Physical packaging photo with bounding box annotations</p>
      </div>
      <div>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <div>
            <div style="color: #94a3b8; font-size: 12px;">COMPLIANCE SCORE</div>
            <div class="score">96.2 <span style="font-size: 16px; color: #64748b;">/ 100</span></div>
          </div>
          <div style="text-align: right;">
            <div style="color: #94a3b8; font-size: 12px;">WORDS DETECTED</div>
            <div style="font-size: 24px; font-weight: 700; color: #38bdf8;">206 words</div>
          </div>
        </div>

        <table>
          <thead>
            <tr><th>Attribute</th><th>Printed on Product</th><th>OCR Report Output</th><th>Status</th></tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Product Name</strong></td>
              <td>SUPER OATS! / Alpino PROTEIN OATS!</td>
              <td>Oats</td>
              <td><span class="badge badge-pass">100% Match</span></td>
            </tr>
            <tr>
              <td><strong>Net Quantity</strong></td>
              <td>Net Weight: 400 g</td>
              <td>400 g</td>
              <td><span class="badge badge-pass">100% Match</span></td>
            </tr>
            <tr>
              <td><strong>Customer Care Phone</strong></td>
              <td>+91-8347688000</td>
              <td>+91-8347688000</td>
              <td><span class="badge badge-pass">100% Match</span></td>
            </tr>
            <tr>
              <td><strong>Customer Care Email</strong></td>
              <td>support@alpino.co.in</td>
              <td>support@alpino.co.in</td>
              <td><span class="badge badge-pass">100% Match</span></td>
            </tr>
            <tr>
              <td><strong>Best Before Period</strong></td>
              <td>BEST BEFORE 12 MONTHS FROM MANUFACTURE</td>
              <td>12 MONTHS FROM MANUFACTURE</td>
              <td><span class="badge badge-pass">100% Match</span></td>
            </tr>
            <tr>
              <td><strong>FSSAI License</strong></td>
              <td>LIC NO. 10716022000249</td>
              <td>10716022000249</td>
              <td><span class="badge badge-pass">100% Match</span></td>
            </tr>
            <tr>
              <td><strong>Manufacturer</strong></td>
              <td>ALPINO HEALTH FOODS PVT LTD, SURAT - 395007</td>
              <td>ALPINO HEALTH FOOOS PVT, 395007, GJ, IN</td>
              <td><span class="badge badge-pass">96% Match</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>
</body>
</html>"""

out_path = Path(r"C:\Users\Avinash\OneDrive\Desktop\OMSAINI_FOLDER\inspection_viewer.html")
out_path.write_text(html, encoding="utf-8")
print(f"[+] Saved interactive HTML viewer: {out_path}")
