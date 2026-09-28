using UnityEngine;

namespace OjolRush
{
    /// <summary>
    /// Traffic AI for one vehicle: follows lanes on the street grid, turns at intersections along
    /// bezier curves, obeys (mostly) traffic lights, and is deliberately imperfect per type.
    /// Movement is ticked by TrafficManager, which also computes the obstacle gap ahead.
    /// </summary>
    public class TrafficVehicle : MonoBehaviour
    {
        public VehicleType type;
        public VehicleSpec spec;
        public VehicleVisual visual;

        // Current edge: leaving node (ni,nj) in direction dir, on lane.
        public int ni, nj, dir, lane;
        public bool turning;
        public float s;
        public float pathLen;
        Vector2 la, lb;             // lane segment endpoints
        Vector2 tp0, tp1, tp2;      // turn bezier
        public int nextDir, nextLane;

        public float speed;
        public float cruise;
        public Vector2 pos;
        public Vector2 fwd = Vector2.up;
        public float lat;           // lateral offset from lane centre (left positive)
        float latVel;

        // Lane change
        public int laneChangeTo = -1;
        float laneChangeBlink;

        // State
        public bool braking;
        public float stuckTime;
        public float ghostTime;
        public float bumpedTime;
        public float honkCooldown;
        public float stopTime;          // angkot passenger stop
        public Passenger stopFor;
        public bool waitingAtLight;
        public bool nearMissArmed = true;
        public bool nearPlayerClose;
        /// <summary>Set by the traffic manager: someone is right beside us (blocks lateral weaving).</summary>
        public bool blockLeft, blockRight;
        float weaveTarget, weaveTimer, phase;
        int blinkSide;               // -1 left, 1 right
        bool brakeShown;
        Material brakeOn, brakeOff;
        System.Random rng;
        CityMap city;

        public float HalfLength { get { return spec.length * 0.5f; } }
        public float HalfWidth { get { return spec.width * 0.5f; } }
        public Vector2 Velocity { get { return fwd * speed; } }
        public bool IsTurningLeftNext { get { return nextDir == CityMap.LeftOf(dir); } }
        public bool IsStraightNext { get { return nextDir == dir; } }

        public void Setup(VehicleType t, VehicleVisual v, System.Random random)
        {
            type = t;
            spec = VehicleSpec.For(t);
            visual = v;
            rng = random;
            brakeOn = Mats.Get(Palette.BrakeOn, true);
            brakeOff = Mats.Get(Palette.BrakeOff);
        }

        public void Place(CityMap map, int i, int j, int d, int ln, float along)
        {
            city = map;
            ni = i; nj = j; dir = d; lane = ln;
            turning = false;
            s = along;
            lat = 0f; latVel = 0f;
            laneChangeTo = -1;
            speed = 0f;
            cruise = spec.maxSpeed * (0.85f + (float)rng.NextDouble() * 0.25f);
            stuckTime = ghostTime = bumpedTime = stopTime = 0f;
            honkCooldown = (float)rng.NextDouble() * 3f;
            stopFor = null;
            nearMissArmed = true;
            phase = (float)rng.NextDouble() * 10f;
            weaveTarget = 0f; weaveTimer = 0f;
            blinkSide = 0;
            brakeShown = true;
            SetBrake(false);
            SetupEdge();
            ChooseNext();
            UpdatePose(0f);
        }

        void SetupEdge()
        {
            city.EdgeLane(ni, nj, dir, lane, out la, out lb);
            pathLen = Vector2.Distance(la, lb);
        }

        void ChooseNext()
        {
            int ex, ez;
            CityMap.Step(ni, nj, dir, out ex, out ez);
            // Candidate exits at the node we are driving to.
            int[] cand = new int[3];
            float[] w = new float[3];
            int n = 0;
            float total = 0f;
            for (int k = 0; k < 3; k++)
            {
                int d = k == 0 ? dir : (k == 1 ? CityMap.LeftOf(dir) : CityMap.RightOf(dir));
                if (!city.HasEdge(ex, ez, d)) continue;
                // Right turns cross the oncoming lanes, so only the inner lane may turn right.
                if (k == 2 && lane != 0 && n > 0) continue;
                float wt = k == 0 ? (type == VehicleType.Bus ? 0.7f : 0.5f) : 0.25f;
                cand[n] = d; w[n] = wt; total += wt; n++;
            }
            if (n == 0)
            {
                nextDir = CityMap.Opposite(dir);
            }
            else
            {
                float r = (float)rng.NextDouble() * total;
                nextDir = cand[n - 1];
                for (int k = 0; k < n; k++)
                {
                    if (r < w[k]) { nextDir = cand[k]; break; }
                    r -= w[k];
                }
            }
            // Lanes are kept through turns so side-by-side turners never cut across each other.
            if (nextDir == CityMap.RightOf(dir)) nextLane = 0;
            else nextLane = lane;
        }

        void BeginTurn()
        {
            int ex, ez;
            CityMap.Step(ni, nj, dir, out ex, out ez);
            Vector2 a2, b2;
            city.EdgeLane(ex, ez, nextDir, nextLane, out a2, out b2);
            tp0 = lb;
            tp2 = a2;
            if (nextDir == dir || nextDir == CityMap.Opposite(dir))
            {
                tp1 = (tp0 + tp2) * 0.5f;
                if (nextDir != dir) tp1 = city.NodePos(ex, ez); // U-turn at the map edge
            }
            else
            {
                tp1 = CityMap.IsHorizontal(dir) ? new Vector2(tp2.x, tp0.y) : new Vector2(tp0.x, tp2.y);
                if (type == VehicleType.Bus)
                {
                    // Buses swing wide.
                    Vector2 mid = (tp0 + tp2) * 0.5f;
                    tp1 += (tp1 - mid) * 0.25f;
                }
            }
            turning = true;
            pathLen = Geo.BezierLength(tp0, tp1, tp2);
            ni = ex; nj = ez;
        }

        void EndTurn()
        {
            dir = nextDir;
            lane = nextLane;
            turning = false;
            SetupEdge();
            ChooseNext();
        }

        public Vector2 PathPoint(out Vector2 tangent)
        {
            if (turning)
            {
                float t = Mathf.Clamp01(s / pathLen);
                tangent = Geo.BezierTangent(tp0, tp1, tp2, t).normalized;
                if (tangent.sqrMagnitude < 0.01f) tangent = CityMap.Dirs[nextDir];
                return Geo.Bezier(tp0, tp1, tp2, t);
            }
            tangent = CityMap.Dirs[dir];
            return la + tangent * s;
        }

        /// <summary>Distance left on the current edge to the stop position (before the zebra).</summary>
        public float DistanceToStopLine()
        {
            if (turning) return float.MaxValue;
            return pathLen - CityMap.StopBack - s;
        }

        public bool CanChangeLane()
        {
            return !turning && laneChangeTo < 0 && s < pathLen - 16f && s > 3f && spec.laneChangeRate > 0f;
        }

        public void StartLaneChange(int toLane)
        {
            laneChangeTo = toLane;
            laneChangeBlink = type == VehicleType.Motorbike ? 0.4f : 1.0f;
        }

        /// <summary>Advances along the path at a speed limited by the gap to the nearest obstacle.</summary>
        public void Tick(float dt, float gap, float speedLimit, bool hardStop, float time)
        {
            if (bumpedTime > 0f) { bumpedTime -= dt; speedLimit = 0f; }
            if (ghostTime > 0f) ghostTime -= dt;
            if (honkCooldown > 0f) honkCooldown -= dt;

            float minGap = type == VehicleType.Motorbike ? 0.8f : 1.6f;
            float decel = hardStop ? spec.hardDecel : spec.decel;
            float gapSpeed = gap < 200f ? Mathf.Sqrt(2f * decel * Mathf.Max(0f, gap - minGap)) : 999f;
            float target = Mathf.Min(Mathf.Min(cruise, speedLimit), gapSpeed);
            if (turning) target = Mathf.Min(target, type == VehicleType.Bus ? 5f : 7.5f);

            if (target < speed)
            {
                speed = Mathf.MoveTowards(speed, target, decel * 1.4f * dt);
                SetBrake(target < speed + 0.01f && (speed - target > 0.3f || speed < 0.5f) || speed < 0.3f);
            }
            else
            {
                speed = Mathf.MoveTowards(speed, target, spec.accel * dt);
                SetBrake(speed < 0.3f);
            }

            if (speed < 0.4f && !waitingAtLight && stopTime <= 0f) stuckTime += dt;
            else stuckTime = 0f;

            s += speed * dt;
            if (!turning && s >= pathLen)
            {
                s -= pathLen;
                BeginTurn();
            }
            if (turning && s >= pathLen)
            {
                s -= pathLen;
                EndTurn();
            }

            UpdateLateral(dt, time);
            UpdateBlinkers(time);
            UpdatePose(dt);
        }

        void UpdateLateral(float dt, float time)
        {
            float latTarget = 0f;
            if (laneChangeTo >= 0)
            {
                blinkSide = laneChangeTo > lane ? -1 : 1;
                if (laneChangeBlink > 0f)
                {
                    laneChangeBlink -= dt;
                }
                else
                {
                    float full = (laneChangeTo - lane) * CityMap.LaneWidth;
                    lat = Mathf.MoveTowards(lat, full, 2.6f * dt * Mathf.Max(0.5f, speed / 8f));
                    if (Mathf.Abs(lat - full) < 0.01f)
                    {
                        lane = laneChangeTo;
                        laneChangeTo = -1;
                        lat = 0f;
                        latVel = 0f;
                        SetupEdge();
                        if (nextDir == CityMap.RightOf(dir) && lane != 0) ChooseNext();
                        else if (nextDir != CityMap.RightOf(dir)) nextLane = lane;
                    }
                    return;
                }
            }

            switch (type)
            {
                case VehicleType.Bajaj:
                    // Slow, unpredictable swerving - no blinker.
                    latTarget = Mathf.Sin(time * 0.7f + phase) * 0.9f + Mathf.Sin(time * 1.9f + phase * 2f) * 0.35f;
                    break;
                case VehicleType.Motorbike:
                    weaveTimer -= dt;
                    if (weaveTimer <= 0f)
                    {
                        weaveTimer = 1.2f + (float)rng.NextDouble() * 2f;
                        weaveTarget = ((float)rng.NextDouble() * 2f - 1f) * 1.45f;
                    }
                    latTarget = weaveTarget;
                    break;
            }
            if (turning) latTarget *= 0.3f;
            if (latTarget > lat && blockLeft) latTarget = lat;
            if (latTarget < lat && blockRight) latTarget = lat;
            float prev = lat;
            float rate = type == VehicleType.Bajaj ? 0.6f : 1.2f;
            lat = Mathf.MoveTowards(lat, latTarget, rate * dt);
            latVel = dt > 0f ? (lat - prev) / dt : 0f;
        }

        void UpdateBlinkers(float time)
        {
            int side = 0;
            if (laneChangeTo >= 0) side = blinkSide;
            else if (!turning && s > pathLen - 18f && nextDir != dir && type != VehicleType.Bajaj)
                side = nextDir == CityMap.LeftOf(dir) ? -1 : 1;
            else if (turning && nextDir != dir && s < pathLen * 0.6f)
                side = nextDir == CityMap.LeftOf(dir) ? -1 : 1;
            bool on = side != 0 && Mathf.Repeat(time, 0.6f) < 0.35f;
            visual.blinkLeft.enabled = on && side < 0;
            visual.blinkRight.enabled = on && side > 0;
        }

        void SetBrake(bool on)
        {
            braking = on;
            if (on == brakeShown) return;
            brakeShown = on;
            visual.brake.sharedMaterial = on ? brakeOn : brakeOff;
        }

        void UpdatePose(float dt)
        {
            Vector2 tan;
            Vector2 p = PathPoint(out tan);
            fwd = tan;
            pos = p + Geo.Left(tan) * lat;
            float yaw = Geo.Heading(tan);
            float drift = Mathf.Atan2(-latVel, Mathf.Max(speed, 2f)) * Mathf.Rad2Deg;
            transform.position = Geo.X0Z(pos);
            transform.rotation = Quaternion.Euler(0f, yaw + drift, 0f);
        }

        /// <summary>The player bumped into us: stop, stare, honk.</summary>
        public void OnHitByPlayer()
        {
            bumpedTime = 1.2f;
            speed *= 0.3f;
        }
    }
}
