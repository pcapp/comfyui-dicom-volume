declare module "*/scripts/app.js" {
  export const app: { registerExtension(extension: { name: string; nodeCreated(node: import("./extension").HostNode): void }): void };
}
declare module "*/scripts/api.js" {
  export const api: { fetchApi(route: string, options?: RequestInit): Promise<Response> };
}
declare module "*.css?inline" { const css: string; export default css; }
