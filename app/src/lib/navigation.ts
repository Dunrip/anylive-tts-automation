export type NavItem = {
  id: string;
  label: string;
  icon: string;
  panel: PanelType;
};

export type PanelType = "tts" | "faq" | "scripts" | "history" | "settings";

export const NAV_ITEMS: NavItem[] = [
  { id: "tts", label: "TTS", icon: "🎙️", panel: "tts" },
  { id: "faq", label: "FAQ", icon: "❓", panel: "faq" },
  { id: "scripts", label: "Scripts", icon: "📜", panel: "scripts" },
  { id: "history", label: "History", icon: "📊", panel: "history" },
  { id: "settings", label: "Settings", icon: "⚙️", panel: "settings" },
];
