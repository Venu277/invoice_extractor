from reportlab.pdfgen import canvas


def make_invoice(filename, vendor, inv_no, date, gstin, subtotal,
                 tax_type="gst", total_override=None):
    tax = round(subtotal * 0.18, 2)
    half = round(tax / 2, 2)
    if tax_type == "cgst_sgst":
        tax_lines = [f"CGST (9%): Rs. {half:.2f}", f"SGST (9%): Rs. {half:.2f}"]
        tax_total = half * 2
    elif tax_type == "igst":
        tax_lines = [f"IGST (18%): Rs. {tax:.2f}"]
        tax_total = tax
    else:
        tax_lines = [f"GST (18%): Rs. {tax:.2f}"]
        tax_total = tax
    total = total_override if total_override else round(subtotal + tax_total, 2)
    lines = [vendor, "TAX INVOICE", f"Invoice No: {inv_no}", f"Invoice Date: {date}",
             f"GSTIN: {gstin}", "", f"Subtotal: Rs. {subtotal:.2f}"] + tax_lines + \
            [f"Grand Total: Rs. {total:.2f}"]
    c = canvas.Canvas(filename)
    y = 800
    for line in lines:
        c.drawString(72, y, line)
        y -= 24
    c.save()


make_invoice("invoices/inv1.pdf", "Sharma Traders", "INV-1001", "12/03/2025",
             "29ABCDE1234F1Z5", 10000, tax_type="gst")
make_invoice("invoices/inv2.pdf", "Bright Tech Solutions", "BT/2025/045", "05-04-2025",
             "27AAPFU0939F1ZV", 25000, tax_type="cgst_sgst")
make_invoice("invoices/inv3.pdf", "Mehta Hardware", "MH-310", "15 Mar 2025",
             "07AABCM1234C1Z8", 40000, tax_type="igst")
make_invoice("invoices/inv4.pdf", "Kumar Stationery", "KS-77", "20/04/2025",
             "29ABCDE1234", 5000, tax_type="cgst_sgst", total_override=6000)
make_invoice("invoices/inv5.pdf", "Sharma Traders", "INV-1002", "25/03/2025",
             "29ABCDE1234F1Z5", 18000, tax_type="gst")
print("Sample invoices created in the invoices/ folder")