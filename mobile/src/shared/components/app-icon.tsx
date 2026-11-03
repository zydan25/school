import type { LucideIcon } from "lucide-react-native";

type AppIconProps = {
  icon: LucideIcon;
  size?: number;
  color?: string;
  strokeWidth?: number;
};

export function AppIcon({
  icon: Icon,
  size = 22,
  color = "#203B60",
  strokeWidth = 1.9,
}: AppIconProps) {
  return <Icon size={size} color={color} strokeWidth={strokeWidth} />;
}
