// Minimal stand-ins for the UnityEngine types used by the engine-independent game logic, so the
// EditMode tests can also run with plain Mono (no Unity install / license needed, e.g. in CI).
// This file lives outside Assets/ and is never compiled by Unity.
using System;
namespace UnityEngine
{
    public struct Vector2 : IEquatable<Vector2>
    {
        public float x, y;
        public Vector2(float x, float y) { this.x = x; this.y = y; }
        public static Vector2 zero { get { return new Vector2(0, 0); } }
        public static Vector2 up { get { return new Vector2(0, 1); } }
        public static Vector2 down { get { return new Vector2(0, -1); } }
        public float sqrMagnitude { get { return x * x + y * y; } }
        public float magnitude { get { return (float)Math.Sqrt(sqrMagnitude); } }
        public Vector2 normalized { get { float m = magnitude; return m > 1e-5f ? new Vector2(x / m, y / m) : zero; } }
        public static float Dot(Vector2 a, Vector2 b) { return a.x * b.x + a.y * b.y; }
        public static float Distance(Vector2 a, Vector2 b) { return (a - b).magnitude; }
        public static Vector2 Lerp(Vector2 a, Vector2 b, float t) { t = Mathf.Clamp01(t); return a + (b - a) * t; }
        public static Vector2 ClampMagnitude(Vector2 v, float m) { return v.magnitude > m ? v.normalized * m : v; }
        public static Vector2 operator +(Vector2 a, Vector2 b) { return new Vector2(a.x + b.x, a.y + b.y); }
        public static Vector2 operator -(Vector2 a, Vector2 b) { return new Vector2(a.x - b.x, a.y - b.y); }
        public static Vector2 operator -(Vector2 a) { return new Vector2(-a.x, -a.y); }
        public static Vector2 operator *(Vector2 a, float d) { return new Vector2(a.x * d, a.y * d); }
        public static Vector2 operator *(float d, Vector2 a) { return new Vector2(a.x * d, a.y * d); }
        public static Vector2 operator /(Vector2 a, float d) { return new Vector2(a.x / d, a.y / d); }
        public static bool operator ==(Vector2 a, Vector2 b) { return (a - b).sqrMagnitude < 1e-10f; }
        public static bool operator !=(Vector2 a, Vector2 b) { return !(a == b); }
        public bool Equals(Vector2 o) { return x == o.x && y == o.y; }
        public override bool Equals(object o) { return o is Vector2 && Equals((Vector2)o); }
        public override int GetHashCode() { return x.GetHashCode() ^ (y.GetHashCode() << 2); }
        public override string ToString() { return "(" + x + ", " + y + ")"; }
    }
    public struct Vector3
    {
        public float x, y, z;
        public Vector3(float x, float y, float z) { this.x = x; this.y = y; this.z = z; }
    }
    public struct Rect
    {
        public float x, y, width, height;
        public Rect(float x, float y, float w, float h) { this.x = x; this.y = y; width = w; height = h; }
        public static Rect MinMaxRect(float a, float b, float c, float d) { return new Rect(a, b, c - a, d - b); }
        public float xMin { get { return x; } } public float yMin { get { return y; } }
        public float xMax { get { return x + width; } } public float yMax { get { return y + height; } }
        public Vector2 center { get { return new Vector2(x + width / 2, y + height / 2); } }
        public bool Contains(Vector2 p) { return p.x >= xMin && p.x < xMax && p.y >= yMin && p.y < yMax; }
        public bool Overlaps(Rect o) { return o.xMax > xMin && o.xMin < xMax && o.yMax > yMin && o.yMin < yMax; }
    }
    public static class Mathf
    {
        public const float Deg2Rad = (float)(Math.PI / 180.0), Rad2Deg = (float)(180.0 / Math.PI), PI = (float)Math.PI;
        public static float Sin(float f) { return (float)Math.Sin(f); }
        public static float Cos(float f) { return (float)Math.Cos(f); }
        public static float Atan2(float y, float x) { return (float)Math.Atan2(y, x); }
        public static float Sqrt(float f) { return (float)Math.Sqrt(f); }
        public static float Exp(float f) { return (float)Math.Exp(f); }
        public static float Abs(float f) { return Math.Abs(f); }
        public static float Min(float a, float b) { return a < b ? a : b; }
        public static float Max(float a, float b) { return a > b ? a : b; }
        public static int Min(int a, int b) { return a < b ? a : b; }
        public static int Max(int a, int b) { return a > b ? a : b; }
        public static float Clamp(float v, float a, float b) { return v < a ? a : (v > b ? b : v); }
        public static int Clamp(int v, int a, int b) { return v < a ? a : (v > b ? b : v); }
        public static float Clamp01(float v) { return Clamp(v, 0f, 1f); }
        public static float Floor(float f) { return (float)Math.Floor(f); }
        public static int RoundToInt(float f) { return (int)Math.Round(f); }
        public static float MoveTowards(float c, float t, float m) { return Math.Abs(t - c) <= m ? t : c + Math.Sign(t - c) * m; }
        public static float Repeat(float t, float l) { return Clamp(t - Floor(t / l) * l, 0f, l); }
    }
    public class Object { }
    public class ScriptableObject : Object { public static T CreateInstance<T>() where T : ScriptableObject, new() { return new T(); } }
    public static class Resources { public static T Load<T>(string p) where T : class { return null; } }
    public class CreateAssetMenuAttribute : Attribute { public string menuName, fileName; }
    public class HeaderAttribute : Attribute { public HeaderAttribute(string s) { } }
    public class TooltipAttribute : Attribute { public TooltipAttribute(string s) { } }
    public class RangeAttribute : Attribute { public RangeAttribute(float a, float b) { } }
}


namespace UnityEngine
{
    public struct Color { public float r, g, b, a; public Color(float r, float g, float b, float a = 1f) { this.r = r; this.g = g; this.b = b; this.a = a; } }
    public struct Quaternion { public float yaw; public static Quaternion Euler(float x, float y, float z) { return new Quaternion { yaw = y }; } }
    public class Material { }
    public class Transform { public Vector3 position; public Quaternion rotation; }
    public class GameObject { }
    public class Component : Object { Transform t = new Transform(); public Transform transform { get { return t; } } }
    public class Behaviour : Component { }
    public class MonoBehaviour : Behaviour { }
    public class Renderer : Component { public bool enabled; public Material sharedMaterial; }
}
namespace OjolRush
{
    public static class Mats { public static UnityEngine.Material Get(UnityEngine.Color c, bool e = false) { return new UnityEngine.Material(); } }
}
namespace OjolRush { public class Passenger { public bool claimed; public float along; } }
