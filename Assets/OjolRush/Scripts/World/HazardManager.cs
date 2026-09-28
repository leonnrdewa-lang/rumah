using System.Collections.Generic;
using UnityEngine;

namespace OjolRush
{
    public class Passenger
    {
        public int i, j, d;
        public float along;
        public Vector2 pos;
        public GameObject go;
        public Transform arm;
        public bool claimed;
        public float phase;
    }

    class CircleHazard
    {
        public Vector2 pos;
        public float radius;
        public float cooldown;
        public GameObject go;
    }

    class SpeedBump
    {
        public Vector2 pos;
        public Vector2 roadDir;
        public float cooldown;
    }

    class Obstacle
    {
        public Vector2 pos;
        public Vector2 fwd;
        public float halfLength, halfWidth;
        public GameObject go;
        public float steamTimer;
    }

    class Critter
    {
        public Vector2 pos;
        public Vector2 vel;
        public Vector2 home;
        public Vector2 target;
        public float timer;
        public GameObject go;
        public bool flung;
        public float flyTime;
        public float y;
        public float cooldown;
        public Rect bounds;
    }

    class Zone
    {
        public Rect rect;
        public string street;
        public GameObject go;
        public Renderer lampA, lampB;
    }

    /// <summary>
    /// Everything on the street that is not traffic: puddles, potholes, polisi tidur, gerobak,
    /// cats, gang chickens/kids/laundry, waving angkot passengers, flood zones and razia checkpoints.
    /// </summary>
    public class HazardManager : MonoBehaviour
    {
        GameManager gm;
        CityMap city;
        System.Random rng;
        Transform dynRoot;

        readonly List<CircleHazard> puddles = new List<CircleHazard>();
        readonly List<CircleHazard> rainPuddles = new List<CircleHazard>();
        readonly List<CircleHazard> potholes = new List<CircleHazard>();
        readonly List<SpeedBump> bumps = new List<SpeedBump>();
        readonly List<Obstacle> gerobaks = new List<Obstacle>();
        readonly List<Critter> cats = new List<Critter>();
        readonly List<Critter> chickens = new List<Critter>();
        readonly List<Critter> kids = new List<Critter>();
        public readonly List<Passenger> passengers = new List<Passenger>();
        readonly List<Zone> floods = new List<Zone>();
        readonly List<Zone> razias = new List<Zone>();

        int passengerTarget;
        float catTimer;
        float raziaCooldown;
        float splashTimer;
        float time;
        RushLevelConfig level;
        Material raziaRed, raziaBlue, raziaOff;

        public bool PlayerInFlood { get; private set; }
        public IList<Passenger> Passengers { get { return passengers; } }

        static readonly Color PuddleColor = new Color(0.32f, 0.45f, 0.58f);
        static readonly Color PotholeColor = new Color(0.1f, 0.1f, 0.11f);

        public void Init(GameManager game, CityMap map, System.Random random)
        {
            gm = game;
            city = map;
            rng = random;
            dynRoot = new GameObject("Hazards").transform;
            dynRoot.SetParent(transform, false);
            raziaRed = Mats.Get(new Color(1f, 0.1f, 0.1f), true);
            raziaBlue = Mats.Get(new Color(0.15f, 0.35f, 1f), true);
            raziaOff = Mats.Get(new Color(0.2f, 0.2f, 0.25f));
            BuildGangDecor();
        }

        float R(float a, float b) { return a + (float)rng.NextDouble() * (b - a); }

        void RandomRoadEdge(out int i, out int j, out int d)
        {
            do
            {
                i = rng.Next(city.nx);
                j = rng.Next(city.nz);
                d = rng.Next(2) == 0 ? 0 : 1; // east or north: each street segment once
            } while (!city.HasEdge(i, j, d));
        }

        Vector2 RoadPoint(int i, int j, int d, float along, float offset)
        {
            Vector2 dir = CityMap.Dirs[d];
            return city.NodePos(i, j) + dir * (CityMap.CorridorHalf + along) + Geo.Left(dir) * offset;
        }

        void Clear<T>(List<T> list, System.Func<T, GameObject> go)
        {
            for (int k = 0; k < list.Count; k++)
            {
                GameObject g = go(list[k]);
                if (g != null) Destroy(g);
            }
            list.Clear();
        }

        public void ResetHazards(RushLevelConfig lvl)
        {
            Clear(puddles, h => h.go);
            Clear(rainPuddles, h => h.go);
            Clear(potholes, h => h.go);
            bumps.Clear();
            Clear(gerobaks, o => o.go);
            Clear(cats, c => c.go);
            Clear(passengers, p => p.go);
            Clear(floods, z => z.go);
            Clear(razias, z => z.go);
            if (bumpObject != null) Destroy(bumpObject);
            PlayerInFlood = false;
            raziaCooldown = 0f;

            for (int k = 0; k < 16; k++) puddles.Add(MakePuddle(false));
            for (int k = 0; k < 14; k++)
            {
                int i, j, d;
                RandomRoadEdge(out i, out j, out d);
                CircleHazard h = new CircleHazard { pos = RoadPoint(i, j, d, R(3f, 37f), R(-6f, 6f)), radius = R(0.6f, 0.9f) };
                MeshBatcher mb = new MeshBatcher();
                mb.Prism(new Vector3(0, 0.012f, 0), Vector3.up, h.radius + 0.18f, 0.02f, 7, new Color(0.3f, 0.29f, 0.28f));
                mb.Prism(new Vector3(0, 0.02f, 0), Vector3.up, h.radius, 0.02f, 7, PotholeColor);
                h.go = mb.BuildObject("Pothole", dynRoot, false);
                h.go.transform.position = Geo.X0Z(h.pos);
                potholes.Add(h);
            }
            BuildSpeedBumps();
            for (int k = 0; k < 12; k++) gerobaks.Add(MakeGerobak());
            ResetGangCritters();
            SetLevel(lvl, true);
        }

        GameObject bumpObject;

        void BuildSpeedBumps()
        {
            MeshBatcher mb = new MeshBatcher();
            for (int k = 0; k < 10; k++)
            {
                int i, j, d;
                RandomRoadEdge(out i, out j, out d);
                Vector2 dir = CityMap.Dirs[d];
                Vector2 c = RoadPoint(i, j, d, R(12f, 28f), 0f);
                bumps.Add(new SpeedBump { pos = c, roadDir = dir });
                Vector2 l = Geo.Left(dir);
                int stripes = 8;
                float w = CityMap.RoadHalf * 2f / stripes;
                for (int s = 0; s < stripes; s++)
                {
                    Vector2 p = c + l * (-CityMap.RoadHalf + w * (s + 0.5f));
                    Quaternion rot = Quaternion.Euler(0, Geo.Heading(dir), 0);
                    mb.Box(Geo.X0Z(p, 0.06f), new Vector3(w, 0.12f, 0.8f), rot, s % 2 == 0 ? new Color(1f, 0.82f, 0.1f) : new Color(0.1f, 0.1f, 0.1f));
                }
            }
            bumpObject = mb.BuildObject("PolisiTidur", dynRoot, false);
        }

        CircleHazard MakePuddle(bool rain)
        {
            Vector2 p;
            if (rain)
            {
                // During rain, fresh puddles appear around the player.
                Vector2 c = gm.player.Pos;
                int tries = 0;
                do
                {
                    p = c + new Vector2(R(-70f, 70f), R(-70f, 70f));
                    tries++;
                } while (city.SurfaceAt(p) != Surface.Road && tries < 30);
            }
            else
            {
                int i, j, d;
                RandomRoadEdge(out i, out j, out d);
                p = RoadPoint(i, j, d, R(3f, 37f), R(-6.3f, 6.3f));
            }
            CircleHazard h = new CircleHazard { pos = p, radius = R(1.3f, 2.4f) };
            MeshBatcher mb = new MeshBatcher();
            mb.Prism(new Vector3(0, 0.012f, 0), Vector3.up, h.radius, 0.02f, 9, PuddleColor);
            mb.Prism(new Vector3(h.radius * 0.25f, 0.018f, h.radius * 0.2f), Vector3.up, h.radius * 0.35f, 0.02f, 7, new Color(0.62f, 0.75f, 0.85f));
            h.go = mb.BuildObject("Puddle", dynRoot, false);
            h.go.transform.position = Geo.X0Z(h.pos);
            return h;
        }

        Obstacle MakeGerobak()
        {
            int i, j, d;
            RandomRoadEdge(out i, out j, out d);
            float side = rng.Next(2) == 0 ? 1f : -1f;
            Vector2 dir = CityMap.Dirs[d];
            Vector2 p = RoadPoint(i, j, d, R(4f, 36f), side * R(8.2f, 8.8f));
            Obstacle o = new Obstacle { pos = p, fwd = dir, halfLength = 1.0f, halfWidth = 0.6f };
            MeshBatcher mb = new MeshBatcher();
            Color wood = new Color(0.62f, 0.4f, 0.2f);
            Color[] canopy = { new Color(0.9f, 0.2f, 0.2f), new Color(0.2f, 0.5f, 0.9f), new Color(0.95f, 0.75f, 0.1f), new Color(0.2f, 0.7f, 0.4f) };
            mb.BoxBottom(new Vector3(0, 0.35f, 0), new Vector3(1.1f, 0.6f, 1.9f), wood);
            mb.BoxBottom(new Vector3(0, 0.95f, 0.2f), new Vector3(1.0f, 0.5f, 1.2f), new Color(0.75f, 0.85f, 0.9f));
            mb.BoxBottom(new Vector3(0, 0.95f, -0.65f), new Vector3(0.7f, 0.45f, 0.45f), new Color(0.7f, 0.7f, 0.72f)); // pot
            mb.Prism(new Vector3(0.55f, 0.3f, 0), Vector3.right, 0.3f, 0.1f, 8, Palette.Tire);
            mb.Prism(new Vector3(-0.55f, 0.3f, 0), Vector3.right, 0.3f, 0.1f, 8, Palette.Tire);
            mb.BoxBottom(new Vector3(0, 0.95f, 0), new Vector3(0.06f, 1.4f, 0.06f), new Color(0.4f, 0.4f, 0.4f));
            mb.BoxBottom(new Vector3(0, 2.35f, 0), new Vector3(1.9f, 0.12f, 2.3f), canopy[rng.Next(canopy.Length)]);
            // vendor
            // Vendor stands on the building side of the cart.
            Vector3 vp = new Vector3(side > 0 ? -0.95f : 0.95f, 0, 0);
            mb.BoxBottom(vp + new Vector3(0, 0.05f, 0), new Vector3(0.36f, 0.8f, 0.3f), new Color(0.3f, 0.3f, 0.4f));
            mb.BoxBottom(vp + new Vector3(0, 0.85f, 0), new Vector3(0.44f, 0.55f, 0.32f), Palette.Pick(Palette.JacketColors, rng));
            mb.Ball(vp + new Vector3(0, 1.58f, 0), 0.18f, Palette.Skin);
            o.go = mb.BuildObject("Gerobak", dynRoot);
            o.go.transform.position = Geo.X0Z(p, CityMap.SidewalkHeight);
            o.go.transform.rotation = Quaternion.Euler(0, Geo.Heading(dir), 0);
            o.steamTimer = R(0f, 0.3f);
            return o;
        }

        // ------------------------------------------------------------------ gang decor & critters

        void BuildGangDecor()
        {
            MeshBatcher mb = new MeshBatcher();
            Color[] cloth = { new Color(0.95f, 0.3f, 0.3f), new Color(0.3f, 0.6f, 0.95f), new Color(1f, 0.9f, 0.3f), new Color(0.95f, 0.95f, 0.95f), new Color(0.5f, 0.85f, 0.5f), new Color(0.9f, 0.5f, 0.8f) };
            for (int g = 0; g < city.gangs.Count; g++)
            {
                Rect r = city.gangs[g];
                bool vertical = r.height > r.width;
                float len = vertical ? r.height : r.width;
                for (float u = 6f; u < len - 4f; u += R(5f, 8f))
                {
                    Vector2 c = vertical ? new Vector2(r.center.x, r.yMin + u) : new Vector2(r.xMin + u, r.center.y);
                    if (city.SurfaceAt(c) != Surface.Gang) continue;
                    Vector2 across = vertical ? new Vector2(1, 0) : new Vector2(0, 1);
                    Vector3 a = Geo.X0Z(c - across * (CityMap.GangHalf + 0.3f), 2.9f);
                    Vector3 b = Geo.X0Z(c + across * (CityMap.GangHalf + 0.3f), 2.9f);
                    mb.Beam(a, b, 0.04f, new Color(0.2f, 0.2f, 0.2f));
                    int items = rng.Next(2, 5);
                    for (int k = 0; k < items; k++)
                    {
                        float t = (k + 0.5f) / items + R(-0.08f, 0.08f);
                        Vector3 p = Vector3.Lerp(a, b, t) + Vector3.down * 0.35f;
                        Vector3 size = vertical ? new Vector3(R(0.45f, 0.75f), R(0.5f, 0.8f), 0.04f) : new Vector3(0.04f, R(0.5f, 0.8f), R(0.45f, 0.75f));
                        mb.Box(p, size, Quaternion.identity, cloth[rng.Next(cloth.Length)]);
                    }
                }
            }
            mb.BuildObject("GangLaundry", transform, false);
        }

        void ResetGangCritters()
        {
            Clear(chickens, c => c.go);
            Clear(kids, c => c.go);
            for (int g = 0; g < city.gangs.Count; g++)
            {
                Rect r = city.gangs[g];
                for (int k = 0; k < 7; k++)
                {
                    Vector2 p = GangPoint(r);
                    Critter c = new Critter { pos = p, home = p, target = p, bounds = r, timer = R(0f, 1f) };
                    MeshBatcher mb = new MeshBatcher();
                    Color body = rng.NextDouble() < 0.5 ? new Color(0.95f, 0.93f, 0.88f) : new Color(0.6f, 0.35f, 0.2f);
                    mb.BoxBottom(new Vector3(0, 0.15f, 0), new Vector3(0.28f, 0.28f, 0.4f), body);
                    mb.BoxBottom(new Vector3(0, 0.35f, 0.18f), new Vector3(0.16f, 0.2f, 0.16f), body);
                    mb.BoxBottom(new Vector3(0, 0.55f, 0.2f), new Vector3(0.06f, 0.08f, 0.12f), new Color(0.9f, 0.1f, 0.1f));
                    mb.BoxBottom(new Vector3(0, 0.4f, 0.3f), new Vector3(0.06f, 0.05f, 0.08f), new Color(1f, 0.7f, 0.1f));
                    mb.BoxBottom(new Vector3(0, 0f, 0), new Vector3(0.12f, 0.15f, 0.05f), new Color(1f, 0.7f, 0.1f));
                    c.go = mb.BuildObject("Ayam", dynRoot, false);
                    chickens.Add(c);
                }
                for (int k = 0; k < 2; k++)
                {
                    Vector2 p = GangPoint(r);
                    Critter c = new Critter { pos = p, home = p, bounds = r, timer = R(0f, 6f) };
                    MeshBatcher mb = new MeshBatcher();
                    Color shirt = Palette.Pick(Palette.JacketColors, rng);
                    mb.BoxBottom(new Vector3(0, 0f, 0), new Vector3(0.3f, 0.45f, 0.2f), new Color(0.2f, 0.25f, 0.45f));
                    mb.BoxBottom(new Vector3(0, 0.45f, 0), new Vector3(0.38f, 0.42f, 0.24f), shirt);
                    mb.Ball(new Vector3(0, 1.02f, 0), 0.16f, Palette.Skin);
                    mb.Ball(new Vector3(0.45f, 0.14f, 0.2f), 0.14f, new Color(1f, 1f, 1f));
                    c.go = mb.BuildObject("Anak", dynRoot, false);
                    kids.Add(c);
                }
            }
        }

        Vector2 GangPoint(Rect r)
        {
            for (int tries = 0; tries < 40; tries++)
            {
                Vector2 p = new Vector2(R(r.xMin + 0.4f, r.xMax - 0.4f), R(r.yMin + 0.4f, r.yMax - 0.4f));
                if (city.SurfaceAt(p) == Surface.Gang) return p;
            }
            return r.center;
        }

        // ------------------------------------------------------------------ level-driven content

        public void SetLevel(RushLevelConfig lvl, bool reset)
        {
            level = lvl;
            passengerTarget = lvl.waitingPassengers;
            catTimer = Mathf.Min(catTimer, lvl.catInterval);
            if (reset) catTimer = lvl.catInterval;
            while (passengers.Count < passengerTarget) passengers.Add(MakePassenger());
            while (floods.Count < lvl.floodZones)
            {
                Zone z = MakeFlood();
                if (z == null) break;
                floods.Add(z);
                gm.hud.Banner("BANJIR di " + z.street + "!", new Color(0.4f, 0.75f, 1f));
            }
            while (razias.Count < lvl.raziaCount)
            {
                Zone z = MakeRazia();
                if (z == null) break;
                razias.Add(z);
                gm.hud.Banner("RAZIA di " + z.street + "! Cari jalan lain", new Color(1f, 0.45f, 0.35f));
            }
        }

        Passenger MakePassenger()
        {
            int i, j, d;
            do
            {
                i = rng.Next(city.nx);
                j = rng.Next(city.nz);
                d = rng.Next(4);
            } while (!city.HasEdge(i, j, d));
            Passenger p = new Passenger { i = i, j = j, d = d, along = R(8f, 30f), phase = R(0f, 6f) };
            p.pos = city.CurbPoint(i, j, d, p.along, 2.35f);
            GameObject go = new GameObject("Penumpang");
            go.transform.SetParent(dynRoot, false);
            MeshBatcher mb = new MeshBatcher();
            Color shirt = Palette.Pick(Palette.JacketColors, rng);
            mb.BoxBottom(new Vector3(0, 0f, 0), new Vector3(0.36f, 0.8f, 0.24f), new Color(0.25f, 0.25f, 0.3f));
            mb.BoxBottom(new Vector3(0, 0.8f, 0), new Vector3(0.48f, 0.62f, 0.28f), shirt);
            mb.Ball(new Vector3(0, 1.62f, 0), 0.2f, Palette.Skin);
            mb.Attach(go, true);
            GameObject arm = new GameObject("Arm");
            arm.transform.SetParent(go.transform, false);
            arm.transform.localPosition = new Vector3(0.26f, 1.35f, 0);
            MeshBatcher am = new MeshBatcher();
            am.BoxBottom(new Vector3(0, 0f, 0), new Vector3(0.13f, 0.62f, 0.13f), shirt);
            am.Ball(new Vector3(0, 0.66f, 0), 0.09f, Palette.Skin);
            am.Attach(arm, false);
            p.go = go;
            p.arm = arm.transform;
            go.transform.position = Geo.X0Z(p.pos, CityMap.SidewalkHeight);
            // Face the oncoming traffic.
            go.transform.rotation = Quaternion.Euler(0, Geo.Heading(-CityMap.Dirs[d]), 0);
            return p;
        }

        Zone MakeFlood()
        {
            for (int tries = 0; tries < 30; tries++)
            {
                int i, j, d;
                RandomRoadEdge(out i, out j, out d);
                Rect r = EdgeRect(i, j, d, 0f, CityMap.EdgeLength);
                if (r.Contains(gm.player.Pos) || Vector2.Distance(r.center, gm.player.Pos) < 50f) continue;
                if (Overlaps(r)) continue;
                Zone z = new Zone { rect = r, street = city.StreetNameAt(r.center) };
                MeshBatcher mb = new MeshBatcher();
                mb.Box(new Vector3(0, 0.1f, 0), new Vector3(r.width + 2f, 0.2f, r.height + 2f), Quaternion.identity, new Color(0.42f, 0.52f, 0.55f));
                for (int k = 0; k < 10; k++)
                {
                    Vector3 pp = new Vector3(R(-r.width * 0.45f, r.width * 0.45f), 0.21f, R(-r.height * 0.45f, r.height * 0.45f));
                    mb.Box(pp, new Vector3(R(1f, 3f), 0.02f, R(0.2f, 0.4f)), Quaternion.Euler(0, R(0, 180), 0), new Color(0.65f, 0.78f, 0.85f));
                }
                z.go = mb.BuildObject("Banjir", dynRoot, false);
                z.go.transform.position = Geo.X0Z(r.center);
                return z;
            }
            return null;
        }

        Zone MakeRazia()
        {
            for (int tries = 0; tries < 30; tries++)
            {
                int i, j, d;
                RandomRoadEdge(out i, out j, out d);
                float mid = CityMap.EdgeLength * 0.5f;
                Rect r = EdgeRect(i, j, d, mid - 3f, mid + 3f);
                if (Vector2.Distance(r.center, gm.player.Pos) < 60f) continue;
                if (Overlaps(r)) continue;
                Zone z = new Zone { rect = r, street = city.StreetNameAt(r.center) };
                Vector2 dir = CityMap.Dirs[d];
                GameObject go = new GameObject("Razia");
                go.transform.SetParent(dynRoot, false);
                go.transform.position = Geo.X0Z(r.center);
                go.transform.rotation = Quaternion.Euler(0, Geo.Heading(dir), 0);
                MeshBatcher mb = new MeshBatcher();
                // Cones across the street (local x = left/right, z = along).
                for (float x = -9f; x <= 9f; x += 1.5f)
                {
                    mb.BoxBottom(new Vector3(x, 0.12f, -2.6f), new Vector3(0.4f, 0.1f, 0.4f), new Color(0.95f, 0.45f, 0.1f));
                    mb.BoxBottom(new Vector3(x, 0.22f, -2.6f), new Vector3(0.25f, 0.45f, 0.25f), new Color(0.95f, 0.45f, 0.1f));
                    mb.BoxBottom(new Vector3(x, 0.45f, -2.6f), new Vector3(0.27f, 0.08f, 0.27f), Palette.White);
                }
                // Police pickup on the sidewalk.
                Vector3 car = new Vector3(8.5f, CityMap.SidewalkHeight, 0.5f);
                mb.BoxBottom(car + new Vector3(0, 0.3f, 0), new Vector3(1.9f, 0.7f, 4.5f), Palette.White);
                mb.BoxBottom(car + new Vector3(0, 1.0f, 0.6f), new Vector3(1.7f, 0.55f, 1.8f), Palette.Glass);
                mb.BoxBottom(car + new Vector3(0, 0.55f, 0), new Vector3(1.95f, 0.18f, 4.52f), new Color(0.15f, 0.3f, 0.75f));
                // Officers
                for (int k = 0; k < 2; k++)
                {
                    Vector3 op = new Vector3(k == 0 ? -1.5f : 2f, 0f, -1.2f);
                    mb.BoxBottom(op, new Vector3(0.38f, 0.85f, 0.26f), new Color(0.25f, 0.2f, 0.12f));
                    mb.BoxBottom(op + new Vector3(0, 0.85f, 0), new Vector3(0.5f, 0.62f, 0.3f), new Color(0.55f, 0.45f, 0.25f));
                    mb.BoxBottom(op + new Vector3(0, 1.4f, 0), new Vector3(0.62f, 0.06f, 0.4f), new Color(0.9f, 0.85f, 0.2f));
                    mb.Ball(op + new Vector3(0, 1.68f, 0), 0.2f, Palette.Skin);
                }
                // Sign
                mb.BoxBottom(new Vector3(-8.5f, 0f, -3.4f), new Vector3(0.12f, 2.2f, 0.12f), new Color(0.3f, 0.3f, 0.3f));
                mb.Box(new Vector3(-8.5f, 2.6f, -3.4f), new Vector3(3.2f, 1.0f, 0.1f), Quaternion.identity, new Color(0.95f, 0.95f, 0.9f));
                mb.Attach(go, true);
                TextMesh tm = TextKit.Make(go.transform, "RAZIA", new Vector3(-8.5f, 2.6f, -3.47f), Quaternion.identity, 0.7f, new Color(0.8f, 0.1f, 0.1f));
                tm.transform.rotation = Quaternion.identity; // always face the camera
                MeshBatcher la = new MeshBatcher();
                la.Box(car + new Vector3(-0.4f, 1.62f, 0.4f), new Vector3(0.5f, 0.2f, 0.3f), Quaternion.identity, Color.white);
                z.lampA = la.BuildObject("LampA", go.transform, false).GetComponent<Renderer>();
                MeshBatcher lb = new MeshBatcher();
                lb.Box(car + new Vector3(0.4f, 1.62f, 0.4f), new Vector3(0.5f, 0.2f, 0.3f), Quaternion.identity, Color.white);
                z.lampB = lb.BuildObject("LampB", go.transform, false).GetComponent<Renderer>();
                z.go = go;
                return z;
            }
            return null;
        }

        Rect EdgeRect(int i, int j, int d, float from, float to)
        {
            Vector2 a = RoadPoint(i, j, d, from, 0f);
            Vector2 b = RoadPoint(i, j, d, to, 0f);
            float h = CityMap.CorridorHalf;
            return Rect.MinMaxRect(Mathf.Min(a.x, b.x) - (CityMap.IsHorizontal(d) ? 0f : h), Mathf.Min(a.y, b.y) - (CityMap.IsHorizontal(d) ? h : 0f),
                Mathf.Max(a.x, b.x) + (CityMap.IsHorizontal(d) ? 0f : h), Mathf.Max(a.y, b.y) + (CityMap.IsHorizontal(d) ? h : 0f));
        }

        bool Overlaps(Rect r)
        {
            for (int k = 0; k < floods.Count; k++) if (floods[k].rect.Overlaps(r)) return true;
            for (int k = 0; k < razias.Count; k++) if (razias[k].rect.Overlaps(r)) return true;
            return false;
        }

        public void SetRain(bool raining)
        {
            if (raining && rainPuddles.Count == 0)
            {
                for (int k = 0; k < 14; k++) rainPuddles.Add(MakePuddle(true));
            }
            else if (!raining)
            {
                Clear(rainPuddles, h => h.go);
            }
        }

        // ------------------------------------------------------------------ queries used by traffic

        public float FloodFactor(Vector2 p)
        {
            for (int k = 0; k < floods.Count; k++) if (floods[k].rect.Contains(p)) return gm.config.floodSpeedFactor;
            return 1f;
        }

        public bool SpeedBumpAhead(Vector2 p, Vector2 fwd, float dist)
        {
            for (int k = 0; k < bumps.Count; k++)
            {
                SpeedBump b = bumps[k];
                if (Mathf.Abs(Vector2.Dot(fwd, b.roadDir)) < 0.7f) continue;
                Vector2 rel = b.pos - p;
                float along = Vector2.Dot(rel, fwd);
                if (along < -1f || along > dist) continue;
                if (Mathf.Abs(Vector2.Dot(rel, Geo.Left(fwd))) < CityMap.RoadHalf + 0.5f) return true;
            }
            return false;
        }

        public Passenger PassengerAhead(int i, int j, int d, float s, float range)
        {
            Passenger best = null;
            float bestD = range;
            for (int k = 0; k < passengers.Count; k++)
            {
                Passenger p = passengers[k];
                if (p.claimed || p.i != i || p.j != j || p.d != d) continue;
                float g = p.along - s;
                if (g > -0.5f && g < bestD)
                {
                    bestD = g;
                    best = p;
                }
            }
            return best;
        }

        public void BoardPassenger(Passenger p)
        {
            int idx = passengers.IndexOf(p);
            if (idx < 0) return;
            Destroy(p.go);
            passengers.RemoveAt(idx);
        }

        // ------------------------------------------------------------------ per-frame

        public void Tick(float dt)
        {
            if (dt <= 0f) return;
            time += dt;
            if (raziaCooldown > 0f) raziaCooldown -= dt;
            if (splashTimer > 0f) splashTimer -= dt;

            // Passengers wave, and get replaced (off-screen) after boarding.
            for (int k = 0; k < passengers.Count; k++)
            {
                Passenger p = passengers[k];
                float a = Mathf.Sin(time * 7f + p.phase) * 35f;
                p.arm.localRotation = Quaternion.Euler(0, 0, -15f + a);
            }
            if (passengers.Count < passengerTarget && rng.NextDouble() < dt * 0.5) passengers.Add(MakePassenger());

            // Street food steam.
            for (int k = 0; k < gerobaks.Count; k++)
            {
                Obstacle o = gerobaks[k];
                o.steamTimer -= dt;
                if (o.steamTimer <= 0f)
                {
                    o.steamTimer = 0.25f;
                    if ((o.pos - gm.player.Pos).sqrMagnitude < 60f * 60f)
                        gm.fx.Emit(FxKind.Steam, o.go.transform.TransformPoint(new Vector3(0, 1.25f, -0.65f)), 1);
                }
            }

            TickCats(dt);
            TickChickens(dt);
            TickKids(dt);

            for (int k = 0; k < razias.Count; k++)
            {
                bool flip = Mathf.Repeat(time, 0.5f) < 0.25f;
                razias[k].lampA.sharedMaterial = flip ? raziaRed : raziaOff;
                razias[k].lampB.sharedMaterial = flip ? raziaOff : raziaBlue;
            }
        }

        void TickCats(float dt)
        {
            if (gm.State == GameState.Playing && level != null)
            {
                catTimer -= dt;
                if (catTimer <= 0f)
                {
                    catTimer = level.catInterval * R(0.7f, 1.3f);
                    SpawnCat();
                }
            }
            for (int k = cats.Count - 1; k >= 0; k--)
            {
                Critter c = cats[k];
                c.timer -= dt;
                if (c.flung)
                {
                    c.flyTime += dt;
                    c.pos += c.vel * dt;
                    c.y = Mathf.Max(0f, 6f * c.flyTime - 12f * c.flyTime * c.flyTime);
                    c.go.transform.Rotate(0, 720f * dt, 0);
                }
                else
                {
                    c.pos += c.vel * dt;
                    c.y = Mathf.Abs(Mathf.Sin(time * 14f)) * 0.08f;
                }
                c.go.transform.position = Geo.X0Z(c.pos, c.y);
                if (c.timer <= 0f)
                {
                    Destroy(c.go);
                    cats.RemoveAt(k);
                }
            }
        }

        void SpawnCat()
        {
            PlayerBikeController p = gm.player;
            Vector2 fwd = p.Forward;
            Vector2 at = p.Pos + fwd * R(20f, 30f);
            if (city.SurfaceAt(at) != Surface.Road || city.InIntersection(at)) return;
            bool horizontal;
            city.StreetOffset(at, out horizontal);
            Vector2 axis = horizontal ? new Vector2(1, 0) : new Vector2(0, 1);
            Vector2 across = Geo.Left(axis);
            // Snap to the street and start from one sidewalk.
            float off;
            Vector2 center;
            if (horizontal)
            {
                int j = Mathf.Clamp(Mathf.RoundToInt(at.y / CityMap.Pitch), 0, city.nz - 1);
                center = new Vector2(at.x, j * CityMap.Pitch);
            }
            else
            {
                int i = Mathf.Clamp(Mathf.RoundToInt(at.x / CityMap.Pitch), 0, city.nx - 1);
                center = new Vector2(i * CityMap.Pitch, at.y);
            }
            float sideSign = rng.Next(2) == 0 ? 1f : -1f;
            off = 9f * sideSign;
            float speed = R(4.5f, 6.5f);
            Critter c = new Critter { pos = center + across * off, vel = -across * sideSign * speed, timer = 18f / speed + 0.5f };
            MeshBatcher mb = new MeshBatcher();
            Color[] furs = { new Color(0.95f, 0.6f, 0.2f), new Color(0.95f, 0.95f, 0.92f), new Color(0.15f, 0.15f, 0.15f), new Color(0.6f, 0.55f, 0.5f) };
            Color fur = furs[rng.Next(furs.Length)];
            mb.BoxBottom(new Vector3(0, 0.12f, 0), new Vector3(0.24f, 0.22f, 0.55f), fur);
            mb.BoxBottom(new Vector3(0, 0.25f, 0.32f), new Vector3(0.22f, 0.2f, 0.2f), fur);
            mb.BoxBottom(new Vector3(-0.07f, 0.45f, 0.35f), new Vector3(0.06f, 0.08f, 0.05f), fur);
            mb.BoxBottom(new Vector3(0.07f, 0.45f, 0.35f), new Vector3(0.06f, 0.08f, 0.05f), fur);
            mb.Beam(new Vector3(0, 0.3f, -0.27f), new Vector3(0, 0.6f, -0.45f), 0.06f, fur);
            c.go = mb.BuildObject("Kucing", dynRoot, false);
            c.go.transform.rotation = Quaternion.Euler(0, Geo.Heading(c.vel), 0);
            cats.Add(c);
        }

        void TickChickens(float dt)
        {
            Vector2 pp = gm.player.Pos;
            for (int k = 0; k < chickens.Count; k++)
            {
                Critter c = chickens[k];
                Vector2 away = c.pos - pp;
                float d = away.magnitude;
                Vector2 vel;
                if (c.flung)
                {
                    c.flyTime += dt;
                    c.y = Mathf.Max(0f, 4f * c.flyTime - 9f * c.flyTime * c.flyTime);
                    if (c.flyTime > 0.5f) { c.flung = false; c.y = 0f; }
                    vel = c.vel;
                }
                else if (d < 5f && gm.player.Speed > 3f)
                {
                    vel = away / Mathf.Max(d, 0.1f) * 4.5f; // scatter!
                    c.timer = 0.5f;
                }
                else
                {
                    c.timer -= dt;
                    if (c.timer <= 0f)
                    {
                        c.timer = R(0.8f, 2.5f);
                        c.target = c.home + new Vector2(R(-6f, 6f), R(-6f, 6f));
                    }
                    Vector2 to = c.target - c.pos;
                    vel = to.sqrMagnitude > 0.05f ? to.normalized * 1.2f : Vector2.zero;
                }
                Vector2 np = c.pos + vel * dt;
                if (city.SurfaceAt(np) == Surface.Gang || city.SurfaceAt(np) == Surface.Sidewalk) c.pos = np;
                else c.target = c.home;
                c.go.transform.position = Geo.X0Z(c.pos, c.y + Mathf.Abs(Mathf.Sin(time * 12f + k)) * (vel.sqrMagnitude > 0.1f ? 0.05f : 0f));
                if (vel.sqrMagnitude > 0.05f) c.go.transform.rotation = Quaternion.Euler(0, Geo.Heading(vel), 0);
            }
        }

        void TickKids(float dt)
        {
            for (int k = 0; k < kids.Count; k++)
            {
                Critter c = kids[k];
                bool vertical = c.bounds.height > c.bounds.width;
                float t = time * 0.8f + c.timer;
                Vector2 along = vertical ? new Vector2(0, 1) : new Vector2(1, 0);
                Vector2 across = Geo.Left(along);
                Vector2 p = c.home + along * Mathf.Sin(t * 0.7f) * 4f + across * Mathf.Sin(t * 1.7f) * 1.2f;
                Vector2 v = (p - c.pos) / Mathf.Max(dt, 0.0001f);
                c.pos = p;
                c.go.transform.position = Geo.X0Z(c.pos, Mathf.Abs(Mathf.Sin(time * 9f + k)) * 0.12f);
                if (v.sqrMagnitude > 0.01f) c.go.transform.rotation = Quaternion.Euler(0, Geo.Heading(v), 0);
            }
        }

        // ------------------------------------------------------------------ player interaction

        public void CheckPlayer(PlayerBikeController p, float dt)
        {
            if (!p.Active) return;
            Vector2 pos = p.Pos;
            float r = gm.config.playerRadius;
            bool grounded = !p.Airborne;

            if (grounded && p.Speed > 3f)
            {
                for (int list = 0; list < 2; list++)
                {
                    List<CircleHazard> src = list == 0 ? puddles : rainPuddles;
                    for (int k = 0; k < src.Count; k++)
                    {
                        CircleHazard h = src[k];
                        if ((h.pos - pos).sqrMagnitude < h.radius * h.radius)
                        {
                            if (p.StartSlide() && splashTimer <= 0f)
                            {
                                splashTimer = 0.4f;
                                gm.fx.Emit(FxKind.Splash, Geo.X0Z(pos, 0.1f), 14);
                                gm.audioManager.Play("splash", 0.6f, 1f);
                            }
                        }
                    }
                }
            }

            for (int k = 0; k < potholes.Count; k++)
            {
                CircleHazard h = potholes[k];
                if (h.cooldown > 0f) { h.cooldown -= dt; continue; }
                if (grounded && (h.pos - pos).sqrMagnitude < (h.radius + 0.15f) * (h.radius + 0.15f))
                {
                    h.cooldown = 1f;
                    p.HitPothole();
                    gm.OnPothole(pos);
                }
            }

            for (int k = 0; k < bumps.Count; k++)
            {
                SpeedBump b = bumps[k];
                if (b.cooldown > 0f) { b.cooldown -= dt; continue; }
                Vector2 rel = pos - b.pos;
                if (Mathf.Abs(Vector2.Dot(rel, b.roadDir)) < 0.5f && Mathf.Abs(Vector2.Dot(rel, Geo.Left(b.roadDir))) < CityMap.RoadHalf)
                {
                    b.cooldown = 0.8f;
                    if (grounded) p.HitSpeedBump();
                }
            }

            for (int k = 0; k < gerobaks.Count; k++)
            {
                Obstacle o = gerobaks[k];
                Vector2 closest;
                bool inside = Geo.ClosestOnObb(o.pos, o.fwd, o.halfLength, o.halfWidth, pos, out closest);
                Vector2 delta = pos - closest;
                float dist = delta.magnitude;
                if (inside || dist < r)
                {
                    Vector2 n = dist > 0.0001f ? delta / dist : -o.fwd;
                    if (inside) n = -n;
                    gm.OnPlayerHitObstacle(n, closest, Vector2.zero, "GEROBAK!", null);
                }
            }

            for (int k = 0; k < cats.Count; k++)
            {
                Critter c = cats[k];
                if (c.flung) continue;
                if ((c.pos - pos).sqrMagnitude < (r + 0.35f) * (r + 0.35f))
                {
                    c.flung = true;
                    c.vel = (c.pos - pos).normalized * 5f + p.Velocity * 0.3f;
                    c.timer = 1.2f;
                    gm.OnCritterHit(Geo.X0Z(c.pos, 0.5f), "MEOW!", "meow", FxKind.Dust, false);
                }
            }

            for (int k = 0; k < chickens.Count; k++)
            {
                Critter c = chickens[k];
                if (c.flung) continue;
                if ((c.pos - pos).sqrMagnitude < (r + 0.3f) * (r + 0.3f))
                {
                    c.flung = true;
                    c.flyTime = 0f;
                    c.vel = (c.pos - pos).normalized * 4f;
                    gm.OnCritterHit(Geo.X0Z(c.pos, 0.5f), "PETOK!", "cluck", FxKind.Feather, false);
                }
            }

            for (int k = 0; k < kids.Count; k++)
            {
                Critter c = kids[k];
                if (c.cooldown > 0f) { c.cooldown -= dt; continue; }
                if ((c.pos - pos).sqrMagnitude < (r + 0.4f) * (r + 0.4f) && p.Speed > 1f)
                {
                    c.cooldown = 2.5f;
                    p.HardStop((pos - c.pos).normalized);
                    gm.OnCritterHit(Geo.X0Z(c.pos, 1.2f), "AWAS ADA ANAK!", "horn", FxKind.Dust, true);
                }
            }

            PlayerInFlood = false;
            for (int k = 0; k < floods.Count; k++)
            {
                if (floods[k].rect.Contains(pos))
                {
                    PlayerInFlood = true;
                    if (p.Speed > 2f && rng.NextDouble() < dt * 12f) gm.fx.Emit(FxKind.Splash, Geo.X0Z(pos, 0.2f), 3);
                }
            }

            if (raziaCooldown <= 0f)
            {
                for (int k = 0; k < razias.Count; k++)
                {
                    if (razias[k].rect.Contains(pos))
                    {
                        raziaCooldown = gm.config.raziaStopTime + 4f;
                        p.Freeze(gm.config.raziaStopTime);
                        gm.OnRazia(Geo.X0Z(pos, 1.5f));
                    }
                }
            }
        }
    }
}
