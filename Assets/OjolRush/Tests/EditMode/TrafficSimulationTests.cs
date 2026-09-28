using System.Collections.Generic;
using NUnit.Framework;
using UnityEngine;

namespace OjolRush.Tests
{
    /// <summary>
    /// Headless traffic simulation: spawns a district full of vehicles and runs the real AI for a few
    /// minutes of game time. Guards against NaNs, vehicles leaving the road, permanent gridlock and
    /// vehicles driving through each other.
    /// </summary>
    public class TrafficSimulationTests
    {
        readonly List<Object> spawned = new List<Object>();

        [TearDown]
        public void TearDown()
        {
#if UNITY_5_3_OR_NEWER
            foreach (Object o in spawned) if (o != null) Object.DestroyImmediate(o);
#endif
            spawned.Clear();
        }

        TrafficVehicle MakeVehicle(VehicleType t, System.Random rng)
        {
#if UNITY_5_3_OR_NEWER
            GameObject go = new GameObject("SimVehicle");
            spawned.Add(go);
            TrafficVehicle v = go.AddComponent<TrafficVehicle>();
            VehicleVisual vis = new VehicleVisual { root = go, brake = Child(go, "Brake"), blinkLeft = Child(go, "BlinkL"), blinkRight = Child(go, "BlinkR") };
#else
            TrafficVehicle v = new TrafficVehicle();
            VehicleVisual vis = new VehicleVisual { brake = new Renderer(), blinkLeft = new Renderer(), blinkRight = new Renderer() };
#endif
            v.Setup(t, vis, rng);
            return v;
        }

#if UNITY_5_3_OR_NEWER
        static Renderer Child(GameObject parent, string name)
        {
            GameObject c = new GameObject(name);
            c.transform.SetParent(parent.transform, false);
            return c.AddComponent<MeshRenderer>();
        }
#endif

        static bool Overlap(TrafficVehicle a, TrafficVehicle b)
        {
            Vector2[] axes = { a.fwd, Geo.Left(a.fwd), b.fwd, Geo.Left(b.fwd) };
            for (int i = 0; i < axes.Length; i++)
            {
                Vector2 ax = axes[i];
                float ra = Mathf.Abs(Vector2.Dot(a.fwd, ax)) * a.HalfLength + Mathf.Abs(Vector2.Dot(Geo.Left(a.fwd), ax)) * a.HalfWidth;
                float rb = Mathf.Abs(Vector2.Dot(b.fwd, ax)) * b.HalfLength + Mathf.Abs(Vector2.Dot(Geo.Left(b.fwd), ax)) * b.HalfWidth;
                if (Mathf.Abs(Vector2.Dot(b.pos - a.pos, ax)) > ra + rb - 0.15f) return false;
            }
            return true;
        }

        List<TrafficVehicle> Spawn(CityMap city, System.Random rng, int count)
        {
            VehicleType[] types = { VehicleType.Car, VehicleType.Car, VehicleType.Angkot, VehicleType.Bajaj, VehicleType.Bus, VehicleType.Motorbike, VehicleType.Motorbike, VehicleType.Motorbike };
            List<TrafficVehicle> list = new List<TrafficVehicle>();
            for (int tries = 0; tries < 20000 && list.Count < count; tries++)
            {
                int i = rng.Next(city.nx), j = rng.Next(city.nz), d = rng.Next(4);
                if (!city.HasEdge(i, j, d)) continue;
                VehicleType t = types[rng.Next(types.Length)];
                int lane = rng.Next(CityMap.LanesPerDir);
                float along = (float)rng.NextDouble() * 34f + 3f;
                Vector2 a, b;
                city.EdgeLane(i, j, d, lane, out a, out b);
                Vector2 p = a + CityMap.Dirs[d] * along;
                VehicleSpec sp = VehicleSpec.For(t);
                bool free = true;
                foreach (TrafficVehicle o in list)
                {
                    float c = sp.length * 0.5f + o.HalfLength + 3f;
                    if ((o.pos - p).sqrMagnitude < c * c) { free = false; break; }
                }
                if (!free) continue;
                TrafficVehicle v = MakeVehicle(t, rng);
                v.Place(city, i, j, d, lane, along);
                v.speed = v.cruise * 0.6f;
                list.Add(v);
            }
            return list;
        }

        void Step(List<TrafficVehicle> vs, CityMap city, TrafficLights lights, System.Random rng, float dt, float time)
        {
            for (int k = 0; k < vs.Count; k++)
            {
                TrafficVehicle v = vs[k];
                float gap = Mathf.Min(TrafficSensing.VehicleGap(v, vs), TrafficSensing.LightGap(v, lights, time));
                gap = Mathf.Min(gap, TrafficSensing.YieldGap(v, vs, lights, time));
                if (v.type == VehicleType.Motorbike || v.type == VehicleType.Bajaj)
                {
                    v.blockLeft = TrafficSensing.SideBlocked(v, vs, 1f);
                    v.blockRight = TrafficSensing.SideBlocked(v, vs, -1f);
                }
                TrafficSensing.BreakDeadlock(v);
                v.Tick(dt, gap, 999f, false, time);
                if (v.CanChangeLane() && rng.NextDouble() < v.spec.laneChangeRate * dt)
                {
                    int to = v.lane == 0 ? 1 : 0;
                    if (TrafficSensing.LaneIsFree(v, vs, city, to)) v.StartLaneChange(to);
                }
            }
        }

        [Test]
        public void Traffic_FlowsWithoutGridlockOrCrashes()
        {
            CityMap city = new CityMap();
            System.Random rng = new System.Random(5);
            TrafficLights lights = new TrafficLights(city.nx, city.nz, rng);
            List<TrafficVehicle> vs = Spawn(city, rng, 60);
            Assert.AreEqual(60, vs.Count);

            float dt = 0.05f, time = 0f;
            int steps = 2400; // two minutes
            float[] travelled = new float[vs.Count];
            Vector2[] last = new Vector2[vs.Count];
            for (int k = 0; k < vs.Count; k++) last[k] = vs[k].pos;
            long overlapPairs = 0;
            int offRoad = 0;
            for (int s = 0; s < steps; s++)
            {
                time += dt;
                Step(vs, city, lights, rng, dt, time);
                for (int k = 0; k < vs.Count; k++)
                {
                    TrafficVehicle v = vs[k];
                    Assert.IsFalse(float.IsNaN(v.pos.x) || float.IsNaN(v.pos.y) || float.IsNaN(v.speed), "NaN in vehicle state");
                    if (city.SurfaceAt(v.pos) != Surface.Road) offRoad++;
                    travelled[k] += (v.pos - last[k]).magnitude;
                    last[k] = v.pos;
                }
                if (s % 4 == 0)
                    for (int a = 0; a < vs.Count; a++)
                        for (int b = a + 1; b < vs.Count; b++)
                            if (Overlap(vs[a], vs[b])) overlapPairs++;
            }
            for (int k = 0; k < vs.Count; k++)
                Assert.Greater(travelled[k], 150f, vs[k].type + " barely moved - gridlock?");
            Assert.Less(offRoad, steps * vs.Count / 1000, "vehicles leave the road");
            float overlapPerSample = overlapPairs / (steps / 4f);
            Assert.Less(overlapPerSample, 0.35f, "vehicles drive through each other too often");
        }

        [Test]
        public void Traffic_StopsForRedLights()
        {
            CityMap city = new CityMap();
            System.Random rng = new System.Random(9);
            TrafficLights lights = new TrafficLights(city.nx, city.nz, rng);
            TrafficVehicle car = MakeVehicle(VehicleType.Car, rng);
            car.Place(city, 1, 1, 0, 0, 5f);
            // Force a straight exit so the light applies (left turns may go on red).
            while (car.nextDir != car.dir) car.Place(city, 1, 1, 0, 0, 5f);
            // Find a moment when the east-west light at node (2,1) is red and stays red for a while.
            float t = 0f;
            while (lights.State(2, 1, true, t) != LightState.Red || lights.State(2, 1, true, t + 6f) != LightState.Red) t += 0.25f;
            car.speed = car.cruise;
            for (int s = 0; s < 120; s++)
            {
                float gap = TrafficSensing.LightGap(car, lights, t);
                car.Tick(0.05f, gap, 999f, false, t);
                t += 0.05f;
            }
            Assert.IsFalse(car.turning, "car ran the red light");
            Assert.Less(car.speed, 0.5f);
            Assert.Greater(car.DistanceToStopLine() - car.HalfLength, -1f);
        }
    }
}
