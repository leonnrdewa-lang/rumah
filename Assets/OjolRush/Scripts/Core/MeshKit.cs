using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace OjolRush
{
    /// <summary>
    /// Material cache. Materials are cloned from the render pipeline's default material
    /// (taken from a primitive), so this works in Built-in and URP and survives shader stripping.
    /// </summary>
    public static class Mats
    {
        static Material baseMat, baseEmissive, textMat;
        static readonly Dictionary<long, Material> cache = new Dictionary<long, Material>();
        static Font font;

        static Material Base
        {
            get
            {
                // Prefer the material assets created by the editor setup (Ojol Rush > Apply Project Settings):
                // being real assets in Resources, their shader variants (instancing, emission) survive build stripping.
                if (baseMat == null) baseMat = Resources.Load<Material>("OjolRushBase");
                if (baseMat == null)
                {
                    GameObject go = GameObject.CreatePrimitive(PrimitiveType.Cube);
                    baseMat = go.GetComponent<Renderer>().sharedMaterial;
                    if (Application.isPlaying) Object.Destroy(go);
                    else Object.DestroyImmediate(go);
                }
                return baseMat;
            }
        }

        public static Material Get(Color c, bool emissive = false)
        {
            Color32 k = c;
            long key = ((long)k.r << 24) | ((long)k.g << 16) | ((long)k.b << 8) | k.a | (emissive ? (1L << 40) : 0L);
            Material m;
            if (cache.TryGetValue(key, out m) && m != null) return m;
            Material src = Base;
            if (emissive)
            {
                if (baseEmissive == null) baseEmissive = Resources.Load<Material>("OjolRushBaseEmissive");
                if (baseEmissive != null) src = baseEmissive;
            }
            m = new Material(src);
            m.name = "OR_" + ColorUtility.ToHtmlStringRGB(c) + (emissive ? "_E" : "");
            if (m.HasProperty("_BaseColor")) m.SetColor("_BaseColor", c);
            if (m.HasProperty("_Color")) m.SetColor("_Color", c);
            if (m.HasProperty("_Glossiness")) m.SetFloat("_Glossiness", 0.08f);
            if (m.HasProperty("_Smoothness")) m.SetFloat("_Smoothness", 0.08f);
            if (m.HasProperty("_Metallic")) m.SetFloat("_Metallic", 0f);
            if (!emissive) m.DisableKeyword("_EMISSION");
            if (emissive && m.HasProperty("_EmissionColor"))
            {
                m.EnableKeyword("_EMISSION");
                m.SetColor("_EmissionColor", c * 1.6f);
                m.globalIlluminationFlags = MaterialGlobalIlluminationFlags.None;
            }
            m.enableInstancing = true;
            cache[key] = m;
            return m;
        }

        /// <summary>Depth-tested material for 3D sign text (falls back to the font's own material).</summary>
        public static Material TextMaterial
        {
            get
            {
                if (textMat != null) return textMat;
                Font f = Font;
                Shader sh = Resources.Load<Shader>("OjolRushText");
                if (sh == null) sh = Shader.Find("OjolRush/Text3D");
                if (f == null) return null;
                if (sh == null || !sh.isSupported) return f.material;
                textMat = new Material(sh);
                textMat.mainTexture = f.material.mainTexture;
                Font.textureRebuilt += OnFontRebuilt;
                return textMat;
            }
        }

        static void OnFontRebuilt(Font f)
        {
            if (textMat != null && f == font) textMat.mainTexture = f.material.mainTexture;
        }

        public static Font Font
        {
            get
            {
                if (font != null) return font;
                // Unity 2022.2+ renamed the built-in font.
                string v = Application.unityVersion;
                int major = 0, minor = 0;
                string[] parts = v.Split('.');
                if (parts.Length > 1)
                {
                    int.TryParse(parts[0], out major);
                    int.TryParse(parts[1], out minor);
                }
                bool legacyName = major > 2022 || (major == 2022 && minor >= 2);
                font = Resources.GetBuiltinResource<Font>(legacyName ? "LegacyRuntime.ttf" : "Arial.ttf");
                return font;
            }
        }
    }

    /// <summary>Accumulates low-poly boxes/prisms into one mesh with one submesh per colour.</summary>
    public class MeshBatcher
    {
        class Group
        {
            public readonly List<int> tris = new List<int>();
            public Material mat;
        }

        readonly List<Vector3> verts = new List<Vector3>();
        readonly List<Vector3> normals = new List<Vector3>();
        readonly List<Group> groups = new List<Group>();
        readonly Dictionary<Material, Group> byMat = new Dictionary<Material, Group>();

        public int VertexCount { get { return verts.Count; } }
        public bool IsEmpty { get { return verts.Count == 0; } }

        Group G(Color c, bool emissive)
        {
            Material m = Mats.Get(c, emissive);
            Group g;
            if (!byMat.TryGetValue(m, out g))
            {
                g = new Group { mat = m };
                byMat[m] = g;
                groups.Add(g);
            }
            return g;
        }

        void Quad(Group g, Vector3 a, Vector3 b, Vector3 c, Vector3 d, Vector3 n)
        {
            int i = verts.Count;
            verts.Add(a); verts.Add(b); verts.Add(c); verts.Add(d);
            normals.Add(n); normals.Add(n); normals.Add(n); normals.Add(n);
            g.tris.Add(i); g.tris.Add(i + 1); g.tris.Add(i + 2);
            g.tris.Add(i); g.tris.Add(i + 2); g.tris.Add(i + 3);
        }

        /// <summary>Axis-aligned box given its bottom-centre position.</summary>
        public void BoxBottom(Vector3 bottomCenter, Vector3 size, Color c, bool emissive = false)
        {
            Box(bottomCenter + new Vector3(0, size.y * 0.5f, 0), size, Quaternion.identity, c, emissive);
        }

        public void Box(Vector3 center, Vector3 size, Quaternion rot, Color c, bool emissive = false, bool bottom = false)
        {
            Group g = G(c, emissive);
            Vector3 h = size * 0.5f;
            Vector3 r = rot * new Vector3(h.x, 0, 0);
            Vector3 u = rot * new Vector3(0, h.y, 0);
            Vector3 f = rot * new Vector3(0, 0, h.z);
            Vector3 nr = rot * Vector3.right, nu = rot * Vector3.up, nf = rot * Vector3.forward;
            // top
            Quad(g, center + u - r - f, center + u - r + f, center + u + r + f, center + u + r - f, nu);
            // front (+z)
            Quad(g, center + f - r - u, center + f + r - u, center + f + r + u, center + f - r + u, nf);
            // back (-z)
            Quad(g, center - f + r - u, center - f - r - u, center - f - r + u, center - f + r + u, -nf);
            // right
            Quad(g, center + r + f - u, center + r - f - u, center + r - f + u, center + r + f + u, nr);
            // left
            Quad(g, center - r - f - u, center - r + f - u, center - r + f + u, center - r - f + u, -nr);
            if (bottom) Quad(g, center - u - r + f, center - u - r - f, center - u + r - f, center - u + r + f, -nu);
        }

        /// <summary>Low-poly prism (cylinder) along an axis. Used for wheels, poles, tanks.</summary>
        public void Prism(Vector3 center, Vector3 axis, float radius, float length, int sides, Color c, bool emissive = false)
        {
            Group g = G(c, emissive);
            axis.Normalize();
            Vector3 t1 = Vector3.Cross(axis, Mathf.Abs(axis.y) > 0.9f ? Vector3.right : Vector3.up).normalized;
            Vector3 t2 = Vector3.Cross(axis, t1);
            Vector3 a = center - axis * (length * 0.5f);
            Vector3 b = center + axis * (length * 0.5f);
            for (int s = 0; s < sides; s++)
            {
                float a0 = s * Mathf.PI * 2f / sides, a1 = (s + 1) * Mathf.PI * 2f / sides;
                Vector3 d0 = t1 * Mathf.Cos(a0) + t2 * Mathf.Sin(a0);
                Vector3 d1 = t1 * Mathf.Cos(a1) + t2 * Mathf.Sin(a1);
                Vector3 n = (d0 + d1).normalized;
                Quad(g, a + d0 * radius, a + d1 * radius, b + d1 * radius, b + d0 * radius, n);
                // caps as thin fans
                int i = verts.Count;
                verts.Add(b); verts.Add(b + d0 * radius); verts.Add(b + d1 * radius);
                normals.Add(axis); normals.Add(axis); normals.Add(axis);
                g.tris.Add(i); g.tris.Add(i + 1); g.tris.Add(i + 2);
                i = verts.Count;
                verts.Add(a); verts.Add(a + d0 * radius); verts.Add(a + d1 * radius);
                normals.Add(-axis); normals.Add(-axis); normals.Add(-axis);
                g.tris.Add(i); g.tris.Add(i + 2); g.tris.Add(i + 1);
            }
        }

        /// <summary>Chunky low-poly ball (an octahedron-ish UV sphere with few segments).</summary>
        public void Ball(Vector3 center, float radius, Color c, int seg = 6)
        {
            Group g = G(c, false);
            int rings = Mathf.Max(3, seg / 2 + 1);
            for (int ri = 0; ri < rings; ri++)
            {
                float p0 = Mathf.PI * ri / rings - Mathf.PI / 2f;
                float p1 = Mathf.PI * (ri + 1) / rings - Mathf.PI / 2f;
                for (int s = 0; s < seg; s++)
                {
                    float a0 = s * Mathf.PI * 2f / seg, a1 = (s + 1) * Mathf.PI * 2f / seg;
                    Vector3 v00 = Sph(a0, p0), v01 = Sph(a1, p0), v10 = Sph(a0, p1), v11 = Sph(a1, p1);
                    Vector3 n = (v00 + v01 + v10 + v11).normalized;
                    Quad(g, center + v00 * radius, center + v10 * radius, center + v11 * radius, center + v01 * radius, n);
                }
            }
        }

        static Vector3 Sph(float a, float p)
        {
            return new Vector3(Mathf.Cos(p) * Mathf.Cos(a), Mathf.Sin(p), Mathf.Cos(p) * Mathf.Sin(a));
        }

        /// <summary>Thin box between two points - cables, lines, stripes.</summary>
        public void Beam(Vector3 from, Vector3 to, float thickness, Color c, bool emissive = false)
        {
            Vector3 d = to - from;
            float len = d.magnitude;
            if (len < 0.001f) return;
            Quaternion rot = Quaternion.LookRotation(d / len, Mathf.Abs(d.normalized.y) > 0.95f ? Vector3.forward : Vector3.up);
            Box((from + to) * 0.5f, new Vector3(thickness, thickness, len), rot, c, emissive);
        }

        public Mesh BuildMesh(out Material[] materials)
        {
            Mesh mesh = new Mesh();
            mesh.name = "OR_Batch";
            if (verts.Count > 65000) mesh.indexFormat = IndexFormat.UInt32;
            mesh.SetVertices(verts);
            mesh.SetNormals(normals);
            mesh.subMeshCount = groups.Count;
            materials = new Material[groups.Count];
            for (int i = 0; i < groups.Count; i++)
            {
                mesh.SetTriangles(groups[i].tris, i);
                materials[i] = groups[i].mat;
            }
            mesh.RecalculateBounds();
            return mesh;
        }

        public GameObject BuildObject(string name, Transform parent, bool castShadows = true)
        {
            GameObject go = new GameObject(name);
            go.transform.SetParent(parent, false);
            Attach(go, castShadows);
            return go;
        }

        public void Attach(GameObject go, bool castShadows = true)
        {
            Material[] mats;
            Mesh mesh = BuildMesh(out mats);
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            MeshRenderer mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterials = mats;
            mr.shadowCastingMode = castShadows ? ShadowCastingMode.On : ShadowCastingMode.Off;
        }

        public void Clear()
        {
            verts.Clear();
            normals.Clear();
            groups.Clear();
            byMat.Clear();
        }
    }

    public static class TextKit
    {
        /// <summary>World-space text on a sign. Faces -Z (towards the camera) unless rotated.</summary>
        public static TextMesh Make(Transform parent, string text, Vector3 localPos, Quaternion localRot, float charHeight, Color color)
        {
            GameObject go = new GameObject("Text_" + text);
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            go.transform.localRotation = localRot;
            TextMesh tm = go.AddComponent<TextMesh>();
            tm.font = Mats.Font;
            tm.fontSize = 48;
            // characterSize scales glyphs; with fontSize 48, 0.1 -> ~0.48 world units of line height.
            tm.characterSize = charHeight / 4.8f;
            tm.anchor = TextAnchor.MiddleCenter;
            tm.alignment = TextAlignment.Center;
            tm.fontStyle = FontStyle.Bold;
            tm.color = color;
            tm.text = text;
            MeshRenderer mr = go.GetComponent<MeshRenderer>();
            Material textMaterial = Mats.TextMaterial;
            if (textMaterial != null) mr.sharedMaterial = textMaterial;
            mr.shadowCastingMode = ShadowCastingMode.Off;
            return tm;
        }

        /// <summary>Shrinks a text mesh so it fits in maxWidth (measured from its renderer bounds).</summary>
        public static void FitWidth(TextMesh tm, float maxWidth)
        {
            MeshRenderer mr = tm.GetComponent<MeshRenderer>();
            float w = mr.bounds.size.x;
            // Fallback estimate if the text mesh has not been generated yet (bold glyph ~0.62 of line height).
            if (w < 0.0001f) w = tm.text.Length * tm.characterSize * 4.8f * 0.62f;
            if (w > maxWidth && w > 0.0001f) tm.characterSize *= maxWidth / w;
        }
    }
}
