import { Platform } from "obsidian";

export type RuntimePlatform =
  | "ios"
  | "android"
  | "macos"
  | "windows"
  | "linux"
  | "other";

export function detectRuntimePlatform(): RuntimePlatform {
  if (Platform.isIosApp) return "ios";
  if (Platform.isAndroidApp) return "android";
  if (Platform.isMacOS) return "macos";
  if (Platform.isWin) return "windows";
  if (Platform.isLinux) return "linux";
  return "other";
}

export function isMobileRuntime(): boolean {
  return Platform.isMobile;
}
