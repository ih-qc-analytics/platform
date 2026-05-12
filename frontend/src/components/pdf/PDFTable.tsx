import { StyleSheet, Text, View } from "@react-pdf/renderer"

import { PDF_COLORS, PDF_FONTS } from "@/lib/pdfTheme"
import type { PDFTable as PDFTableType } from "@/types"

const styles = StyleSheet.create({
    section: {
        marginBottom: 16,
    },
    title: {
        marginBottom: 8,
        fontSize: PDF_FONTS.sectionHeader,
        color: PDF_COLORS.primary,
        fontWeight: 700,
    },
    table: {
        width: "100%",
        borderWidth: 1,
        borderColor: PDF_COLORS.border,
        borderRadius: 8,
        overflow: "hidden",
    },
    row: {
        flexDirection: "row",
    },
    headerRow: {
        backgroundColor: PDF_COLORS.primary,
    },
    bodyRowAlt: {
        backgroundColor: PDF_COLORS.rowAlt,
    },
    cell: {
        paddingHorizontal: 6,
        paddingVertical: 6,
        borderRightWidth: 1,
        borderRightColor: PDF_COLORS.border,
        justifyContent: "center",
    },
    headerText: {
        fontSize: 8,
        fontWeight: 700,
        color: PDF_COLORS.white,
    },
    cellText: {
        fontSize: 7,
        color: PDF_COLORS.text,
    },
    empty: {
        fontSize: PDF_FONTS.body,
        color: PDF_COLORS.muted,
    },
})

export default function PDFTable({ title, table }: { title?: string; table: PDFTableType }) {
    return (
        <View style={styles.section}>
            {title ? <Text style={styles.title}>{title}</Text> : null}
            {table.rows.length === 0 ? (
                <Text style={styles.empty}>Sin datos para los filtros seleccionados.</Text>
            ) : (
                <View style={styles.table}>
                    <View style={[styles.row, styles.headerRow]}>
                        {table.headers.map((header, index) => (
                            <View
                                key={`${header}-${index}`}
                                style={{ ...styles.cell, flex: table.column_widths[index] ?? 1 }}
                            >
                                <Text style={styles.headerText}>{header}</Text>
                            </View>
                        ))}
                    </View>
                    {table.rows.map((row, rowIndex) => (
                        <View
                            key={`${rowIndex}-${row.cells[0] ?? "row"}`}
                            style={rowIndex % 2 === 1 ? [styles.row, styles.bodyRowAlt] : styles.row}
                        >
                            {row.cells.map((cell, cellIndex) => (
                                <View
                                    key={`${rowIndex}-${cellIndex}`}
                                    style={{ ...styles.cell, flex: table.column_widths[cellIndex] ?? 1 }}
                                >
                                    <Text style={styles.cellText}>{cell}</Text>
                                </View>
                            ))}
                        </View>
                    ))}
                </View>
            )}
        </View>
    )
}
