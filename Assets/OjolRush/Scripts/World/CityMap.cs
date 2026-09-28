using System.Collections.Generic;
using UnityEngine;

namespace OjolRush
{
    public enum Surface { Blocked, Road, Sidewalk, Gang }

    /// <summary>A place where orders are picked up or dropped off (always on a sidewalk).</summary>
    public class Spot
    {
        public Vector2 pos;
        public string name;
        public bool restaurant;
    }

    /// <summary>
    /// The hand-designed district: a grid of 4-lane streets (2 per direction, left-hand traffic
    /// like Indonesia) with sidewalks, plus two narrow gang shortcuts cutting through blocks.
    /// Pure data + queries, no GameObjects.
    /// </summary>
    public class CityMap
    {
        public const float Pitch = 60f;
        public const float LaneWidth = 3.5f;
        public const int LanesPerDir = 2;
        public const float RoadHalf = LaneWidth * LanesPerDir;   // 7
        public const float CorridorHalf = RoadHalf + 3f;         // 10 (sidewalk 3 m)
        public const float SidewalkHeight = 0.12f;
        public const float GangHalf = 1.75f;
        public const float EdgeLength = Pitch - 2f * CorridorHalf; // 40
        /// <summary>Vehicles stop this far before the end of an edge (before the zebra crossing).</summary>
        public const float StopBack = 3.5f;

        /// <summary>E, N, W, S. Turning left = +1, right = +3 (mod 4).</summary>
        public static readonly Vector2[] Dirs = { new Vector2(1, 0), new Vector2(0, 1), new Vector2(-1, 0), new Vector2(0, -1) };

        public readonly int nx;
        public readonly int nz;
        public readonly List<Rect> gangs = new List<Rect>();
        public readonly List<Spot> spots = new List<Spot>();

        static readonly string[] HorizontalStreets = { "Jl. Kenanga", "Jl. Pasar Lama", "Jl. Melati", "Jl. Kebon Kacang", "Jl. Cempaka", "Jl. Rawa Belong", "Jl. Mangga Dua-an" };
        static readonly string[] VerticalStreets = { "Jl. Pahlawan", "Jl. Kramat", "Jl. Salemba Kecil", "Jl. Tanah Abang Ria", "Jl. Cikini Raya-ish" };

        public static readonly string[] RestaurantNames =
        {
            "Warung Bu Tini", "Bakso Mas Joko", "Martabak Bang Udin", "Nasi Padang Sederhana Banget",
            "Kopi Senja Abadi", "Sate Pak Kumis", "Mie Ayam Gerobak Biru", "Pecel Lele Cak Mat",
            "Seblak Teh Ncep", "Nasi Uduk Bu Yayah", "Soto Betawi H. Ma'ruf-an", "Gorengan Mang Asep",
        };

        public static readonly string[] HomeNames =
        {
            "Kos Melati No. 7", "Kantor Lt. 3 (titip satpam)", "Rumah Pagar Hijau", "Apartemen Tower B",
            "Kontrakan Bu RT", "Pos Ronda RW 05", "Ruko Cat Kuning", "Bengkel Jaya Motor",
            "Kos Putri Anggrek", "Masjid Al-Ikhlas (samping)", "Salon Cantik Sekali", "Rumah No. 13B",
            "Warnet Gaming Pro", "Toko Bangunan Sinar",
        };

        public CityMap(int nx = 5, int nz = 7)
        {
            this.nx = nx;
            this.nz = nz;
            // Gang 1: vertical alley through two blocks, crossing a street at z = 2*Pitch.
            gangs.Add(Rect.MinMaxRect(1.5f * Pitch - GangHalf, Pitch, 1.5f * Pitch + GangHalf, 3f * Pitch));
            // Gang 2: horizontal alley through two blocks, crossing a street at x = 3*Pitch.
            gangs.Add(Rect.MinMaxRect(2f * Pitch, 4.5f * Pitch - GangHalf, 4f * Pitch, 4.5f * Pitch + GangHalf));
        }

        public float MinX { get { return -CorridorHalf; } }
        public float MaxX { get { return (nx - 1) * Pitch + CorridorHalf; } }
        public float MinZ { get { return -CorridorHalf; } }
        public float MaxZ { get { return (nz - 1) * Pitch + CorridorHalf; } }
        public Vector2 Center { get { return new Vector2((nx - 1) * Pitch * 0.5f, (nz - 1) * Pitch * 0.5f); } }

        public bool HasNode(int i, int j) { return i >= 0 && j >= 0 && i < nx && j < nz; }
        public Vector2 NodePos(int i, int j) { return new Vector2(i * Pitch, j * Pitch); }

        public static int Opposite(int d) { return (d + 2) & 3; }
        public static int LeftOf(int d) { return (d + 1) & 3; }
        public static int RightOf(int d) { return (d + 3) & 3; }
        public static bool IsHorizontal(int d) { return (d & 1) == 0; }

        public static void Step(int i, int j, int d, out int ni, out int nj)
        {
            ni = i + (int)Dirs[d].x;
            nj = j + (int)Dirs[d].y;
        }

        public bool HasEdge(int i, int j, int d)
        {
            int ni, nj;
            Step(i, j, d, out ni, out nj);
            return HasNode(i, j) && HasNode(ni, nj);
        }

        /// <summary>Offset from the road centerline to the centre of a lane (left-hand traffic).</summary>
        public static Vector2 LaneOffset(int d, int lane)
        {
            return Geo.Left(Dirs[d]) * ((lane + 0.5f) * LaneWidth);
        }

        /// <summary>Start/end of a lane along the edge leaving node (i,j) in direction d.</summary>
        public void EdgeLane(int i, int j, int d, int lane, out Vector2 a, out Vector2 b)
        {
            Vector2 dir = Dirs[d];
            Vector2 off = LaneOffset(d, lane);
            a = NodePos(i, j) + dir * CorridorHalf + off;
            b = NodePos(i, j) + dir * (Pitch - CorridorHalf) + off;
        }

        /// <summary>Signed distance to the nearest road centerline (horizontal or vertical) - used for surface queries.</summary>
        float AxisDistance(float v, int count)
        {
            int k = Mathf.Clamp(Mathf.RoundToInt(v / Pitch), 0, count - 1);
            return Mathf.Abs(v - k * Pitch);
        }

        public Surface SurfaceAt(Vector2 p)
        {
            if (p.x < MinX || p.x > MaxX || p.y < MinZ || p.y > MaxZ) return Surface.Blocked;
            float dz = AxisDistance(p.y, nz); // distance to a horizontal street
            float dx = AxisDistance(p.x, nx); // distance to a vertical street
            float d = Mathf.Min(dx, dz);
            if (d <= RoadHalf) return Surface.Road;
            if (d <= CorridorHalf) return Surface.Sidewalk;
            for (int g = 0; g < gangs.Count; g++)
                if (gangs[g].Contains(p)) return Surface.Gang;
            return Surface.Blocked;
        }

        public bool IsDrivable(Vector2 p) { return SurfaceAt(p) != Surface.Blocked; }

        public bool IsDrivable(Vector2 p, float r)
        {
            return IsDrivable(p) && IsDrivable(p + new Vector2(r, 0)) && IsDrivable(p - new Vector2(r, 0))
                && IsDrivable(p + new Vector2(0, r)) && IsDrivable(p - new Vector2(0, r));
        }

        public float SurfaceHeight(Vector2 p)
        {
            return SurfaceAt(p) == Surface.Sidewalk ? SidewalkHeight : 0f;
        }

        /// <summary>True when the nearest street at p runs east-west.</summary>
        public bool OnHorizontalStreet(Vector2 p)
        {
            return AxisDistance(p.y, nz) <= AxisDistance(p.x, nx);
        }

        /// <summary>Signed offset of p from the centreline of the nearest street (left of E / left of N positive).</summary>
        public float StreetOffset(Vector2 p, out bool horizontal)
        {
            horizontal = OnHorizontalStreet(p);
            if (horizontal)
            {
                int j = Mathf.Clamp(Mathf.RoundToInt(p.y / Pitch), 0, nz - 1);
                return p.y - j * Pitch;
            }
            int i = Mathf.Clamp(Mathf.RoundToInt(p.x / Pitch), 0, nx - 1);
            return -(p.x - i * Pitch);
        }

        public bool InIntersection(Vector2 p)
        {
            return AxisDistance(p.x, nx) <= CorridorHalf && AxisDistance(p.y, nz) <= CorridorHalf;
        }

        public string StreetNameAt(Vector2 p)
        {
            float dz = AxisDistance(p.y, nz);
            float dx = AxisDistance(p.x, nx);
            if (dz <= dx)
            {
                int j = Mathf.Clamp(Mathf.RoundToInt(p.y / Pitch), 0, nz - 1);
                return HorizontalStreets[j % HorizontalStreets.Length];
            }
            int i = Mathf.Clamp(Mathf.RoundToInt(p.x / Pitch), 0, nx - 1);
            return VerticalStreets[i % VerticalStreets.Length];
        }

        /// <summary>Block interiors (building land), indexed bi in [0,nx-2], bj in [0,nz-2].</summary>
        public Rect BlockRect(int bi, int bj)
        {
            return Rect.MinMaxRect(bi * Pitch + CorridorHalf, bj * Pitch + CorridorHalf,
                (bi + 1) * Pitch - CorridorHalf, (bj + 1) * Pitch - CorridorHalf);
        }

        /// <summary>Builds the pickup/drop-off spots on the sidewalks in front of each block side.</summary>
        public void BuildSpots(System.Random rng)
        {
            spots.Clear();
            int r = 0, h = 0;
            for (int bi = 0; bi < nx - 1; bi++)
            {
                for (int bj = 0; bj < nz - 1; bj++)
                {
                    Rect b = BlockRect(bi, bj);
                    for (int side = 0; side < 4; side++)
                    {
                        float u = (float)(rng.NextDouble() * 20.0 - 10.0);
                        Vector2 p;
                        switch (side)
                        {
                            case 0: p = new Vector2(b.center.x + u, b.yMin - 1.5f); break;
                            case 1: p = new Vector2(b.xMax + 1.5f, b.center.y + u); break;
                            case 2: p = new Vector2(b.center.x + u, b.yMax + 1.5f); break;
                            default: p = new Vector2(b.xMin - 1.5f, b.center.y + u); break;
                        }
                        // Keep spots out of the gang mouths.
                        bool nearGang = false;
                        for (int g = 0; g < gangs.Count; g++)
                        {
                            Rect gr = gangs[g];
                            if (Mathf.Abs(p.x - Mathf.Clamp(p.x, gr.xMin, gr.xMax)) < 3f && Mathf.Abs(p.y - Mathf.Clamp(p.y, gr.yMin, gr.yMax)) < 3f)
                                nearGang = true;
                        }
                        if (nearGang) continue;
                        bool isRestaurant = rng.NextDouble() < 0.35;
                        Spot s = new Spot { pos = p, restaurant = isRestaurant };
                        s.name = isRestaurant ? RestaurantNames[r++ % RestaurantNames.Length] : HomeNames[h++ % HomeNames.Length];
                        spots.Add(s);
                    }
                }
            }
        }

        /// <summary>World position of a lane point at distance s along an edge, pushed to the curb (for passengers).</summary>
        public Vector2 CurbPoint(int i, int j, int d, float s, float extraOffset)
        {
            Vector2 a, b;
            EdgeLane(i, j, d, LanesPerDir - 1, out a, out b);
            return a + Dirs[d] * s + Geo.Left(Dirs[d]) * extraOffset;
        }
    }
}
