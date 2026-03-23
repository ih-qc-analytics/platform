import { NavLink } from "react-router-dom"
import { BarChart2, Users, Globe, FileText } from "lucide-react"
import {
    Sidebar,
    SidebarContent,
    SidebarHeader,
    SidebarMenu,
    SidebarMenuButton,
    SidebarMenuItem,
} from "@/components/ui/sidebar"

const NAV_ITEMS = [
    { path: "/ventas-totales",  label: "Ventas Totales",        icon: <BarChart2 className="size-4" /> },
    { path: "/por-asesor",      label: "Resultados por Asesor", icon: <Users className="size-4" /> },
    { path: "/detalle-asesor",  label: "Detalle por Asesor",    icon: <FileText className="size-4" /> },
    { path: "/por-pais",        label: "Resultado por País",    icon: <Globe className="size-4" /> },
]

export default function AppSidebar() {
    return (
        <Sidebar>
            <SidebarHeader className="px-4 py-4 border-b border-sidebar-border">
                <div className="flex items-center gap-3">
                    <BarChart2 className="size-6 shrink-0" />
                    <span className="font-bold text-base tracking-wide">QC Analytics</span>
                </div>
            </SidebarHeader>
            <SidebarContent className="p-2">
                <SidebarMenu className="gap-1">
                    {NAV_ITEMS.map(item => (
                        <SidebarMenuItem key={item.path}>
                            <NavLink to={item.path}>
                                {({ isActive }) => (
                                    <SidebarMenuButton
                                        isActive={isActive}
                                        size="lg"
                                    >
                                        {item.icon}
                                        <span>{item.label}</span>
                                    </SidebarMenuButton>
                                )}
                            </NavLink>
                        </SidebarMenuItem>
                    ))}
                </SidebarMenu>
            </SidebarContent>
        </Sidebar>
    )
}