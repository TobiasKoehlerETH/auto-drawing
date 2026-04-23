// Minimal shim so TypeScript accepts the deep import into opencascade.js.
// The real surface is the entire OCCT API — we use `any` at the call sites.
declare module "opencascade.js/dist/opencascade.wasm.js" {
  const factory: (opts: { locateFile: (p: string) => string }) => Promise<unknown>;
  export default factory;
}
