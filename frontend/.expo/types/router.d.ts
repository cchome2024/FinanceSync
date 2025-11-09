/* eslint-disable */
import * as Router from 'expo-router';

export * from 'expo-router';

declare module 'expo-router' {
  export namespace ExpoRouter {
    export interface __routes<T extends string = string> extends Record<string, unknown> {
      StaticRoutes: `/` | `/(app)` | `/(app)/ai-chat` | `/(app)/history` | `/(app)\analysis\` | `/_sitemap` | `/ai-chat` | `/history`;
      DynamicRoutes: never;
      DynamicRouteTemplate: never;
    }
  }
}
