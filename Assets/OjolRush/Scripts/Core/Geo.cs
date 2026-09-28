using UnityEngine;

namespace OjolRush
{
    /// <summary>
    /// Small helpers for the top-down XZ plane. The game logic lives in 2D (x, z);
    /// Vector2.y always means world Z. Heading 0 = north (+Z), 90 = east (+X).
    /// </summary>
    public static class Geo
    {
        public static Vector3 X0Z(Vector2 p, float y = 0f) { return new Vector3(p.x, y, p.y); }
        public static Vector2 XZ(Vector3 p) { return new Vector2(p.x, p.z); }

        public static Vector2 Dir(float headingDeg)
        {
            float r = headingDeg * Mathf.Deg2Rad;
            return new Vector2(Mathf.Sin(r), Mathf.Cos(r));
        }

        public static float Heading(Vector2 dir) { return Mathf.Atan2(dir.x, dir.y) * Mathf.Rad2Deg; }

        /// <summary>Left-hand perpendicular of a forward vector (seen from above).</summary>
        public static Vector2 Left(Vector2 f) { return new Vector2(-f.y, f.x); }

        /// <summary>
        /// Closest point on an oriented box (center c, unit forward f, half length hl, half width hw) to p.
        /// Returns true when p is inside the box.
        /// </summary>
        public static bool ClosestOnObb(Vector2 c, Vector2 f, float hl, float hw, Vector2 p, out Vector2 closest)
        {
            Vector2 l = Left(f);
            Vector2 d = p - c;
            float a = Vector2.Dot(d, f);
            float b = Vector2.Dot(d, l);
            bool inside = Mathf.Abs(a) <= hl && Mathf.Abs(b) <= hw;
            float ca = Mathf.Clamp(a, -hl, hl);
            float cb = Mathf.Clamp(b, -hw, hw);
            if (inside)
            {
                // Push out through the nearest face.
                float px = hl - Mathf.Abs(a);
                float pz = hw - Mathf.Abs(b);
                if (px < pz) ca = a >= 0 ? hl : -hl;
                else cb = b >= 0 ? hw : -hw;
            }
            closest = c + f * ca + l * cb;
            return inside;
        }

        public static Vector2 Bezier(Vector2 p0, Vector2 p1, Vector2 p2, float t)
        {
            float u = 1f - t;
            return u * u * p0 + 2f * u * t * p1 + t * t * p2;
        }

        public static Vector2 BezierTangent(Vector2 p0, Vector2 p1, Vector2 p2, float t)
        {
            return 2f * (1f - t) * (p1 - p0) + 2f * t * (p2 - p1);
        }

        public static float BezierLength(Vector2 p0, Vector2 p1, Vector2 p2)
        {
            float len = 0f;
            Vector2 prev = p0;
            for (int i = 1; i <= 10; i++)
            {
                Vector2 q = Bezier(p0, p1, p2, i / 10f);
                len += Vector2.Distance(prev, q);
                prev = q;
            }
            return len;
        }

        public static float ExpLerp(float sharpness, float dt) { return 1f - Mathf.Exp(-sharpness * dt); }
    }
}
