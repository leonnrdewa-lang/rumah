using System.Collections.Generic;
using UnityEngine;

namespace OjolRush
{
    /// <summary>
    /// Spawns and despawns traffic around the player, computes each vehicle's obstacle gap
    /// (vehicles, the player, red lights, angkot passengers) and drives the TrafficVehicle AI.
    /// </summary>
    public class TrafficManager : MonoBehaviour
    {
        public readonly List<TrafficVehicle> vehicles = new List<TrafficVehicle>();
        public TrafficLights lights;

        GameManager gm;
        CityMap city;
        System.Random rng;
        PoolManager pools;
        Transform root;
        float time;
        int targetCount;
        RushLevelConfig level;
        float spawnTimer;
        float chorusTimer;

        // Signal heads: one renderer per approach per intersection.
        class SignalHead { public int i, j; public bool horizontal; public Renderer lamp; public LightState shown = (LightState)(-1); }
        readonly List<SignalHead> heads = new List<SignalHead>();
        Material lampGreen, lampYellow, lampRed;

        const float SpawnMin = 40f;
        const float SpawnMax = 85f;
        const float DespawnDist = 100f;

        public void Init(GameManager game, CityMap map, System.Random random, PoolManager poolManager)
        {
            gm = game;
            city = map;
            rng = random;
            pools = poolManager;
            root = new GameObject("Traffic").transform;
            root.SetParent(transform, false);
            lights = new TrafficLights(city.nx, city.nz, rng);
            lampGreen = Mats.Get(new Color(0.2f, 1f, 0.35f), true);
            lampYellow = Mats.Get(new Color(1f, 0.8f, 0.1f), true);
            lampRed = Mats.Get(new Color(1f, 0.12f, 0.1f), true);
            BuildSignals();
        }

        void BuildSignals()
        {
            Transform sroot = new GameObject("Signals").transform;
            sroot.SetParent(transform, false);
            MeshBatcher poles = new MeshBatcher();
            for (int i = 0; i < city.nx; i++)
            {
                for (int j = 0; j < city.nz; j++)
                {
                    for (int d = 0; d < 4; d++)
                    {
                        // Signal for traffic arriving in direction d, placed on its left curb before the junction.
                        int pi, pj;
                        CityMap.Step(i, j, CityMap.Opposite(d), out pi, out pj);
                        if (!city.HasNode(pi, pj)) continue;
                        Vector2 dv = CityMap.Dirs[d];
                        Vector2 p = city.NodePos(i, j) - dv * (CityMap.CorridorHalf + 0.6f) + Geo.Left(dv) * (CityMap.RoadHalf + 1.2f);
                        Vector3 p3 = Geo.X0Z(p, CityMap.SidewalkHeight);
                        poles.BoxBottom(p3, new Vector3(0.18f, 3.6f, 0.18f), new Color(0.25f, 0.27f, 0.25f));
                        Vector3 armEnd = p3 + new Vector3(-Geo.Left(dv).x, 0, -Geo.Left(dv).y) * 2.2f + Vector3.up * 3.6f;
                        poles.Beam(p3 + Vector3.up * 3.5f, armEnd, 0.14f, new Color(0.25f, 0.27f, 0.25f));
                        poles.Box(armEnd + Vector3.up * 0.05f, new Vector3(0.6f, 0.45f, 0.6f), Quaternion.identity, new Color(0.12f, 0.12f, 0.12f));

                        MeshBatcher lamp = new MeshBatcher();
                        lamp.Box(armEnd + Vector3.up * 0.38f, new Vector3(0.5f, 0.22f, 0.5f), Quaternion.identity, Color.white);
                        GameObject lg = lamp.BuildObject("Lamp", sroot, false);
                        SignalHead h = new SignalHead { i = i, j = j, horizontal = CityMap.IsHorizontal(d), lamp = lg.GetComponent<Renderer>() };
                        heads.Add(h);
                    }
                }
            }
            poles.BuildObject("SignalPoles", sroot);
        }

        public void ResetTraffic(RushLevelConfig lvl)
        {
            for (int i = vehicles.Count - 1; i >= 0; i--) Despawn(i);
            level = lvl;
            SetLevel(lvl);
            // Initial fill: allow spawns closer (but not on top of the player).
            for (int k = 0; k < targetCount * 15 && vehicles.Count < targetCount; k++) TrySpawn(14f, SpawnMax, false);
        }

        public void SetLevel(RushLevelConfig lvl)
        {
            level = lvl;
            targetCount = lvl.trafficCount;
            lights.green = lvl.lightGreenTime;
        }

        VehicleType PickType()
        {
            float total = level.car + level.angkot + level.bajaj + level.bus + level.motorbike;
            float r = (float)rng.NextDouble() * total;
            if ((r -= level.car) < 0) return VehicleType.Car;
            if ((r -= level.angkot) < 0) return VehicleType.Angkot;
            if ((r -= level.bajaj) < 0) return VehicleType.Bajaj;
            if ((r -= level.bus) < 0) return VehicleType.Bus;
            return VehicleType.Motorbike;
        }

        bool TrySpawn(float minDist, float maxDist, bool mustBeHidden)
        {
            Vector2 center = gm.player.Pos;
            int i = rng.Next(city.nx), j = rng.Next(city.nz), d = rng.Next(4);
            if (!city.HasEdge(i, j, d)) return false;
            VehicleType t = PickType();
            int ln = rng.Next(CityMap.LanesPerDir);
            if (t == VehicleType.Angkot && rng.NextDouble() < 0.7) ln = CityMap.LanesPerDir - 1;
            if (t == VehicleType.Bajaj && rng.NextDouble() < 0.6) ln = CityMap.LanesPerDir - 1;
            float along = (float)rng.NextDouble() * (CityMap.EdgeLength - 6f) + 3f;
            Vector2 a, b;
            city.EdgeLane(i, j, d, ln, out a, out b);
            Vector2 p = a + CityMap.Dirs[d] * along;
            float dist = Vector2.Distance(p, center);
            if (dist < minDist || dist > maxDist) return false;
            if (mustBeHidden && gm.cameraManager.IsVisible(Geo.X0Z(p), 6f)) return false;
            VehicleSpec sp = VehicleFactory.Spec(t);
            for (int k = 0; k < vehicles.Count; k++)
            {
                TrafficVehicle o = vehicles[k];
                float clear = sp.length * 0.5f + o.HalfLength + 3f;
                if ((o.pos - p).sqrMagnitude < clear * clear) return false;
            }
            string key = "veh_" + t;
            VehicleType tt = t;
            Pool<TrafficVehicle> pool = pools.For<TrafficVehicle>(key, () => CreateVehicle(tt));
            TrafficVehicle v = pool.Get();
            v.Place(city, i, j, d, ln, along);
            v.speed = v.cruise * 0.6f;
            vehicles.Add(v);
            return true;
        }

        TrafficVehicle CreateVehicle(VehicleType t)
        {
            VehicleVisual vis = VehicleFactory.Build(t, rng, root);
            TrafficVehicle v = vis.root.AddComponent<TrafficVehicle>();
            v.Setup(t, vis, rng);
            return v;
        }

        void Despawn(int index)
        {
            TrafficVehicle v = vehicles[index];
            vehicles.RemoveAt(index);
            if (v.stopFor != null)
            {
                v.stopFor.claimed = false;
                v.stopFor = null;
            }
            v.stopTime = 0f;
            pools.For<TrafficVehicle>("veh_" + v.type, () => CreateVehicle(v.type)).Release(v);
        }

        public void Tick(float dt)
        {
            if (dt <= 0f) return;
            time += dt;
            UpdateSignals();

            Vector2 pp = gm.player.Pos;
            // Despawn far & hidden vehicles, spawn new ones off-screen.
            for (int i = vehicles.Count - 1; i >= 0; i--)
            {
                TrafficVehicle v = vehicles[i];
                float d2 = (v.pos - pp).sqrMagnitude;
                bool tooMany = vehicles.Count > targetCount + 4 && d2 > SpawnMin * SpawnMin;
                if ((d2 > DespawnDist * DespawnDist || tooMany || v.stuckTime > 25f) && !gm.cameraManager.IsVisible(v.transform.position, 6f))
                    Despawn(i);
            }
            spawnTimer -= dt;
            if (spawnTimer <= 0f && vehicles.Count < targetCount)
            {
                spawnTimer = 0.05f;
                for (int k = 0; k < 6 && vehicles.Count < targetCount; k++) TrySpawn(SpawnMin, SpawnMax, true);
            }

            float speedMul = level != null ? level.trafficSpeedMultiplier : 1f;
            for (int i = 0; i < vehicles.Count; i++)
            {
                TrafficVehicle v = vehicles[i];
                bool hard;
                float limit;
                float gap = SenseGap(v, dt, out hard, out limit);
                limit *= speedMul * gm.hazards.FloodFactor(v.pos);
                if (gm.hazards.SpeedBumpAhead(v.pos, v.fwd, 9f)) limit = Mathf.Min(limit, 4.5f);
                v.Tick(dt, gap, limit, hard, time);
                MaybeChangeLane(v, dt);
            }
            HonkChorus(dt);
        }

        void UpdateSignals()
        {
            for (int k = 0; k < heads.Count; k++)
            {
                SignalHead h = heads[k];
                LightState st = lights.State(h.i, h.j, h.horizontal, time);
                if (st == h.shown) continue;
                h.shown = st;
                h.lamp.sharedMaterial = st == LightState.Green ? lampGreen : (st == LightState.Yellow ? lampYellow : lampRed);
            }
        }

        /// <summary>Distance to the nearest thing this vehicle must not hit, plus a speed limit.</summary>
        float SenseGap(TrafficVehicle v, float dt, out bool hard, out float limit)
        {
            hard = false;
            limit = 999f;
            float gap = TrafficSensing.VehicleGap(v, vehicles);

            // The player: traffic reacts late (they are used to ojol cutting in) and honks.
            PlayerBikeController p = gm.player;
            if (p.Active || gm.State == GameState.GameOver)
            {
                float g = TrafficSensing.PlayerGap(v, p.Pos);
                if (g < gap) gap = g;
                if (g < 4f && v.speed < 3f && v.honkCooldown <= 0f && rng.NextDouble() < 0.5)
                {
                    v.honkCooldown = 2.5f + (float)rng.NextDouble() * 2f;
                    gm.audioManager.PlayHorn(v.transform.position, v.type);
                }
            }

            gap = Mathf.Min(gap, TrafficSensing.LightGap(v, lights, time));
            gap = Mathf.Min(gap, TrafficSensing.YieldGap(v, vehicles, lights, time));
            if (v.type == VehicleType.Motorbike || v.type == VehicleType.Bajaj)
            {
                v.blockLeft = TrafficSensing.SideBlocked(v, vehicles, 1f);
                v.blockRight = TrafficSensing.SideBlocked(v, vehicles, -1f);
            }

            // Angkot: stop abruptly next to a waving passenger.
            if (v.type == VehicleType.Angkot)
            {
                if (v.stopTime > 0f)
                {
                    v.stopTime -= dt;
                    limit = 0f;
                    hard = true;
                    if (v.stopTime <= 0f && v.stopFor != null)
                    {
                        gm.hazards.BoardPassenger(v.stopFor);
                        v.stopFor = null;
                    }
                }
                else if (!v.turning && v.lane == CityMap.LanesPerDir - 1)
                {
                    Passenger ps = gm.hazards.PassengerAhead(v.ni, v.nj, v.dir, v.s, 16f);
                    if (ps != null)
                    {
                        float g = ps.along - v.s - 0.5f;
                        if (g < gap)
                        {
                            gap = g + 1.6f;
                            hard = true;
                        }
                        if (g < 1.2f && v.speed < 1f)
                        {
                            v.stopTime = 2.2f + (float)rng.NextDouble();
                            v.stopFor = ps;
                            ps.claimed = true;
                            if (Vector2.Distance(v.pos, p.Pos) < 30f) gm.audioManager.Play("shout", 0.7f, 0.9f + (float)rng.NextDouble() * 0.3f);
                        }
                    }
                }
            }

            // Deadlock breaker: after waiting a while (not at a light), squeeze through.
            if (TrafficSensing.BreakDeadlock(v) && v.honkCooldown <= 0f && Vector2.Distance(v.pos, p.Pos) < 40f)
            {
                v.honkCooldown = 3f;
                gm.audioManager.PlayHorn(v.transform.position, v.type);
            }
            return gap;
        }

        void MaybeChangeLane(TrafficVehicle v, float dt)
        {
            if (!v.CanChangeLane()) return;
            float rate = v.spec.laneChangeRate * (v.braking ? 4f : 1f);
            if (rng.NextDouble() > rate * dt) return;
            int to = v.lane == 0 ? 1 : 0;
            if (TrafficSensing.LaneIsFree(v, vehicles, city, to)) v.StartLaneChange(to);
        }

        void HonkChorus(float dt)
        {
            if (level == null) return;
            chorusTimer -= dt;
            if (chorusTimer > 0f) return;
            chorusTimer = 0.4f;
            int jammed = 0;
            TrafficVehicle candidate = null;
            Vector2 pp = gm.player.Pos;
            for (int i = 0; i < vehicles.Count; i++)
            {
                TrafficVehicle v = vehicles[i];
                if (v.speed < 1.5f && (v.pos - pp).sqrMagnitude < 45f * 45f)
                {
                    jammed++;
                    if (v.honkCooldown <= 0f && (candidate == null || rng.NextDouble() < 0.3)) candidate = v;
                }
            }
            float chance = level.honkRate * 0.4f * Mathf.Min(1f, jammed / 6f);
            if (candidate != null && rng.NextDouble() < chance)
            {
                candidate.honkCooldown = 2f + (float)rng.NextDouble() * 3f;
                gm.audioManager.PlayHorn(candidate.transform.position, candidate.type);
            }
        }

        public LightState SignalFor(int i, int j, bool horizontal) { return lights.State(i, j, horizontal, time); }
    }
}
