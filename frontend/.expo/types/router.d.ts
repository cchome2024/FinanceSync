/* eslint-disable */
import * as Router from 'expo-router';

export * from 'expo-router';

declare module 'expo-router' {
  export namespace ExpoRouter {
    export interface __routes<T extends string = string> extends Record<string, unknown> {
      StaticRoutes: `/` | `/(app)` | `/(app)/ai-chat` | `/(app)/analysis` | `/(app)/dashboard` | `/(app)/dashboard/history` | `/(app)/history` | `/(app)/import` | `/(app)/import/panels/AIImportPanel` | `/(app)/import/panels/APIImportPanel` | `/(app)/import/panels/FileImportPanel` | `/_sitemap` | `/ai-chat` | `/analysis` | `/dashboard` | `/dashboard/history` | `/history` | `/import` | `/import/panels/AIImportPanel` | `/import/panels/APIImportPanel` | `/import/panels/FileImportPanel` | `/login`;
      DynamicRoutes: never;
      DynamicRouteTemplate: never;
    }
  }
}
