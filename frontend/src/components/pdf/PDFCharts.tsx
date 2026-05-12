import { StyleSheet, Text, View } from "@react-pdf/renderer"

import { PDF_COLORS, PDF_FONTS } from "@/lib/pdfTheme"
import type { PDFGeoPoint, PDFTrendPoint } from "@/types"

const TREND_BAR_HEIGHT = 160
const GEO_BAR_WIDTH = 470

const styles = StyleSheet.create({
    chartsColumn: {
        gap: 16,
    },
    panel: {
        width: "100%",
        padding: 16,
        borderRadius: 12,
        backgroundColor: PDF_COLORS.white,
        border: `1 solid ${PDF_COLORS.border}`,
    },
    panelTitle: {
        marginBottom: 10,
        fontSize: PDF_FONTS.sectionHeader,
        color: PDF_COLORS.primary,
        fontWeight: 700,
    },
    empty: {
        fontSize: PDF_FONTS.body,
        color: PDF_COLORS.muted,
    },
    trendArea: {
        flexDirection: "row",
        alignItems: "flex-end",
        justifyContent: "space-between",
        minHeight: 220,
        gap: 10,
    },
    trendColumn: {
        flex: 1,
        alignItems: "center",
        gap: 4,
    },
    trendValue: {
        fontSize: 8,
        color: PDF_COLORS.muted,
        textAlign: "center",
    },
    trendBarWrap: {
        width: "100%",
        height: TREND_BAR_HEIGHT,
        justifyContent: "flex-end",
        alignItems: "center",
    },
    trendBar: {
        width: 26,
        minHeight: 2,
        borderRadius: 6,
        backgroundColor: PDF_COLORS.primaryLight,
    },
    trendLabel: {
        fontSize: 8,
        color: PDF_COLORS.text,
        textAlign: "center",
    },
    geoList: {
        gap: 10,
    },
    geoRow: {
        gap: 4,
    },
    geoTop: {
        flexDirection: "row",
        justifyContent: "space-between",
        gap: 8,
    },
    geoLabel: {
        fontSize: PDF_FONTS.body,
        color: PDF_COLORS.text,
    },
    geoValue: {
        fontSize: PDF_FONTS.body,
        color: PDF_COLORS.muted,
    },
    geoTrack: {
        width: GEO_BAR_WIDTH,
        maxWidth: "100%",
        height: 14,
        borderRadius: 999,
        backgroundColor: PDF_COLORS.background,
    },
    geoFill: {
        height: 14,
        borderRadius: 999,
        backgroundColor: PDF_COLORS.primary,
    },
})

const formatCompactCurrency = (value: number) => {
    if (Math.abs(value) >= 1000) {
        const scaled = value / 1000
        const decimals = Math.abs(scaled) >= 100 ? 0 : 1
        return `$${scaled.toFixed(decimals)}k`
    }
    return `$${value.toFixed(0)}`
}

export default function PDFCharts({
    trendPoints,
    geoPoints,
}: {
    trendPoints: PDFTrendPoint[]
    geoPoints: PDFGeoPoint[]
}) {
    return (
        <View style={styles.chartsColumn}>
            <View style={styles.panel}>
                <Text style={styles.panelTitle}>Tendencia</Text>
                {trendPoints.length === 0 ? (
                    <Text style={styles.empty}>Sin datos para el período seleccionado.</Text>
                ) : (
                    <View style={styles.trendArea}>
                        {trendPoints.map((point) => (
                            <View key={point.label} style={styles.trendColumn}>
                                <Text style={styles.trendValue}>{formatCompactCurrency(point.value)}</Text>
                                <View style={styles.trendBarWrap}>
                                    <View style={{ ...styles.trendBar, height: Math.max(point.scaled * TREND_BAR_HEIGHT, 2) }} />
                                </View>
                                <Text style={styles.trendLabel}>{point.label}</Text>
                            </View>
                        ))}
                    </View>
                )}
            </View>
            <View style={styles.panel}>
                <Text style={styles.panelTitle}>Distribución geográfica</Text>
                {geoPoints.length === 0 ? (
                    <Text style={styles.empty}>Sin datos para el período seleccionado.</Text>
                ) : (
                    <View style={styles.geoList}>
                        {geoPoints.map((point) => (
                            <View key={point.label} style={styles.geoRow}>
                                <View style={styles.geoTop}>
                                    <Text style={styles.geoLabel}>{point.label}</Text>
                                    <Text style={styles.geoValue}>{formatCompactCurrency(point.value)}</Text>
                                </View>
                                <View style={styles.geoTrack}>
                                    <View
                                        style={{
                                            ...styles.geoFill,
                                            width: Math.max(point.scaled * GEO_BAR_WIDTH, 4),
                                        }}
                                    />
                                </View>
                            </View>
                        ))}
                    </View>
                )}
            </View>
        </View>
    )
}
