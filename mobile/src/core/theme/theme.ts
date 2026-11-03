import { MD3LightTheme, type MD3Theme } from "react-native-paper";

import { palette } from "@/core/theme/tokens";

export const appTheme: MD3Theme = {
  ...MD3LightTheme,
  roundness: 4,
  colors: {
    ...MD3LightTheme.colors,
    primary: palette.primary,
    onPrimary: palette.white,
    secondary: palette.secondary,
    onSecondary: palette.white,
    background: palette.background,
    surface: palette.surface,
    onSurface: palette.text,
    onSurfaceVariant: palette.muted,
    outline: palette.border,
    error: palette.danger,
  },
};
