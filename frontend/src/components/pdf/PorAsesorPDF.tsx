import { Document, Page, StyleSheet } from "@react-pdf/renderer"

import PDFFooter from "@/components/pdf/PDFFooter"
import PDFHeader from "@/components/pdf/PDFHeader"
import PDFKpiGrid from "@/components/pdf/PDFKpiGrid"
import PDFTable from "@/components/pdf/PDFTable"
import { PDF_COLORS, PDF_FONTS } from "@/lib/pdfTheme"
import type { PorAsesorPDFPayload } from "@/types"

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

export default function PorAsesorPDF({ data }: { data: PorAsesorPDFPayload }) {
    return (
        <Document title="Por Asesor">
            <Page size="A4" style={styles.page}>
                <PDFHeader {...data.header} />
                <PDFKpiGrid items={data.kpis} />
                <PDFTable title="Resultados por asesor" table={data.table} />
                <PDFFooter generatedAt={data.header.generated_at} />
            </Page>
        </Document>
    )
}
