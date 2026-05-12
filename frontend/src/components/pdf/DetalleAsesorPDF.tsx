import { Document, Page, StyleSheet } from "@react-pdf/renderer"

import PDFFooter from "@/components/pdf/PDFFooter"
import PDFHeader from "@/components/pdf/PDFHeader"
import PDFTable from "@/components/pdf/PDFTable"
import { PDF_COLORS, PDF_FONTS } from "@/lib/pdfTheme"
import type { DetalleAsesorPDFPayload } from "@/types"

const styles = StyleSheet.create({
    page: {
        paddingTop: 24,
        paddingBottom: 28,
        paddingHorizontal: 24,
        backgroundColor: PDF_COLORS.background,
        color: PDF_COLORS.text,
        fontSize: PDF_FONTS.body,
    },
})

export default function DetalleAsesorPDF({ data }: { data: DetalleAsesorPDFPayload }) {
    return (
        <Document title="Detalle por Asesor">
            <Page size="A4" orientation="landscape" style={styles.page}>
                <PDFHeader {...data.header} />
                <PDFTable title="Identidad de registros" table={data.table_identity} />
                <PDFTable title="Desglose por examen" table={data.table_exams} />
                <PDFFooter generatedAt={data.header.generated_at} />
            </Page>
        </Document>
    )
}
