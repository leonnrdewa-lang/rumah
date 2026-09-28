using System.Collections.Generic;
using UnityEngine;

namespace OjolRush
{
    /// <summary>
    /// Builds the static district as chunky low-poly meshes: streets, markings, sidewalks, ruko
    /// shophouses with warung signs and awnings, water tanks, tangled overhead cables, spanduk
    /// banners, trees and the gang alleys. Geometry is batched per 60 m chunk so it culls well.
    /// </summary>
    public class CityBuilder
    {
        readonly CityMap city;
        readonly System.Random rng;
        readonly Transform root;
        readonly Dictionary<long, MeshBatcher> chunks = new Dictionary<long, MeshBatcher>();
        readonly Dictionary<long, MeshBatcher> flatChunks = new Dictionary<long, MeshBatcher>();

        static readonly Color Asphalt = new Color(0.26f, 0.26f, 0.29f);
        static readonly Color AsphaltJunction = new Color(0.28f, 0.28f, 0.3f);
        static readonly Color Sidewalk = new Color(0.74f, 0.71f, 0.66f);
        static readonly Color Curb = new Color(0.55f, 0.53f, 0.5f);
        static readonly Color Marking = new Color(0.95f, 0.95f, 0.9f);
        static readonly Color Ground = new Color(0.52f, 0.48f, 0.42f);
        static readonly Color GangFloor = new Color(0.63f, 0.58f, 0.5f);
        static readonly Color Cable = new Color(0.1f, 0.1f, 0.1f);
        static readonly Color PoleColor = new Color(0.45f, 0.42f, 0.38f);

        static readonly Color[] Walls =
        {
            new Color(0.96f, 0.84f, 0.6f), new Color(0.62f, 0.82f, 0.72f), new Color(0.93f, 0.62f, 0.5f),
            new Color(0.95f, 0.94f, 0.86f), new Color(0.72f, 0.76f, 0.92f), new Color(0.88f, 0.58f, 0.64f),
            new Color(0.98f, 0.9f, 0.45f), new Color(0.7f, 0.88f, 0.55f), new Color(0.85f, 0.75f, 0.65f),
            new Color(0.6f, 0.75f, 0.85f),
        };
        static readonly Color[] Roofs =
        {
            new Color(0.72f, 0.36f, 0.22f), new Color(0.55f, 0.3f, 0.2f), new Color(0.45f, 0.47f, 0.5f),
            new Color(0.3f, 0.45f, 0.55f), new Color(0.8f, 0.42f, 0.25f),
        };
        static readonly Color[] SignColors =
        {
            new Color(0.9f, 0.15f, 0.15f), new Color(0.1f, 0.45f, 0.85f), new Color(0.95f, 0.8f, 0.1f),
            new Color(0.15f, 0.65f, 0.3f), new Color(0.95f, 0.45f, 0.1f), new Color(0.55f, 0.2f, 0.65f),
        };
        static readonly string[] SignTexts =
        {
            "WARTEG", "BAKSO", "PULSA", "LAUNDRY", "NASI PADANG", "BENGKEL", "FOTOKOPI", "KOPI", "SEMBAKO",
            "MARTABAK", "SATE", "SOTO", "APOTEK", "SALON", "MIE AYAM", "SERVIS HP", "JAMU", "TOKO EMAS",
        };
        static readonly string[] BannerTexts =
        {
            "SELAMAT DATANG", "PROMO PULSA 10RB", "LOMBA 17-AN RW 05", "HATI-HATI BANYAK ANAK",
            "DIJUAL CEPAT TANPA PERANTARA", "PENGAJIAN MALAM JUMAT", "DISKON 50% (SYARAT BERLAKU)",
        };

        public CityBuilder(CityMap city, System.Random rng, Transform parent)
        {
            this.city = city;
            this.rng = rng;
            root = new GameObject("City").transform;
            root.SetParent(parent, false);
        }

        float R(float a, float b) { return a + (float)rng.NextDouble() * (b - a); }

        MeshBatcher Chunk(Vector3 p, bool flat = false)
        {
            long key = ((long)Mathf.FloorToInt(p.x / 60f) << 32) ^ (uint)Mathf.FloorToInt(p.z / 60f);
            Dictionary<long, MeshBatcher> dict = flat ? flatChunks : chunks;
            MeshBatcher mb;
            if (!dict.TryGetValue(key, out mb))
            {
                mb = new MeshBatcher();
                dict[key] = mb;
            }
            return mb;
        }

        public void Build()
        {
            BuildGround();
            BuildStreets();
            BuildGangFloors();
            for (int bi = 0; bi < city.nx - 1; bi++)
                for (int bj = 0; bj < city.nz - 1; bj++)
                    BuildBlock(bi, bj);
            BuildOuterRing();
            BuildPolesAndCables();
            BuildBanners();
            BuildTrees();

            foreach (KeyValuePair<long, MeshBatcher> kv in flatChunks)
                if (!kv.Value.IsEmpty) kv.Value.BuildObject("Ground", root, false).GetComponent<Renderer>().receiveShadows = true;
            foreach (KeyValuePair<long, MeshBatcher> kv in chunks)
                if (!kv.Value.IsEmpty) kv.Value.BuildObject("Chunk", root, true);
        }

        void BuildGround()
        {
            MeshBatcher mb = new MeshBatcher();
            Vector2 c = city.Center;
            mb.Box(new Vector3(c.x, -0.15f, c.y), new Vector3(city.MaxX - city.MinX + 200f, 0.3f, city.MaxZ - city.MinZ + 200f), Quaternion.identity, Ground);
            mb.BuildObject("BaseGround", root, false);
        }

        // ------------------------------------------------------------------ streets

        void BuildStreets()
        {
            float P = CityMap.Pitch;
            for (int i = 0; i < city.nx; i++)
            {
                for (int j = 0; j < city.nz; j++)
                {
                    Vector2 n = city.NodePos(i, j);
                    Vector3 n3 = Geo.X0Z(n);
                    // Junction asphalt + corner sidewalks.
                    // Cross-shaped junction: each street's asphalt runs through the other's sidewalk strip.
                    Chunk(n3, true).Box(n3, new Vector3(CityMap.CorridorHalf * 2f, 0.02f, CityMap.RoadHalf * 2f), Quaternion.identity, AsphaltJunction);
                    Chunk(n3, true).Box(n3, new Vector3(CityMap.RoadHalf * 2f, 0.02f, CityMap.CorridorHalf * 2f), Quaternion.identity, AsphaltJunction);
                    for (int cx = -1; cx <= 1; cx += 2)
                        for (int cz = -1; cz <= 1; cz += 2)
                        {
                            Vector3 cp = n3 + new Vector3(cx * (CityMap.RoadHalf + 1.5f), CityMap.SidewalkHeight * 0.5f, cz * (CityMap.RoadHalf + 1.5f));
                            Chunk(cp, true).Box(cp, new Vector3(3f, CityMap.SidewalkHeight, 3f), Quaternion.identity, Sidewalk);
                        }
                    // Edge stubs where the grid ends (junction mouths onto the map border).
                    for (int d = 0; d < 4; d++)
                    {
                        if (city.HasEdge(i, j, d)) continue;
                        Vector2 dir = CityMap.Dirs[d];
                        Vector3 sp = Geo.X0Z(n + dir * (CityMap.RoadHalf + 1.5f), CityMap.SidewalkHeight * 0.5f);
                        Vector3 size = CityMap.IsHorizontal(d) ? new Vector3(3f, CityMap.SidewalkHeight, CityMap.RoadHalf * 2f) : new Vector3(CityMap.RoadHalf * 2f, CityMap.SidewalkHeight, 3f);
                        Chunk(sp, true).Box(sp, size, Quaternion.identity, Sidewalk);
                    }
                    // Segments to the east and north.
                    for (int d = 0; d < 2; d++)
                    {
                        if (!city.HasEdge(i, j, d)) continue;
                        Vector2 dir = CityMap.Dirs[d];
                        Vector2 left = Geo.Left(dir);
                        Vector2 mid = n + dir * (P * 0.5f);
                        Quaternion rot = Quaternion.Euler(0, Geo.Heading(dir), 0);
                        float len = CityMap.EdgeLength;
                        Vector3 m3 = Geo.X0Z(mid);
                        MeshBatcher f = Chunk(m3, true);
                        f.Box(m3, new Vector3(CityMap.RoadHalf * 2f, 0.02f, len + 0.02f), rot, Asphalt);
                        for (int s = -1; s <= 1; s += 2)
                        {
                            Vector3 sw = Geo.X0Z(mid + left * s * (CityMap.RoadHalf + 1.5f), CityMap.SidewalkHeight * 0.5f);
                            f.Box(sw, new Vector3(3f, CityMap.SidewalkHeight, len), rot, Sidewalk);
                            Vector3 cb = Geo.X0Z(mid + left * s * (CityMap.RoadHalf + 0.12f), CityMap.SidewalkHeight * 0.5f + 0.01f);
                            f.Box(cb, new Vector3(0.24f, CityMap.SidewalkHeight + 0.02f, len), rot, Curb);
                        }
                        // Centre line + dashed lane lines.
                        f.Box(Geo.X0Z(mid, 0.012f), new Vector3(0.16f, 0.02f, len - 7f), rot, Marking);
                        for (int s = -1; s <= 1; s += 2)
                        {
                            for (float u = -len * 0.5f + 5f; u < len * 0.5f - 5f; u += 5f)
                            {
                                Vector2 p = mid + dir * (u + 1f) + left * s * CityMap.LaneWidth;
                                f.Box(Geo.X0Z(p, 0.012f), new Vector3(0.14f, 0.02f, 2f), rot, Marking);
                            }
                        }
                        // Zebra crossings and stop lines at both ends.
                        for (int e = -1; e <= 1; e += 2)
                        {
                            Vector2 z = mid + dir * e * (len * 0.5f - 1.5f);
                            for (float x = -CityMap.RoadHalf + 0.6f; x < CityMap.RoadHalf; x += 1.2f)
                                f.Box(Geo.X0Z(z + left * x, 0.012f), new Vector3(0.6f, 0.02f, 2.6f), rot, Marking);
                            // Stop line on the incoming half: traffic heading towards this end drives on the left.
                            float side = e > 0 ? 1f : -1f;
                            Vector2 sl = mid + dir * e * (len * 0.5f - CityMap.StopBack + 0.1f) + left * side * CityMap.RoadHalf * 0.5f;
                            f.Box(Geo.X0Z(sl, 0.012f), new Vector3(CityMap.RoadHalf, 0.02f, 0.35f), rot, Marking);
                        }
                    }
                }
            }
        }

        void BuildGangFloors()
        {
            for (int g = 0; g < city.gangs.Count; g++)
            {
                Rect r = city.gangs[g];
                bool vertical = r.height > r.width;
                float len = vertical ? r.height : r.width;
                for (float u = 0f; u < len; u += 4f)
                {
                    float seg = Mathf.Min(4f, len - u);
                    Vector2 c = vertical ? new Vector2(r.center.x, r.yMin + u + seg * 0.5f) : new Vector2(r.xMin + u + seg * 0.5f, r.center.y);
                    if (city.SurfaceAt(c) != Surface.Gang) continue;
                    Vector3 size = vertical ? new Vector3(r.width + 0.6f, 0.04f, seg) : new Vector3(seg, 0.04f, r.height + 0.6f);
                    Vector3 c3 = Geo.X0Z(c, 0.02f);
                    Chunk(c3, true).Box(c3, size, Quaternion.identity, (int)(u / 4f) % 2 == 0 ? GangFloor : Palette.Shade(GangFloor, 0.94f));
                    // gutter
                    Vector3 gut = vertical ? new Vector3(r.xMin + 0.15f, 0.045f, c.y) : new Vector3(c.x, 0.045f, r.yMin + 0.15f);
                    Chunk(c3, true).Box(gut, vertical ? new Vector3(0.25f, 0.02f, seg) : new Vector3(seg, 0.02f, 0.25f), Quaternion.identity, new Color(0.35f, 0.33f, 0.3f));
                }
            }
        }

        // ------------------------------------------------------------------ buildings

        void BuildBlock(int bi, int bj)
        {
            Rect b = city.BlockRect(bi, bj);
            float gx = float.NaN, gz = float.NaN;
            for (int g = 0; g < city.gangs.Count; g++)
            {
                Rect gr = city.gangs[g];
                if (!gr.Overlaps(b)) continue;
                if (gr.height > gr.width) gx = gr.center.x;
                else gz = gr.center.y;
            }
            float gap = CityMap.GangHalf + 0.25f;
            float midZ = float.IsNaN(gz) ? b.center.y : gz;
            float rowGap = float.IsNaN(gz) ? 0f : gap;
            // South row faces the street below (towards the camera), north row faces the street above.
            BuildRow(b.xMin, b.xMax, b.yMin, midZ - rowGap, gx, gap, true);
            BuildRow(b.xMin, b.xMax, midZ + rowGap, b.yMax, gx, gap, false);
            // Ground patch inside the block (backyards, visible between buildings).
            Vector3 c3 = new Vector3(b.center.x, 0.005f, b.center.y);
            Chunk(c3, true).Box(c3, new Vector3(b.width, 0.01f, b.height), Quaternion.identity, new Color(0.46f, 0.43f, 0.38f));
        }

        void BuildRow(float x0, float x1, float z0, float z1, float gx, float gap, bool facesSouth)
        {
            if (float.IsNaN(gx))
            {
                BuildLots(x0, x1, z0, z1, facesSouth);
            }
            else
            {
                BuildLots(x0, gx - gap, z0, z1, facesSouth);
                BuildLots(gx + gap, x1, z0, z1, facesSouth);
            }
        }

        void BuildLots(float x0, float x1, float z0, float z1, bool facesSouth)
        {
            float x = x0;
            while (x < x1 - 0.5f)
            {
                float w = R(6f, 11f);
                if (x1 - (x + w) < 5f) w = x1 - x;
                Building(x + 0.15f, x + w - 0.15f, z0, z1, facesSouth);
                x += w;
            }
        }

        void Building(float x0, float x1, float z0, float z1, bool facesSouth)
        {
            float w = x1 - x0;
            float depth = z1 - z0;
            // North-row buildings stay low so they never hide the street behind them from the camera.
            float h = facesSouth ? R(4f, 8f) : R(3.2f, 5.2f);
            Color wall = Walls[rng.Next(Walls.Length)];
            Vector3 c = new Vector3((x0 + x1) * 0.5f, 0f, (z0 + z1) * 0.5f);
            MeshBatcher mb = Chunk(c);
            mb.BoxBottom(c, new Vector3(w, h, depth), wall);
            // Roof slab and bits.
            Color roof = Roofs[rng.Next(Roofs.Length)];
            mb.BoxBottom(c + new Vector3(0, h, 0), new Vector3(w + 0.3f, 0.25f, depth + 0.3f), roof);
            if (rng.NextDouble() < 0.45)
            {
                Vector3 tp = c + new Vector3(R(-w * 0.3f, w * 0.3f), h + 0.25f, R(-depth * 0.3f, depth * 0.3f));
                mb.BoxBottom(tp, new Vector3(0.9f, 0.5f, 0.9f), new Color(0.5f, 0.5f, 0.5f));
                mb.Prism(tp + new Vector3(0, 1.05f, 0), Vector3.up, 0.55f, 1.1f, 8, rng.NextDouble() < 0.5 ? new Color(0.2f, 0.45f, 0.85f) : new Color(0.95f, 0.55f, 0.15f));
            }
            if (rng.NextDouble() < 0.4)
                mb.BoxBottom(c + new Vector3(R(-w * 0.3f, w * 0.3f), h + 0.25f, R(-depth * 0.3f, depth * 0.3f)), new Vector3(0.8f, 0.5f, 0.6f), new Color(0.85f, 0.85f, 0.85f));

            // Street-facing ruko front: shutter / shop opening, awning, upper windows.
            float fz = facesSouth ? z0 : z1;
            float sgn = facesSouth ? -1f : 1f;
            float shopH = Mathf.Min(2.8f, h - 0.6f);
            bool shutter = rng.NextDouble() < 0.35;
            mb.BoxBottom(new Vector3(c.x, 0.05f, fz + sgn * 0.03f), new Vector3(w - 0.8f, shopH, 0.08f), shutter ? new Color(0.62f, 0.64f, 0.66f) : new Color(0.2f, 0.18f, 0.16f));
            if (!shutter && rng.NextDouble() < 0.7)
            {
                // Awning (striped canopy).
                Color aw = SignColors[rng.Next(SignColors.Length)];
                Quaternion tilt = Quaternion.Euler(facesSouth ? -18f : 18f, 0, 0);
                int stripes = Mathf.Max(2, (int)(w / 1.2f));
                for (int s = 0; s < stripes; s++)
                {
                    float sx = x0 + 0.3f + (w - 0.6f) * (s + 0.5f) / stripes;
                    mb.Box(new Vector3(sx, shopH + 0.1f, fz + sgn * 0.75f), new Vector3((w - 0.6f) / stripes, 0.08f, 1.5f), tilt, s % 2 == 0 ? aw : Palette.White);
                }
            }
            for (float wy = shopH + 1.2f; wy < h - 0.8f; wy += 2.6f)
                for (float wx = x0 + 1.2f; wx < x1 - 1f; wx += 2.2f)
                    mb.BoxBottom(new Vector3(wx + 0.5f, wy, fz + sgn * 0.03f), new Vector3(1.1f, 1.1f, 0.08f), new Color(0.22f, 0.3f, 0.38f));

            // Warung signs on camera-facing fronts.
            if (facesSouth && w >= 5.5f && rng.NextDouble() < 0.6)
            {
                Color sc = SignColors[rng.Next(SignColors.Length)];
                float sy = Mathf.Min(shopH + 0.9f, h - 0.7f);
                Vector3 sp = new Vector3(c.x, sy, fz - 0.12f);
                mb.Box(sp, new Vector3(w - 1.2f, 1.1f, 0.14f), Quaternion.identity, sc);
                Color tc = sc.grayscale > 0.6f ? new Color(0.1f, 0.1f, 0.1f) : Color.white;
                TextMesh tm = TextKit.Make(root, SignTexts[rng.Next(SignTexts.Length)], sp + new Vector3(0, 0, -0.09f), Quaternion.identity, 0.7f, tc);
                TextKit.FitWidth(tm, w - 1.8f);
            }
        }

        void BuildOuterRing()
        {
            float m = 32f;
            float x0 = city.MinX, x1 = city.MaxX, z0 = city.MinZ, z1 = city.MaxZ;
            // South ring (faces north towards the first street - keep it low), north ring faces south.
            BuildLots(x0 - m, x1 + m, z0 - m, z0 - 0.1f, false);
            BuildLots(x0 - m, x1 + m, z1 + 0.1f, z1 + m, true);
            RingColumn(x0 - m, x0 - 0.1f, z0, z1);
            RingColumn(x1 + 0.1f, x1 + m, z0, z1);
        }

        void RingColumn(float x0, float x1, float z0, float z1)
        {
            float z = z0;
            while (z < z1 - 0.5f)
            {
                float d = R(8f, 14f);
                if (z1 - (z + d) < 6f) d = z1 - z;
                float h = R(3.5f, 7f);
                Vector3 c = new Vector3((x0 + x1) * 0.5f, 0f, z + d * 0.5f);
                MeshBatcher mb = Chunk(c);
                mb.BoxBottom(c, new Vector3(x1 - x0, h, d - 0.3f), Walls[rng.Next(Walls.Length)]);
                mb.BoxBottom(c + new Vector3(0, h, 0), new Vector3(x1 - x0 + 0.3f, 0.25f, d), Roofs[rng.Next(Roofs.Length)]);
                z += d;
            }
        }

        // ------------------------------------------------------------------ street furniture

        void BuildPolesAndCables()
        {
            float P = CityMap.Pitch;
            float off = CityMap.CorridorHalf - 0.45f;
            // Horizontal streets: poles along both sidewalks, cables strung between consecutive poles.
            for (int j = 0; j < city.nz; j++)
            {
                for (int s = -1; s <= 1; s += 2)
                {
                    List<Vector3> tops = new List<Vector3>();
                    for (int i = 0; i < city.nx - 1; i++)
                        for (int k = 0; k < 3; k++)
                        {
                            float x = i * P + CityMap.CorridorHalf + 4f + k * 16f + R(-1.5f, 1.5f);
                            tops.Add(Pole(new Vector2(x, j * P + s * off)));
                        }
                    Wires(tops);
                }
            }
            for (int i = 0; i < city.nx; i++)
            {
                for (int s = -1; s <= 1; s += 2)
                {
                    List<Vector3> tops = new List<Vector3>();
                    for (int j = 0; j < city.nz - 1; j++)
                        for (int k = 0; k < 3; k++)
                        {
                            float z = j * P + CityMap.CorridorHalf + 4f + k * 16f + R(-1.5f, 1.5f);
                            tops.Add(Pole(new Vector2(i * P + s * off, z)));
                        }
                    Wires(tops);
                }
            }
        }

        Vector3 Pole(Vector2 p)
        {
            Vector3 b = Geo.X0Z(p, CityMap.SidewalkHeight);
            float h = R(6.6f, 7.4f);
            MeshBatcher mb = Chunk(b);
            mb.BoxBottom(b, new Vector3(0.22f, h, 0.22f), PoleColor);
            mb.Box(b + new Vector3(0, h - 0.4f, 0), new Vector3(1.4f, 0.1f, 0.1f), Quaternion.identity, PoleColor);
            if (rng.NextDouble() < 0.25)
                mb.BoxBottom(b + new Vector3(0.25f, h - 2.2f, 0), new Vector3(0.5f, 0.8f, 0.45f), new Color(0.35f, 0.38f, 0.35f));
            if (rng.NextDouble() < 0.4)
            {
                // Cable nest.
                for (int k = 0; k < 5; k++)
                {
                    Vector3 a = b + new Vector3(R(-0.8f, 0.8f), h - R(0.3f, 1.3f), R(-0.8f, 0.8f));
                    Vector3 c = b + new Vector3(R(-0.8f, 0.8f), h - R(0.3f, 1.3f), R(-0.8f, 0.8f));
                    mb.Beam(a, c, 0.05f, Cable);
                }
                mb.Box(b + new Vector3(0, h - 1f, 0), new Vector3(0.45f, 0.4f, 0.45f), Quaternion.Euler(0, 30, 0), Cable);
            }
            return b + Vector3.up * (h - 0.4f);
        }

        void Wires(List<Vector3> tops)
        {
            for (int k = 0; k + 1 < tops.Count; k++)
            {
                Vector3 a = tops[k], b = tops[k + 1];
                int wires = rng.Next(2, 5);
                for (int w = 0; w < wires; w++)
                {
                    Vector3 o = new Vector3(R(-0.6f, 0.6f), -w * 0.18f, R(-0.6f, 0.6f)) * 0.6f;
                    float sag = R(0.4f, 1.2f);
                    Sag(a + o, b + o, sag, 0.045f);
                }
                // Occasional wire across the street to the other side.
                if (rng.NextDouble() < 0.2)
                {
                    Vector3 across = (Mathf.Abs(b.x - a.x) > Mathf.Abs(b.z - a.z)) ? new Vector3(0, 0, R(12f, 18f) * (a.z > 0 ? -1f : 1f)) : new Vector3(R(12f, 18f) * (a.x > 0 ? -1f : 1f), 0, 0);
                    Sag(a, a + across + new Vector3(R(-3f, 3f), R(-0.5f, 0.3f), R(-3f, 3f)), R(0.8f, 1.6f), 0.04f);
                }
            }
        }

        void Sag(Vector3 a, Vector3 b, float sag, float th)
        {
            const int segs = 5;
            Vector3 prev = a;
            MeshBatcher mb = Chunk((a + b) * 0.5f);
            for (int i = 1; i <= segs; i++)
            {
                float t = (float)i / segs;
                Vector3 p = Vector3.Lerp(a, b, t) + Vector3.down * sag * 4f * t * (1f - t);
                mb.Beam(prev, p, th, Cable);
                prev = p;
            }
        }

        void BuildBanners()
        {
            // Spanduk hang across north-south streets so they face the (north-looking) camera.
            float P = CityMap.Pitch;
            for (int k = 0; k < 7; k++)
            {
                int i = rng.Next(city.nx);
                int j = rng.Next(city.nz - 1);
                float z = j * P + CityMap.CorridorHalf + R(8f, 32f);
                float xc = i * P;
                Color bc = rng.NextDouble() < 0.5 ? new Color(0.95f, 0.95f, 0.9f) : new Color(0.85f, 0.15f, 0.15f);
                Vector3 c = new Vector3(xc, 4.9f, z);
                MeshBatcher mb = Chunk(c);
                float span = CityMap.CorridorHalf * 2f - 1f;
                mb.BoxBottom(new Vector3(xc - span * 0.5f, CityMap.SidewalkHeight, z), new Vector3(0.12f, 5.6f, 0.12f), new Color(0.55f, 0.4f, 0.25f));
                mb.BoxBottom(new Vector3(xc + span * 0.5f, CityMap.SidewalkHeight, z), new Vector3(0.12f, 5.6f, 0.12f), new Color(0.55f, 0.4f, 0.25f));
                mb.Box(c, new Vector3(span - 2f, 1.1f, 0.08f), Quaternion.identity, bc);
                mb.Beam(new Vector3(xc - span * 0.5f, 5.5f, z), new Vector3(xc + span * 0.5f, 5.5f, z), 0.03f, Cable);
                Color tc = bc.r > 0.9f && bc.g > 0.9f ? new Color(0.8f, 0.1f, 0.1f) : Color.white;
                TextMesh tm = TextKit.Make(root, BannerTexts[rng.Next(BannerTexts.Length)], c + new Vector3(0, 0, -0.06f), Quaternion.identity, 0.6f, tc);
                TextKit.FitWidth(tm, span - 3f);
            }
        }

        void BuildTrees()
        {
            for (int k = 0; k < 26; k++)
            {
                int i, j, d;
                do
                {
                    i = rng.Next(city.nx);
                    j = rng.Next(city.nz);
                    d = rng.Next(2);
                } while (!city.HasEdge(i, j, d));
                Vector2 dir = CityMap.Dirs[d];
                float side = rng.Next(2) == 0 ? 1f : -1f;
                // Trees only on the north side of east-west streets so they never hide the road.
                if (d == 0) side = 1f;
                Vector2 p = city.NodePos(i, j) + dir * (CityMap.CorridorHalf + R(3f, 37f)) + Geo.Left(dir) * side * (CityMap.CorridorHalf - 0.9f);
                Vector3 b = Geo.X0Z(p, CityMap.SidewalkHeight);
                MeshBatcher mb = Chunk(b);
                float h = R(2.4f, 3.2f);
                mb.BoxBottom(b, new Vector3(0.3f, h, 0.3f), new Color(0.45f, 0.3f, 0.18f));
                Color leaf = rng.NextDouble() < 0.5 ? new Color(0.3f, 0.6f, 0.25f) : new Color(0.4f, 0.68f, 0.3f);
                mb.Ball(b + new Vector3(0, h + 0.7f, 0), R(1.3f, 1.8f), leaf, 6);
                mb.Ball(b + new Vector3(R(-0.6f, 0.6f), h + 1.5f, R(-0.6f, 0.6f)), R(0.9f, 1.2f), Palette.Shade(leaf, 1.12f), 6);
                // painted trunk base (white/red, very Indonesian)
                mb.BoxBottom(b, new Vector3(0.34f, 0.6f, 0.34f), Palette.White);
            }
        }
    }
}
