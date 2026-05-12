import { Document, Page, StyleSheet } from "@react-pdf/renderer"

import PDFFooter from "@/components/pdf/PDFFooter"
import PDFHeader from "@/components/pdf/PDFHeader"
import PDFKpiGrid from "@/components/pdf/PDFKpiGrid"
import PDFTable from "@/components/pdf/PDFTable"
import { PDF_COLORS, PDF_FONTS } from "@/lib/pdfTheme"
import type { PorPaisPDFPayload } from "@/types"

const styles = StyleSheet.create({
    page: {
        paddingTop: 28,
        paddingBottom: 32,
        paddingHorizontal: 28,
        backgroundColor: PDF_COLORS.background,
        color: PDF_COLORS.text,
        fontSize: PDF_FONTS.body,
    },
})

export default function PorPaisPDF({ data }: { data: PorPaisPDFPayload }) {
    return (
        <Document title="Por País">
            <Page size="A4" style={styles.page}>
                <PDFHeader {...data.header} />
                <PDFKpiGrid items={data.kpis} />
                <PDFTable title="Resumen por país" table={data.summary_table} />
                <PDFTable title="Ganados, perdidos y mantenidos" table={data.status_table} />
                <PDFFooter generatedAt={data.header.generated_at} />
            </Page>
        </Document>
    )
}
