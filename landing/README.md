# Kage landing page

Renders ThreeUI's `<KageLandingPage />` (`@designcodeio/threeui@1.2.0`) with the configured typography and color props in `src/Scene.tsx`.

```bash
cd landing
npm install
npm run dev            # http://localhost:5173
npm run build          # type-check + production build to dist/
npm run verify-assets  # SHA-256 check of public/landing-pages against assets.sha256
```

The component loads `/landing-pages/kage.html` in an iframe and injects the typography/color overrides into it. `public/landing-pages/` holds the canonical HTML, the Three.js runtime, fonts and images, copied byte-for-byte from the npm package's `lib-dist/assets/landing-pages/`.
