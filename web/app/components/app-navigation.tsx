/* eslint-disable @next/next/no-img-element */
import {
  BarChart3,
  Boxes,
  FileText,
  Factory,
  Home,
  History,
  MapPinned,
  MoreHorizontal,
  Package,
  Settings,
  ShoppingBag,
  Trash2,
  Users,
  WalletCards,
} from "lucide-react";
import { bridgeUrl } from "../lib/hustlenest";
import type { WorkspaceView } from "../lib/hustlenest";

type NavigationItem = {
  label: string;
  icon: typeof Home;
  view?: WorkspaceView;
  count?: number;
};

export function AppNavigation({
  activeView,
  onNavigate,
  orderCount,
  customerCount,
  productCount,
  materialCount,
  vendorCount,
  expenseCount,
  businessName,
  showBusinessName,
  logoAvailable,
  brandingRevision,
  profileName,
  profileRole,
  profileInitials,
  profileAvatarAvailable,
}: {
  activeView: WorkspaceView;
  onNavigate: (view: WorkspaceView) => void;
  orderCount: number;
  customerCount: number;
  productCount: number;
  materialCount: number;
  vendorCount: number;
  expenseCount: number;
  businessName?: string;
  showBusinessName?: boolean;
  logoAvailable?: boolean;
  brandingRevision?: string;
  profileName?: string;
  profileRole?: string;
  profileInitials?: string;
  profileAvatarAvailable?: boolean;
}) {
  const groups: Array<{ label: string; items: NavigationItem[] }> = [
    {
      label: "Workspace",
      items: [
        { label: "Home", icon: Home, view: "home" },
        { label: "Orders", icon: ShoppingBag, view: "orders", count: orderCount },
        { label: "Customers", icon: Users, view: "customers", count: customerCount },
      ],
    },
    {
      label: "Business",
      items: [
        { label: "Products", icon: Package, view: "products", count: productCount },
        { label: "Materials", icon: Boxes, view: "materials", count: materialCount },
        { label: "Vendors", icon: Factory, view: "vendors", count: vendorCount },
        { label: "Finance", icon: WalletCards, view: "finance", count: expenseCount },
      ],
    },
    {
      label: "Understand",
      items: [
        { label: "Reports", icon: BarChart3, view: "reports" },
        { label: "History", icon: History, view: "history" },
        { label: "Geography", icon: MapPinned, view: "geography" },
        { label: "Documents", icon: FileText, view: "documents" },
        { label: "Trash", icon: Trash2, view: "trash" },
      ],
    },
  ];

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className={`brand-mark${logoAvailable ? " has-logo" : ""}`}>{logoAvailable ? <img src={`${bridgeUrl}/api/settings/logo?v=${brandingRevision ?? "current"}`} alt="" /> : "HN"}</div>
        <div><strong>{showBusinessName && businessName ? businessName : "HustleNest"}</strong><span>{showBusinessName && businessName ? "HustleNest workspace" : "Business workspace"}</span></div>
      </div>
      <nav aria-label="Main navigation">
        {groups.map((group) => (
          <div className="nav-group" key={group.label}>
            <p>{group.label}</p>
            {group.items.map((item) => {
              const Icon = item.icon;
              const active = item.view === activeView;
              return (
                <button
                  className={active ? "nav-item active" : "nav-item"}
                  key={item.label}
                  onClick={() => item.view && onNavigate(item.view)}
                  aria-current={active ? "page" : undefined}
                >
                  <Icon size={18} strokeWidth={1.9} />
                  <span>{item.label}</span>
                  {item.count !== undefined ? <em>{item.count}</em> : null}
                </button>
              );
            })}
          </div>
        ))}
      </nav>
      <div className="sidebar-footer">
        <button className={activeView === "settings" ? "nav-item active" : "nav-item"} onClick={() => onNavigate("settings")} aria-current={activeView === "settings" ? "page" : undefined}><Settings size={18} /><span>Settings</span></button>
        <button className="profile profile-button" onClick={() => onNavigate("settings")} aria-label="Edit owner profile">
          <div className={`avatar avatar-owner${profileAvatarAvailable ? " has-photo" : ""}`}>{profileAvatarAvailable ? <img src={`${bridgeUrl}/api/settings/profile/avatar?v=${brandingRevision ?? "current"}`} alt="" /> : profileInitials || "?"}</div>
          <div><strong>{profileName || "Owner"}</strong><span>{profileRole || "Owner"}</span></div>
          <MoreHorizontal size={18} />
        </button>
      </div>
    </aside>
  );
}
