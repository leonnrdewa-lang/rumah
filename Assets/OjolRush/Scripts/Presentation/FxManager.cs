using System.Collections.Generic;
using UnityEngine;

namespace OjolRush
{
    public enum FxKind { Spark, Dust, Splash, Feather, Steam, Confetti }

    /// <summary>
    /// Tiny chunky cube particles drawn with GPU instancing (no particle assets needed),
    /// plus the rain streaks around the camera.
    /// </summary>
    public class FxManager : MonoBehaviour
    {
        struct P
        {
            public Vector3 pos, vel;
            public float life, maxLife, size, gravity, grow;
            public int mat;
        }

        const int Max = 900;
        readonly P[] parts = new P[Max];
        int count;
        Mesh cube;
        Material[] mats;
        readonly List<Matrix4x4>[] batches = new List<Matrix4x4>[8];
        Matrix4x4[] tmp = new Matrix4x4[1023];
        System.Random rng = new System.Random(11);

        // Rain
        const int Drops = 260;
        Vector3[] drops = new Vector3[Drops];
        Material rainMat;
        GameManager gm;

        static readonly Color[] Colors =
        {
            new Color(1f, 0.85f, 0.25f),   // spark
            new Color(0.7f, 0.65f, 0.58f), // dust
            new Color(0.6f, 0.78f, 0.95f), // splash
            new Color(1f, 1f, 1f),         // feather / steam
            Palette.OjolGreen,             // confetti a
            new Color(1f, 0.8f, 0.15f),    // confetti b
            new Color(1f, 0.45f, 0.2f),    // confetti c
        };

        public void Init(GameManager game)
        {
            gm = game;
            MeshBatcher mb = new MeshBatcher();
            mb.Box(Vector3.zero, Vector3.one, Quaternion.identity, Color.white, false, true);
            Material[] dummy;
            cube = mb.BuildMesh(out dummy);
            cube.subMeshCount = 1;
            mats = new Material[Colors.Length];
            for (int i = 0; i < Colors.Length; i++) mats[i] = Mats.Get(Colors[i], i == 0);
            for (int i = 0; i < batches.Length; i++) batches[i] = new List<Matrix4x4>(256);
            rainMat = Mats.Get(new Color(0.75f, 0.85f, 1f));
            for (int i = 0; i < Drops; i++) drops[i] = new Vector3(R(-30, 30), R(0, 25), R(-30, 40));
        }

        float R(float a, float b) { return a + (float)rng.NextDouble() * (b - a); }

        public void Emit(FxKind kind, Vector3 at, int n)
        {
            for (int i = 0; i < n && count < Max; i++)
            {
                P p = new P();
                p.pos = at;
                switch (kind)
                {
                    case FxKind.Spark:
                        p.vel = new Vector3(R(-6, 6), R(2, 7), R(-6, 6));
                        p.maxLife = R(0.25f, 0.5f); p.size = R(0.08f, 0.16f); p.gravity = 18f; p.mat = 0; break;
                    case FxKind.Dust:
                        p.vel = new Vector3(R(-2, 2), R(0.5f, 2f), R(-2, 2));
                        p.maxLife = R(0.4f, 0.8f); p.size = R(0.18f, 0.35f); p.gravity = 1f; p.grow = 0.6f; p.mat = 1; break;
                    case FxKind.Splash:
                        p.vel = new Vector3(R(-3, 3), R(2, 5), R(-3, 3));
                        p.maxLife = R(0.3f, 0.6f); p.size = R(0.1f, 0.22f); p.gravity = 14f; p.mat = 2; break;
                    case FxKind.Feather:
                        p.vel = new Vector3(R(-2.5f, 2.5f), R(1.5f, 4f), R(-2.5f, 2.5f));
                        p.maxLife = R(0.8f, 1.4f); p.size = R(0.1f, 0.18f); p.gravity = 1.5f; p.mat = 3; break;
                    case FxKind.Steam:
                        p.vel = new Vector3(R(-0.2f, 0.2f), R(0.8f, 1.4f), R(-0.2f, 0.2f));
                        p.maxLife = R(0.9f, 1.4f); p.size = R(0.12f, 0.2f); p.gravity = -0.3f; p.grow = 0.35f; p.mat = 3; break;
                    case FxKind.Confetti:
                        p.vel = new Vector3(R(-4, 4), R(4, 9), R(-4, 4));
                        p.maxLife = R(0.8f, 1.3f); p.size = R(0.12f, 0.22f); p.gravity = 9f; p.mat = 4 + rng.Next(3); break;
                }
                p.life = p.maxLife;
                parts[count++] = p;
            }
        }

        public void Tick(float dt, float rain)
        {
            for (int i = 0; i < batches.Length; i++) batches[i].Clear();
            for (int i = count - 1; i >= 0; i--)
            {
                P p = parts[i];
                p.life -= dt;
                if (p.life <= 0f)
                {
                    parts[i] = parts[--count];
                    continue;
                }
                p.vel.y -= p.gravity * dt;
                p.vel *= 1f - 1.5f * dt;
                p.pos += p.vel * dt;
                if (p.pos.y < 0.02f && p.gravity > 0f)
                {
                    p.pos.y = 0.02f;
                    p.vel = new Vector3(p.vel.x * 0.5f, -p.vel.y * 0.3f, p.vel.z * 0.5f);
                }
                parts[i] = p;
                float t = p.life / p.maxLife;
                float s = p.size * (p.grow > 0f ? 1f + (1f - t) * p.grow * 4f : Mathf.Min(1f, t * 2.5f));
                batches[p.mat].Add(Matrix4x4.TRS(p.pos, Quaternion.Euler(p.pos.x * 90f, p.pos.z * 90f, 0f), Vector3.one * s));
            }

            if (rain > 0.01f)
            {
                Vector3 f = Geo.X0Z(gm.player.Pos);
                int n = (int)(Drops * rain);
                List<Matrix4x4> rb = batches[7];
                for (int i = 0; i < n; i++)
                {
                    Vector3 d = drops[i];
                    d.y -= 26f * dt;
                    if (d.y < 0f) d = new Vector3(R(-26, 26), R(20, 28), R(-24, 44));
                    drops[i] = d;
                    Vector3 wp = new Vector3(f.x + d.x, d.y, f.z + d.z);
                    rb.Add(Matrix4x4.TRS(wp, Quaternion.Euler(8f, 0f, 0f), new Vector3(0.05f, 1.3f, 0.05f)));
                }
            }

            for (int m = 0; m < batches.Length; m++)
            {
                List<Matrix4x4> b = batches[m];
                if (b.Count == 0) continue;
                Material mat = m == 7 ? rainMat : mats[m];
                Draw(mat, b);
            }
        }

        void Draw(Material mat, List<Matrix4x4> list)
        {
            if (SystemInfo.supportsInstancing)
            {
                int i = 0;
                while (i < list.Count)
                {
                    int n = Mathf.Min(1023, list.Count - i);
                    list.CopyTo(i, tmp, 0, n);
                    Graphics.DrawMeshInstanced(cube, 0, mat, tmp, n, null, UnityEngine.Rendering.ShadowCastingMode.Off, false);
                    i += n;
                }
            }
            else
            {
                for (int i = 0; i < list.Count; i++) Graphics.DrawMesh(cube, list[i], mat, 0);
            }
        }

        public void Clear() { count = 0; }
    }
}
