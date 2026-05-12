import { Document, Page, StyleSheet } from "@react-pdf/renderer"

import PDFFooter from "@/components/pdf/PDFFooter"
import PDFHeader from "@/components/pdf/PDFHeader"
import PDFKpiGrid from "@/components/pdf/PDFKpiGrid"
import PDFTable from "@/components/pdf/PDFTable"
import { PDF_COLORS, PDF_FONTS } from "@/lib/pdfTheme"
import type { PDFKpiItem, PorPaisDetailPDFPayload } from "@/types"

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

export default function PorPaisDetailPDF({ data }: { data: PorPaisDetailPDFPayload }) {
    const familyKpis = buildFamilyKpis(data)

    return (
        <Document title={data.header.title}>
            <Page size="A4" style={styles.page}>
                <PDFHeader {...data.header} />
                <PDFKpiGrid items={familyKpis} />
                <PDFTable title="Desglose por examen" table={data.detail_table} />
                <PDFFooter generatedAt={data.header.generated_at} />
            </Page>
        </Document>
    )
}

function buildFamilyKpis(data: PorPaisDetailPDFPayload): PDFKpiItem[] {
    const counts = new Map(data.detail_table.rows.map(row => [row.cells[0], Number(row.cells[1].replace(/,/g, "")) || 0]))
    const cambridge = data.detail_table.rows.reduce((sum, row) => {
        const examName = row.cells[0]
        const value = Number(row.cells[1].replace(/,/g, "")) || 0
        return ["IELTS", "MET", "MET Go!", "TEA", "Other"].includes(examName) ? sum : sum + value
    }, 0)
    const ielts = counts.get("IELTS") ?? 0
    const met = (counts.get("MET") ?? 0) + (counts.get("MET Go!") ?? 0)
    const tea = counts.get("TEA") ?? 0
    const otros = counts.get("Other") ?? 0
    const total = data.detail_table.rows.reduce((sum, row) => sum + (Number(row.cells[1].replace(/,/g, "")) || 0), 0)

    return [
        { label: "Cambridge", value: String(cambridge) },
        { label: "IELTS", value: String(ielts) },
        { label: "MET", value: String(met) },
        { label: "TEA", value: String(tea) },
        { label: "Otros", value: String(otros) },
        { label: "Total", value: String(total) },
    ]
}
