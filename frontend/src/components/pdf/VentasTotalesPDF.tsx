import { Document, Page, StyleSheet, Text, View } from "@react-pdf/renderer"

import PDFCharts from "@/components/pdf/PDFCharts"
import PDFFooter from "@/components/pdf/PDFFooter"
import PDFHeader from "@/components/pdf/PDFHeader"
import PDFKpiGrid from "@/components/pdf/PDFKpiGrid"
import { PDF_COLORS, PDF_FONTS } from "@/lib/pdfTheme"
import type { VentasTotalesPDFPayload } from "@/types"

const styles = StyleSheet.create({
    page: {
        paddingTop: 28,
        paddingBottom: 32,
        paddingHorizontal: 28,
        backgroundColor: PDF_COLORS.background,
        color: PDF_COLORS.text,
        fontSize: PDF_FONTS.body,
    },
    footer: {
        display: "none",
    },
    chartsIntro: {
        marginBottom: 14,
        fontSize: PDF_FONTS.sectionHeader,
        color: PDF_COLORS.primary,
        fontWeight: 700,
    },
})

export default function VentasTotalesPDF({ data }: { data: VentasTotalesPDFPayload }) {
    return (
        <Document title="Ventas Totales">
            <Page size="A4" style={styles.page}>
                <PDFHeader {...data.header} />
                <PDFKpiGrid items={data.kpis} />
                <PDFFooter generatedAt={data.header.generated_at} />
            </Page>
            <Page size="A4" style={styles.page}>
                <Text style={styles.chartsIntro}>Tendencia y distribución geográfica</Text>
                <PDFCharts trendPoints={data.trend_points} geoPoints={data.geo_points} />
                <PDFFooter generatedAt={data.header.generated_at} />
            </Page>
        </Document>
    )
}
