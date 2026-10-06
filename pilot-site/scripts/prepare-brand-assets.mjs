import sharp from "sharp";
import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const master = new URL("../public/brand/orakt-icon-master.png", import.meta.url);
await Promise.all([
  sharp(fileURLToPath(master)).resize(384, 384).webp({ quality: 90 }).toFile("public/brand/orakt-icon.webp"),
  sharp(fileURLToPath(master)).resize(64, 64).png().toFile("public/brand/favicon-64.png"),
  sharp(fileURLToPath(master)).resize(180, 180).flatten({ background: "#080711" }).png().toFile("public/brand/apple-touch-icon.png"),
]);

// Natural Earth 1:110m land, public domain. This is a decorative sampling of
// real geographic polygons, not a source of current geopolitical boundaries.
const land = JSON.parse(await readFile(".tmp/world-land.geojson", "utf8"));
const polygons = land.features.flatMap(({ geometry }) => geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates);
const contains = (x, y, ring) => {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [ax, ay] = ring[i], [bx, by] = ring[j];
    if (((ay > y) !== (by > y)) && x < (bx - ax) * (y - ay) / (by - ay) + ax) inside = !inside;
  }
  return inside;
};
const points = [];
for (let lat = -56; lat < 80; lat += 2.6) {
  const step = 2.6 / Math.cos(lat * Math.PI / 180);
  for (let lon = -180; lon < 180; lon += step) {
    if (polygons.some(rings => contains(lon, lat, rings[0]) && !rings.slice(1).some(ring => contains(lon, lat, ring)))) points.push([+lon.toFixed(2), +lat.toFixed(2)]);
  }
}
await writeFile("public/brand/world-land-points.json", JSON.stringify(points));
console.log(`Prepared icon sizes and ${points.length} geographic land points.`);
