import { Image, StyleSheet, Text, View } from "@react-pdf/renderer"

import logo from "@/images/logo.png"
import { PDF_COLORS, PDF_FONTS } from "@/lib/pdfTheme"
import type { PDFHeader as PDFHeaderType } from "@/types"

const styles = StyleSheet.create({
    container: {
        marginBottom: 18,
        padding: 16,
        borderRadius: 12,
        backgroundColor: PDF_COLORS.rowAlt,
        border: `1 solid ${PDF_COLORS.border}`,
    },
    topRow: {
        flexDirection: "row",
        justifyContent: "space-between",
        alignItems: "flex-start",
        gap: 12,
    },
    titleGroup: {
        flex: 1,
        gap: 4,
    },
    logo: {
        width: 74,
        height: 74,
        objectFit: "contain",
    },
    title: {
        fontSize: PDF_FONTS.title,
        color: PDF_COLORS.primary,
        fontWeight: 700,
    },
    subtitle: {
        fontSize: PDF_FONTS.body,
        color: PDF_COLORS.text,
    },
    generatedAt: {
        marginTop: 6,
        fontSize: PDF_FONTS.body,
        color: PDF_COLORS.muted,
    },
    filtersWrap: {
        marginTop: 12,
        flexDirection: "row",
        flexWrap: "wrap",
        gap: 8,
    },
    filterPill: {
        paddingHorizontal: 8,
        paddingVertical: 5,
        borderRadius: 999,
        backgroundColor: PDF_COLORS.white,
        border: `1 solid ${PDF_COLORS.border}`,
    },
    filterText: {
        fontSize: PDF_FONTS.filterTag,
        color: PDF_COLORS.text,
    },
})

export default function PDFHeader({ title, subtitle, generated_at, filters_summary }: PDFHeaderType) {
    const filters = Object.entries(filters_summary)

    return (
        <View style={styles.container}>
            <View style={styles.topRow}>
                <View style={styles.titleGroup}>
                    <Text style={styles.title}>{title}</Text>
                    <Text style={styles.subtitle}>{subtitle}</Text>
                    <Text style={styles.generatedAt}>Generado: {generated_at}</Text>
                </View>
                <Image src={logo} style={styles.logo} />
            </View>
            <View style={styles.filtersWrap}>
                {filters.length > 0 ? (
                    filters.map(([label, value]) => (
                        <View key={label} style={styles.filterPill}>
                            <Text style={styles.filterText}>
                                {label}: {value}
                            </Text>
                        </View>
                    ))
                ) : (
                    <View style={styles.filterPill}>
                        <Text style={styles.filterText}>Sin filtros geográficos adicionales</Text>
                    </View>
                )}
            </View>
        </View>
    )
}
