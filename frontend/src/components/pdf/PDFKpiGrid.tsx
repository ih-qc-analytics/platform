import { StyleSheet, Text, View } from "@react-pdf/renderer"

import { PDF_COLORS, PDF_FONTS } from "@/lib/pdfTheme"
import type { PDFKpiItem } from "@/types"

const styles = StyleSheet.create({
    section: {
        marginBottom: 18,
    },
    sectionTitle: {
        marginBottom: 10,
        fontSize: PDF_FONTS.sectionHeader,
        color: PDF_COLORS.primary,
        fontWeight: 700,
    },
    grid: {
        flexDirection: "row",
        flexWrap: "wrap",
        gap: 10,
    },
    card: {
        width: "31%",
        minHeight: 70,
        padding: 10,
        borderRadius: 10,
        backgroundColor: PDF_COLORS.white,
        border: `1 solid ${PDF_COLORS.border}`,
    },
    label: {
        fontSize: PDF_FONTS.kpiLabel,
        color: PDF_COLORS.muted,
        marginBottom: 6,
    },
    value: {
        fontSize: PDF_FONTS.kpi,
        color: PDF_COLORS.text,
        fontWeight: 700,
    },
    growth: {
        marginTop: 4,
        fontSize: PDF_FONTS.body,
    },
})

export default function PDFKpiGrid({ items }: { items: PDFKpiItem[] }) {
    return (
        <View style={styles.section}>
            <Text style={styles.sectionTitle}>Indicadores principales</Text>
            <View style={styles.grid}>
                {items.map((item) => (
                    <View key={item.label} style={styles.card}>
                        <Text style={styles.label}>{item.label}</Text>
                        <Text style={styles.value}>{item.value}</Text>
                        {item.growth ? (
                            <Text
                                style={{
                                    ...styles.growth,
                                    color: item.growth_positive ? PDF_COLORS.success : PDF_COLORS.destructive,
                                }}
                            >
                                Variación: {item.growth}
                            </Text>
                        ) : null}
                    </View>
                ))}
            </View>
        </View>
    )
}
