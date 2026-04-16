import { Outlet, NavLink, useLocation, useNavigate } from "react-router-dom";
import {
  LayoutDashboard, Users, UserSearch, Calendar, ArrowLeftRight,
  TrendingUp, Settings, Target, PanelLeft, Users2, Radio,
  TableProperties, BarChart3, Activity, LogOut, Wrench,
} from "lucide-react";
import {
  Sidebar, SidebarContent, SidebarHeader, SidebarFooter,
  SidebarGroup, SidebarGroupContent, SidebarMenu, SidebarMenuItem,
  SidebarMenuButton, SidebarInset, SidebarProvider, SidebarTrigger,
} from "@/components/ui/sidebar";
import { isAdmin, getUser, clearAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";

const NAV_ITEMS = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard", adminOnly: false },
  { to: "/team", icon: Users, label: "My Team", adminOnly: false },
  { to: "/live-gw", icon: Activity, label: "Live GW", adminOnly: false },
  { to: "/leagues", icon: Users2, label: "Leagues", adminOnly: false },
  { to: "/players", icon: UserSearch, label: "Players", adminOnly: false },
  { to: "/fixtures", icon: Calendar, label: "Fixtures", adminOnly: true },
  { to: "/transfers", icon: ArrowLeftRight, label: "Transfers", adminOnly: true },
  { to: "/prices", icon: TrendingUp, label: "Prices", adminOnly: true },
  { to: "/scores", icon: Radio, label: "Scores", adminOnly: false },
  { to: "/tables", icon: TableProperties, label: "Tables", adminOnly: false },
  { to: "/stats", icon: BarChart3, label: "Stats", adminOnly: false },
  { to: "/settings", icon: Settings, label: "Settings", adminOnly: true },
  { to: "/setup", icon: Wrench, label: "Setup", adminOnly: false },
];

export default function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const admin = isAdmin();
  const user = getUser();

  const visibleItems = NAV_ITEMS.filter((item) => {
    if (item.adminOnly && !admin) return false;
    // Hide Setup for admin (they use Settings instead)
    if (item.to === "/setup" && admin) return false;
    return true;
  });

  const handleLogout = () => {
    clearAuth();
    navigate("/login");
  };

  return (
    <SidebarProvider>
      <Sidebar collapsible="icon">
        <SidebarHeader className="p-4">
          <NavLink to="/" className="flex items-center gap-2 group-data-[collapsible=icon]:justify-center">
            <Target className="h-6 w-6 text-fpl-green shrink-0" />
            <span className="font-display text-lg font-bold text-fpl-green tracking-wider group-data-[collapsible=icon]:hidden">
              FPL TRACKER
            </span>
          </NavLink>
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupContent>
              <SidebarMenu>
                {visibleItems.map((item) => {
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
        <SidebarFooter className="p-3 group-data-[collapsible=icon]:hidden space-y-2">
          {user && (
            <p className="text-[10px] text-muted-foreground text-center">
              {user.username} ({user.role})
            </p>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={handleLogout}
            className="w-full text-xs text-muted-foreground hover:text-fpl-pink"
          >
            <LogOut className="h-3.5 w-3.5 mr-1" />
            Logout
          </Button>
        </SidebarFooter>
      </Sidebar>
      <SidebarInset className="bg-pitch-texture">
        <header className="sticky top-0 z-10 flex h-12 items-center gap-2 border-b bg-background/80 backdrop-blur-sm px-4 md:hidden">
          <SidebarTrigger>
            <PanelLeft className="h-5 w-5" />
          </SidebarTrigger>
          <Target className="h-5 w-5 text-fpl-green" />
          <span className="font-display text-sm font-bold text-fpl-green tracking-wider">FPL TRACKER</span>
        </header>
        <div className="flex-1 p-4 md:p-6 lg:p-8 max-w-[1400px]">
          <Outlet />
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
