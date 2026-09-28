using System.Collections.Generic;
using UnityEngine;

namespace OjolRush
{
    /// <summary>
    /// What a traffic driver "sees": the free distance ahead to other vehicles, the player and the
    /// stop line of a red light. Pure functions so the AI can be simulated and tested headless.
    /// </summary>
    public static class TrafficSensing
    {
        public const float None = 999f;
        /// <summary>Traffic only reacts to the ojol when this close (they are used to being cut off).</summary>
        public const float PlayerReaction = 7f;
        public const float StuckBeforeGhost = 4f;
        public const float GhostTime = 2f;

        static float HalfWidthWithMargin(TrafficVehicle v)
        {
            return v.HalfWidth + (v.type == VehicleType.Motorbike ? 0.15f : 0.35f);
        }

        /// <summary>Free distance from our front bumper to the nearest vehicle in our forward corridor.</summary>
        public static float VehicleGap(TrafficVehicle v, IList<TrafficVehicle> vehicles)
        {
            bool ghost = v.ghostTime > 0f;
            float gap = None;
            Vector2 f = v.fwd;
            Vector2 l = Geo.Left(f);
            float look = 6f + v.speed * 1.8f + 12f;
            float look2 = look * look;
            float myHalfW = HalfWidthWithMargin(v);
            for (int k = 0; k < vehicles.Count; k++)
            {
                TrafficVehicle o = vehicles[k];
                if (o == v) continue;
                Vector2 rel = o.pos - v.pos;
                if (rel.sqrMagnitude > look2) continue;
                float along = Vector2.Dot(rel, f);
                if (along <= 0f) continue;
                // Breaking a deadlock only ignores crossing traffic, never the queue in front of us.
                if (ghost && Vector2.Dot(o.fwd, f) < 0.7f) continue;
                // Project the other box onto our lateral / forward axes.
                Vector2 ol = Geo.Left(o.fwd);
                float oHalfSide = Mathf.Abs(Vector2.Dot(o.fwd, l)) * o.HalfLength + Mathf.Abs(Vector2.Dot(ol, l)) * o.HalfWidth;
                float side = Vector2.Dot(rel, l);
                if (Mathf.Abs(side) > myHalfW + oHalfSide) continue;
                float oHalfAlong = Mathf.Abs(Vector2.Dot(o.fwd, f)) * o.HalfLength + Mathf.Abs(Vector2.Dot(ol, f)) * o.HalfWidth;
                float g = along - v.HalfLength - oHalfAlong;
                if (g < gap) gap = g;
            }
            return gap;
        }

        /// <summary>Gap to the player bike if it is in our corridor and already close.</summary>
        public static float PlayerGap(TrafficVehicle v, Vector2 playerPos)
        {
            Vector2 f = v.fwd;
            Vector2 rel = playerPos - v.pos;
            float along = Vector2.Dot(rel, f);
            float side = Vector2.Dot(rel, Geo.Left(f));
            if (along <= 0f || Mathf.Abs(side) >= HalfWidthWithMargin(v) + 0.5f) return None;
            float g = along - v.HalfLength - 0.9f;
            return g < PlayerReaction ? g : None;
        }

        /// <summary>
        /// Gap to the stop line when the signal ahead is red (or yellow and there is room to stop).
        /// Turning left is always allowed ("belok kiri jalan terus"); bikes creep past the line.
        /// </summary>
        public static float LightGap(TrafficVehicle v, TrafficLights lights, float time)
        {
            v.waitingAtLight = false;
            if (v.turning || v.IsTurningLeftNext) return None;
            int ex, ez;
            CityMap.Step(v.ni, v.nj, v.dir, out ex, out ez);
            LightState st = lights.State(ex, ez, CityMap.IsHorizontal(v.dir), time);
            if (st == LightState.Green) return None;
            float dStop = v.DistanceToStopLine() - v.HalfLength;
            if (v.type == VehicleType.Motorbike) dStop += 2.2f;
            if (dStop <= -0.5f) return None;
            bool stop = st == LightState.Red || dStop > v.speed * 1.2f + 1f;
            if (!stop) return None;
            if (dStop < 12f) v.waitingAtLight = true;
            return dStop + 1.2f;
        }

        /// <summary>
        /// Yield rules at junctions: a right turn (crossing oncoming lanes in left-hand traffic) waits for
        /// oncoming traffic, and a left turn on red waits for cross traffic heading into its exit street.
        /// </summary>
        public static float YieldGap(TrafficVehicle v, IList<TrafficVehicle> vehicles, TrafficLights lights, float time)
        {
            if (v.turning) return None;
            float dStop = v.DistanceToStopLine() - v.HalfLength;
            if (dStop > 6f || dStop < -1.5f) return None;
            int ex, ez;
            CityMap.Step(v.ni, v.nj, v.dir, out ex, out ez);
            bool myAxis = CityMap.IsHorizontal(v.dir);
            // Don't enter while cross traffic is still clearing the junction (slow buses, yellow runners).
            for (int k = 0; k < vehicles.Count; k++)
            {
                TrafficVehicle o = vehicles[k];
                if (o == v || !o.turning || o.ni != ex || o.nj != ez) continue;
                bool crossing = CityMap.IsHorizontal(o.dir) != myAxis;
                bool oncomingRightTurn = o.dir == CityMap.Opposite(v.dir) && o.nextDir == CityMap.RightOf(o.dir);
                if (crossing || oncomingRightTurn) return Mathf.Max(0f, dStop) + 1.2f;
            }
            if (v.nextDir == v.dir) return None;
            bool rightTurn = v.nextDir == CityMap.RightOf(v.dir);
            if (!rightTurn && lights.State(ex, ez, CityMap.IsHorizontal(v.dir), time) == LightState.Green) return None;
            // Right turn: yield to oncoming traffic going straight or left.
            // Left on red: yield to cross traffic from both sides (they have green).
            for (int k = 0; k < vehicles.Count; k++)
            {
                TrafficVehicle o = vehicles[k];
                if (o == v) continue;
                if (rightTurn ? o.dir != CityMap.Opposite(v.dir) : CityMap.IsHorizontal(o.dir) == myAxis) continue;
                if (!o.turning && o.speed < 0.5f) continue;
                if (rightTurn && o.nextDir == CityMap.RightOf(o.dir) && !o.turning) continue; // opposing right turns pass each other
                bool approaching;
                if (o.turning) approaching = o.ni == ex && o.nj == ez && o.s < o.pathLen * 0.7f;
                else
                {
                    int ox, oz;
                    CityMap.Step(o.ni, o.nj, o.dir, out ox, out oz);
                    approaching = ox == ex && oz == ez && o.DistanceToStopLine() < 22f && o.DistanceToStopLine() > -3f;
                }
                if (approaching) return Mathf.Max(0f, dStop) + 1.2f;
            }
            return None;
        }

        /// <summary>Is there a vehicle right beside us on the given side (+1 left, -1 right)?</summary>
        public static bool SideBlocked(TrafficVehicle v, IList<TrafficVehicle> vehicles, float sideSign)
        {
            Vector2 f = v.fwd;
            Vector2 l = Geo.Left(f);
            for (int k = 0; k < vehicles.Count; k++)
            {
                TrafficVehicle o = vehicles[k];
                if (o == v) continue;
                Vector2 rel = o.pos - v.pos;
                if (rel.sqrMagnitude > 144f) continue;
                Vector2 ol = Geo.Left(o.fwd);
                float oHalfAlong = Mathf.Abs(Vector2.Dot(o.fwd, f)) * o.HalfLength + Mathf.Abs(Vector2.Dot(ol, f)) * o.HalfWidth;
                float oHalfSide = Mathf.Abs(Vector2.Dot(o.fwd, l)) * o.HalfLength + Mathf.Abs(Vector2.Dot(ol, l)) * o.HalfWidth;
                float along = Vector2.Dot(rel, f);
                if (Mathf.Abs(along) > v.HalfLength + oHalfAlong + 0.5f) continue;
                float side = Vector2.Dot(rel, l) * sideSign;
                if (side > 0f && side < v.HalfWidth + oHalfSide + 0.45f) return true;
            }
            return false;
        }

        /// <summary>After being stuck (not at a light) for a while, squeeze through for a moment.</summary>
        public static bool BreakDeadlock(TrafficVehicle v)
        {
            if (v.stuckTime <= StuckBeforeGhost || v.ghostTime > 0f) return false;
            v.ghostTime = GhostTime;
            v.stuckTime = 0f;
            return true;
        }

        /// <summary>True when the neighbouring lane has room around our position.</summary>
        public static bool LaneIsFree(TrafficVehicle v, IList<TrafficVehicle> vehicles, CityMap city, int toLane)
        {
            Vector2 a, b;
            city.EdgeLane(v.ni, v.nj, v.dir, toLane, out a, out b);
            Vector2 target = a + CityMap.Dirs[v.dir] * v.s;
            for (int k = 0; k < vehicles.Count; k++)
            {
                TrafficVehicle o = vehicles[k];
                if (o == v) continue;
                float clear = v.HalfLength + o.HalfLength + 4f;
                if ((o.pos - target).sqrMagnitude < clear * clear) return false;
            }
            return true;
        }
    }
}
