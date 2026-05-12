import { StyleSheet, Text, View } from "@react-pdf/renderer"

import { PDF_COLORS, PDF_FONTS } from "@/lib/pdfTheme"

const styles = StyleSheet.create({
    footer: {
        position: "absolute",
        left: 28,
        right: 28,
        bottom: 16,
        flexDirection: "row",
        justifyContent: "space-between",
        fontSize: PDF_FONTS.footer,
        color: PDF_COLORS.muted,
    },
})

export default function PDFFooter({ generatedAt }: { generatedAt: string }) {
    return (
        <View style={styles.footer} fixed>
            <Text>Reporte Confidencial - Sistema QC</Text>
            <Text
                render={({ pageNumber, totalPages }: { pageNumber: number; totalPages: number }) =>
                    `Página ${pageNumber} de ${totalPages}`
                }
            />
            <Text>{generatedAt}</Text>
        </View>
    )
}
