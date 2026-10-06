import sharp from "sharp";
// Raster fallback for iOS home-screen icons, rendered from the line-mark source.
await sharp("public/brand/orakt-line.svg").resize(180,180).png().toFile("public/brand/apple-touch-line.png");
