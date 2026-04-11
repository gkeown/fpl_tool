import { Outlet, NavLink, useLocation } from "react-router-dom";
import {
  LayoutDashboard, Users, UserSearch, Calendar, ArrowLeftRight,
  TrendingUp, Settings, Trophy, PanelLeft, Users2, Radio,
} from "lucide-react";
import {
  Sidebar, SidebarContent, SidebarHeader, SidebarFooter,
  SidebarGroup, SidebarGroupContent, SidebarMenu, SidebarMenuItem,
  SidebarMenuButton, SidebarInset, SidebarProvider, SidebarTrigger,
} from "@/components/ui/sidebar";

const NAV_ITEMS = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/team", icon: Users, label: "My Team" },
  { to: "/leagues", icon: Users2, label: "Leagues" },
  { to: "/scores", icon: Radio, label: "Scores" },
  { to: "/players", icon: UserSearch, label: "Players" },
  { to: "/fixtures", icon: Calendar, label: "Fixtures" },
  { to: "/transfers", icon: ArrowLeftRight, label: "Transfers" },
  { to: "/prices", icon: TrendingUp, label: "Prices" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

export default function AppLayout() {
  const location = useLocation();

  return (
    <SidebarProvider>
      <Sidebar collapsible="icon">
        <SidebarHeader className="p-4">
          <NavLink to="/" className="flex items-center gap-2 group-data-[collapsible=icon]:justify-center">
            <Trophy className="h-6 w-6 text-fpl-green shrink-0" />
            <span className="font-display text-lg font-bold text-fpl-green tracking-wider group-data-[collapsible=icon]:hidden">
              FPL COMMAND
            </span>
          </NavLink>
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupContent>
              <SidebarMenu>
                {NAV_ITEMS.map((item) => {
                  const isActive = location.pathname === item.to ||
                    (item.to !== "/" && location.pathname.startsWith(item.to));
                  return (
                    <SidebarMenuItem key={item.to}>
                      <SidebarMenuButton
                        asChild
                        isActive={isActive}
                        tooltip={item.label}
                        className={isActive ? "text-fpl-green bg-fpl-green/10 border-l-2 border-fpl-green" : ""}
                      >
                        <NavLink to={item.to}>
                          <item.icon className="h-4 w-4" />
                          <span>{item.label}</span>
                        </NavLink>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  );
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
        <SidebarFooter className="p-3 group-data-[collapsible=icon]:hidden">
          <p className="text-xs text-muted-foreground text-center">Cmd+B to toggle</p>
        </SidebarFooter>
      </Sidebar>
      <SidebarInset className="bg-pitch-texture">
        <header className="sticky top-0 z-10 flex h-12 items-center gap-2 border-b bg-background/80 backdrop-blur-sm px-4 md:hidden">
          <SidebarTrigger>
            <PanelLeft className="h-5 w-5" />
          </SidebarTrigger>
          <Trophy className="h-5 w-5 text-fpl-green" />
          <span className="font-display text-sm font-bold text-fpl-green tracking-wider">FPL COMMAND</span>
        </header>
        <div className="flex-1 p-4 md:p-6 lg:p-8 max-w-[1400px]">
          <Outlet />
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
