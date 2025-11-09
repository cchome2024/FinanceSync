/* eslint-disable */
import * as Router from 'expo-router';

export * from 'expo-router';

declare module 'expo-router' {
  export namespace ExpoRouter {
    export interface __routes<T extends string = string> extends Record<string, unknown> {
      StaticRoutes: `/` | `/(app)` | `/(app)/ai-chat` | `/(app)/analysis` | `/(app)/dashboard` | `/(app)/dashboard/history` | `/(app)/history` | `/_sitemap` | `/ai-chat` | `/analysis` | `/dashboard` | `/dashboard/history` | `/history`;
      DynamicRoutes: never;
      DynamicRouteTemplate: never;
    }
  }
}
