from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def build_prescription_pdf(prescription, patient, doctor):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 20 * mm

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(20 * mm, y, "Patient Prescription")
    y -= 12 * mm

    pdf.setFont("Helvetica", 11)
    pdf.drawString(20 * mm, y, f"Prescription ID: {prescription.get('prescription_code', '')}")
    y -= 8 * mm
    pdf.drawString(20 * mm, y, f"Patient: {patient.get('full_name', '')}")
    y -= 8 * mm
    pdf.drawString(20 * mm, y, f"Doctor: {doctor.get('full_name', '')}")
    y -= 8 * mm
    pdf.drawString(20 * mm, y, f"Diagnosis: {prescription.get('diagnosis', '')}")
    y -= 12 * mm

    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(20 * mm, y, "Medicines")
    y -= 8 * mm
    pdf.setFont("Helvetica", 11)

    for index, medicine in enumerate(prescription.get("medicines", []), start=1):
        line = (
            f"{index}. {medicine.get('name', '')} | "
            f"Dose: {medicine.get('dosage', '')} | "
            f"Duration: {medicine.get('duration', '')}"
        )
        pdf.drawString(20 * mm, y, line[:100])
        y -= 7 * mm
        notes = medicine.get("notes")
        if notes:
            pdf.drawString(25 * mm, y, f"Notes: {notes}"[:95])
            y -= 7 * mm
        if y < 30 * mm:
            pdf.showPage()
            y = height - 20 * mm
            pdf.setFont("Helvetica", 11)

    y -= 5 * mm
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(20 * mm, y, "Advice")
    y -= 8 * mm
    pdf.setFont("Helvetica", 11)
    for line in str(prescription.get("advice", "")).splitlines() or [""]:
        pdf.drawString(20 * mm, y, line[:100])
        y -= 7 * mm

    y -= 5 * mm
    pdf.drawString(20 * mm, y, f"Next Visit: {prescription.get('next_visit_date', 'N/A')}")

    pdf.save()
    buffer.seek(0)
    return buffer
