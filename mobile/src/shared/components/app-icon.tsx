import type { LucideIcon } from "lucide-react-native";
import { palette } from "@/core/theme/tokens";

type AppIconProps = {
  icon: LucideIcon;
  size?: number;
  color?: string;
  strokeWidth?: number;
};

export function AppIcon({
  icon: Icon,
  size = 22,
  color = palette.primary,
  strokeWidth = 1.9,
}: AppIconProps) {
  return <Icon size={size} color={color} strokeWidth={strokeWidth} />;
}
