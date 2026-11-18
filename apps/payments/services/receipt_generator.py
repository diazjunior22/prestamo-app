import io
from decimal import Decimal
from django.core.files.base import ContentFile
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether,
)

def mask_document(doc_number: str) -> str:
    """Masks customer document number for privacy, showing only first 4 and last 2 digits."""
    if not doc_number:
        return "N/A"
    clean_doc = doc_number.strip()
    if len(clean_doc) <= 5:
        return clean_doc
    return f"{clean_doc[:4]}****{clean_doc[-2:]}"


def build_receipt_pdf_bytes(payment) -> bytes:
    """
    Generates a professional financial PDF payment receipt using ReportLab.
    Returns bytes of the generated PDF document.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    # Styles
    styles = getSampleStyleSheet()
    
    # Custom Brand Colors
    NAVY = colors.HexColor('#14243A')
    BLUE = colors.HexColor('#2563EB')
    SLATE_DARK = colors.HexColor('#1E293B')
    SLATE_MUTED = colors.HexColor('#64748B')
    SLATE_LIGHT = colors.HexColor('#F8FAFC')
    BORDER_COLOR = colors.HexColor('#E2E8F0')
    EMERALD = colors.HexColor('#059669')
    RED = colors.HexColor('#DC2626')

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=NAVY,
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=SLATE_MUTED,
    )

    receipt_tag_style = ParagraphStyle(
        'ReceiptTag',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        alignment=2,  # Right aligned
        textColor=BLUE,
    )

    date_tag_style = ParagraphStyle(
        'DateTag',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        alignment=2,
        textColor=SLATE_MUTED,
    )

    section_header_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=NAVY,
    )

    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=SLATE_DARK,
    )

    body_bold_style = ParagraphStyle(
        'BodyBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=12,
        textColor=SLATE_DARK,
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white,
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=SLATE_DARK,
    )

    table_cell_right_style = ParagraphStyle(
        'TableCellRight',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        alignment=2,
        textColor=SLATE_DARK,
    )

    footer_style = ParagraphStyle(
        'FooterText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        alignment=1,  # Center
        textColor=SLATE_MUTED,
    )

    story = []

    # 1. Header (Brand vs Receipt Info)
    status_label = " (REVERSADO)" if payment.is_reversed else ""
    header_data = [
        [
            Paragraph("<b>LOANMANAGER</b>", title_style),
            Paragraph(f"<b>COMPROBANTE DE PAGO{status_label}</b>", receipt_tag_style)
        ],
        [
            Paragraph("Sistema de Gestión Financiera de Créditos y Cartera", subtitle_style),
            Paragraph(f"Recibo N°: <b>{payment.receipt_number}</b>", date_tag_style)
        ],
        [
            Paragraph("Bogotá D.C., Colombia — Moneda: COP ($)", subtitle_style),
            Paragraph(f"Fecha de emisión: {payment.payment_date.strftime('%d/%m/%Y')}", date_tag_style)
        ]
    ]

    header_table = Table(header_data, colWidths=[3.5 * inch, 3.8 * inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=NAVY, spaceAfter=12))

    # 2. Customer & Loan Information Card
    loan = payment.loan
    customer = payment.customer
    masked_doc = f"{customer.get_document_type_display()}: {mask_document(customer.document_number)}"

    info_data = [
        [
            Paragraph("<b>DATOS DEL CLIENTE</b>", section_header_style),
            Paragraph("<b>DATOS DE LA OBLIGACIÓN</b>", section_header_style),
        ],
        [
            Paragraph(f"Nombre: <b>{customer.full_name}</b>", body_style),
            Paragraph(f"Préstamo: <b>{loan.loan_code}</b>", body_style),
        ],
        [
            Paragraph(f"Identificación: {masked_doc}", body_style),
            Paragraph(f"Capital Original: $ {loan.principal:,.0f} COP", body_style),
        ],
        [
            Paragraph(f"Teléfono / WhatsApp: {customer.whatsapp or customer.phone}", body_style),
            Paragraph(f"Modalidad: {loan.get_interest_type_display()} ({loan.interest_rate}%)", body_style),
        ],
        [
            Paragraph(f"Ciudad: {customer.city or 'No especificada'}", body_style),
            Paragraph(f"Frecuencia: {loan.get_payment_frequency_display()}", body_style),
        ],
    ]

    info_table = Table(info_data, colWidths=[3.65 * inch, 3.65 * inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), SLATE_LIGHT),
        ('BOX', (0, 0), (-1, -1), 1, BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 12))

    # 3. Transaction Summary Highlight
    payment_method_display = payment.get_payment_method_display()
    ref_display = payment.reference_number or 'Sin referencia'
    created_by_display = payment.created_by.get_full_name() if payment.created_by else 'Administrador'

    tx_summary_data = [
        [
            Paragraph("<b>DETALLE DE LA TRANSACCIÓN</b>", section_header_style),
            Paragraph("", section_header_style)
        ],
        [
            Paragraph(f"Monto Pagado: <font color='#059669' size='11'><b>$ {payment.amount:,.2f} COP</b></font>", body_style),
            Paragraph(f"Método de Pago: <b>{payment_method_display}</b>", body_style),
        ],
        [
            Paragraph(f"Comprobante / Ref: <b>{ref_display}</b>", body_style),
            Paragraph(f"Registrado por: <b>{created_by_display}</b>", body_style),
        ]
    ]

    tx_table = Table(tx_summary_data, colWidths=[3.65 * inch, 3.65 * inch])
    tx_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#EFF6FF')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#BFDBFE')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(tx_table)
    story.append(Spacer(1, 14))

    # 4. Allocations Table (Waterfall Imputation)
    story.append(Paragraph("<b>DESGLOSE DE IMPUTACIÓN A CUOTAS</b>", section_header_style))
    story.append(Spacer(1, 6))

    allocations_data = [
        [
            Paragraph("Cuota #", table_header_style),
            Paragraph("Vencimiento", table_header_style),
            Paragraph("Abono Interés", table_header_style),
            Paragraph("Abono Capital", table_header_style),
            Paragraph("Total Aplicado", table_header_style),
            Paragraph("Saldo Cuota", table_header_style),
            Paragraph("Estado Cuota", table_header_style),
        ]
    ]

    allocations = payment.allocations.select_related('installment').order_by('installment__installment_number')
    
    total_principal_all = Decimal('0.00')
    total_interest_all = Decimal('0.00')
    total_applied_all = Decimal('0.00')

    for alloc in allocations:
        inst = alloc.installment
        total_principal_all += alloc.principal_applied
        total_interest_all += alloc.interest_applied
        total_applied_all += alloc.total_applied

        status_text = inst.get_status_display()
        allocations_data.append([
            Paragraph(f"Cuota {inst.installment_number}", table_cell_style),
            Paragraph(inst.due_date.strftime('%d/%m/%Y'), table_cell_style),
            Paragraph(f"$ {alloc.interest_applied:,.2f}", table_cell_right_style),
            Paragraph(f"$ {alloc.principal_applied:,.2f}", table_cell_right_style),
            Paragraph(f"<b>$ {alloc.total_applied:,.2f}</b>", table_cell_right_style),
            Paragraph(f"$ {inst.balance:,.2f}", table_cell_right_style),
            Paragraph(status_text, table_cell_style),
        ])

    # Total Row
    allocations_data.append([
        Paragraph("<b>TOTALES</b>", body_bold_style),
        Paragraph("", table_cell_style),
        Paragraph(f"<b>$ {total_interest_all:,.2f}</b>", table_cell_right_style),
        Paragraph(f"<b>$ {total_principal_all:,.2f}</b>", table_cell_right_style),
        Paragraph(f"<b>$ {total_applied_all:,.2f}</b>", table_cell_right_style),
        Paragraph("", table_cell_style),
        Paragraph("", table_cell_style),
    ])

    alloc_table = Table(
        allocations_data,
        colWidths=[0.8 * inch, 0.9 * inch, 1.15 * inch, 1.15 * inch, 1.2 * inch, 1.05 * inch, 1.05 * inch]
    )
    alloc_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('ALIGN', (2, 0), (4, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('BACKGROUND', (0, -1), (-1, -1), SLATE_LIGHT),
        ('LINEABOVE', (0, -1), (-1, -1), 1.5, NAVY),
    ]))
    story.append(alloc_table)
    story.append(Spacer(1, 14))

    # 5. Loan Balances Summary Box
    previous_balance = loan.balance + payment.amount if not payment.is_reversed else loan.balance
    current_balance = loan.balance

    summary_data = [
        [
            Paragraph("Saldo Anterior del Préstamo:", body_style),
            Paragraph(f"<b>$ {previous_balance:,.2f} COP</b>", table_cell_right_style),
        ],
        [
            Paragraph("Total Abonado en este Recibo:", body_style),
            Paragraph(f"<font color='#059669'><b>- $ {payment.amount:,.2f} COP</b></font>", table_cell_right_style),
        ],
        [
            Paragraph("<b>NUEVO SALDO TOTAL PENDIENTE:</b>", body_bold_style),
            Paragraph(f"<font color='#1E293B' size='10'><b>$ {current_balance:,.2f} COP</b></font>", table_cell_right_style),
        ],
    ]

    summary_table = Table(summary_data, colWidths=[4.8 * inch, 2.5 * inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), SLATE_LIGHT),
        ('BOX', (0, 0), (-1, -1), 1, BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_table)

    # 6. Notes if present
    if payment.notes:
        story.append(Spacer(1, 10))
        notes_p = Paragraph(f"<b>Observaciones:</b> {payment.notes}", body_style)
        story.append(notes_p)

    if payment.is_reversed:
        story.append(Spacer(1, 10))
        reversal_info = [
            [
                Paragraph(
                    f"<font color='#DC2626'><b>AVISO DE REVERSIÓN:</b> Este recibo fue formalmente REVERSADO el {payment.reversed_at.strftime('%d/%m/%Y %H:%M') if payment.reversed_at else ''}. Motivo: {payment.reversal_reason or 'No especificado'}.</font>",
                    body_style
                )
            ]
        ]
        rev_table = Table(reversal_info, colWidths=[7.3 * inch])
        rev_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FEF2F2')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#FCA5A5')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(rev_table)

    # 7. Signatures & Legal Footer
    story.append(Spacer(1, 24))
    
    signatures_data = [
        [
            Paragraph("________________________________________", footer_style),
            Paragraph("________________________________________", footer_style),
        ],
        [
            Paragraph("Firma Autorizada / Cobrador", footer_style),
            Paragraph("Firma Cliente / Conforme", footer_style),
        ]
    ]
    sig_table = Table(signatures_data, colWidths=[3.65 * inch, 3.65 * inch])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(KeepTogether(sig_table))

    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_COLOR, spaceAfter=8))
    story.append(Paragraph(
        "Este comprobante digital ha sido emitido de manera electrónica por LoanManager. "
        "Conserve este soporte para constancia de sus abonos. No tiene validez con enmiendas o tachaduras.",
        footer_style
    ))

    # Build Document
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def generate_and_save_receipt_pdf(payment) -> str:
    """
    Builds the PDF receipt for a Payment and saves it to payment.receipt_pdf FileField.
    Returns the file name.
    """
    pdf_bytes = build_receipt_pdf_bytes(payment)
    file_name = f"{payment.receipt_number}.pdf"
    payment.receipt_pdf.save(file_name, ContentFile(pdf_bytes), save=True)
    return file_name
