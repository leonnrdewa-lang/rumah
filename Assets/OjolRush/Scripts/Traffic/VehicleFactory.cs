using UnityEngine;

namespace OjolRush
{
    /// <summary>Builds chunky low-poly vehicle meshes from boxes and prisms.</summary>
    public static class VehicleFactory
    {
        public static VehicleSpec Spec(VehicleType t) { return VehicleSpec.For(t); }

        static void Wheel(MeshBatcher mb, float x, float z, float r, float w)
        {
            mb.Prism(new Vector3(x, r, z), Vector3.right, r, w, 8, Palette.Tire);
        }

        public static VehicleVisual Build(VehicleType t, System.Random rng, Transform parent)
        {
            VehicleSpec sp = Spec(t);
            float L = sp.length, W = sp.width;
            MeshBatcher mb = new MeshBatcher();
            // Light positions (rear corners / all corners), in local space.
            Vector3[] brakes;
            float lightY;
            switch (t)
            {
                case VehicleType.Angkot:
                {
                    Color body = Palette.AngkotBlue;
                    mb.BoxBottom(new Vector3(0, 0.3f, 0), new Vector3(W, 1.35f, L), body);
                    mb.BoxBottom(new Vector3(0, 1.0f, -0.1f), new Vector3(W + 0.03f, 0.45f, L * 0.72f), Palette.Glass);
                    mb.BoxBottom(new Vector3(0, 0.95f, L * 0.36f), new Vector3(W * 0.92f, 0.5f, 0.3f), Palette.Glass);
                    mb.BoxBottom(new Vector3(0, 0.72f, 0), new Vector3(W + 0.04f, 0.12f, L + 0.02f), Palette.White);
                    mb.BoxBottom(new Vector3(0, 1.65f, -0.2f), new Vector3(W * 0.95f, 0.08f, L * 0.8f), Palette.Shade(body, 1.25f));
                    // roof rack
                    mb.BoxBottom(new Vector3(-W * 0.4f, 1.73f, -0.2f), new Vector3(0.06f, 0.1f, L * 0.7f), Palette.Tire);
                    mb.BoxBottom(new Vector3(W * 0.4f, 1.73f, -0.2f), new Vector3(0.06f, 0.1f, L * 0.7f), Palette.Tire);
                    // open side door (left, curb side)
                    mb.BoxBottom(new Vector3(-W * 0.5f, 0.35f, -0.4f), new Vector3(0.05f, 1.2f, 0.9f), new Color(0.1f, 0.12f, 0.16f));
                    // route plate on the roof (readable blob of colour from above)
                    mb.BoxBottom(new Vector3(0, 1.72f, L * 0.3f), new Vector3(W * 0.6f, 0.06f, 0.5f), new Color(1f, 0.85f, 0.1f));
                    Wheel(mb, -W * 0.5f, L * 0.32f, 0.32f, 0.22f); Wheel(mb, W * 0.5f, L * 0.32f, 0.32f, 0.22f);
                    Wheel(mb, -W * 0.5f, -L * 0.32f, 0.32f, 0.22f); Wheel(mb, W * 0.5f, -L * 0.32f, 0.32f, 0.22f);
                    lightY = 0.75f;
                    brakes = new[] { new Vector3(-W * 0.36f, lightY, -L * 0.5f), new Vector3(W * 0.36f, lightY, -L * 0.5f) };
                    break;
                }
                case VehicleType.Bajaj:
                {
                    Color body = Palette.BajajOrange;
                    mb.BoxBottom(new Vector3(0, 0.25f, -0.2f), new Vector3(W, 0.65f, L * 0.72f), body);
                    mb.BoxBottom(new Vector3(0, 0.25f, L * 0.3f), new Vector3(W * 0.55f, 0.95f, 0.7f), body);
                    mb.BoxBottom(new Vector3(0, 0.95f, L * 0.36f), new Vector3(W * 0.5f, 0.45f, 0.1f), Palette.Glass);
                    mb.BoxBottom(new Vector3(0, 0.9f, -0.35f), new Vector3(W * 0.8f, 0.35f, 0.6f), new Color(0.2f, 0.2f, 0.2f));
                    mb.BoxBottom(new Vector3(0, 1.55f, -0.1f), new Vector3(W, 0.1f, L * 0.85f), new Color(0.12f, 0.12f, 0.12f));
                    mb.BoxBottom(new Vector3(-W * 0.45f, 0.85f, -L * 0.4f), new Vector3(0.06f, 0.72f, 0.06f), Palette.Tire);
                    mb.BoxBottom(new Vector3(W * 0.45f, 0.85f, -L * 0.4f), new Vector3(0.06f, 0.72f, 0.06f), Palette.Tire);
                    Wheel(mb, 0, L * 0.4f, 0.26f, 0.16f);
                    Wheel(mb, -W * 0.45f, -L * 0.3f, 0.26f, 0.16f); Wheel(mb, W * 0.45f, -L * 0.3f, 0.26f, 0.16f);
                    lightY = 0.6f;
                    brakes = new[] { new Vector3(-W * 0.38f, lightY, -L * 0.56f), new Vector3(W * 0.38f, lightY, -L * 0.56f) };
                    break;
                }
                case VehicleType.Bus:
                {
                    Color body = Palette.Pick(Palette.BusColors, rng);
                    mb.BoxBottom(new Vector3(0, 0.35f, 0), new Vector3(W, 2.45f, L), body);
                    mb.BoxBottom(new Vector3(0, 1.45f, -0.3f), new Vector3(W + 0.03f, 0.8f, L * 0.85f), Palette.Glass);
                    mb.BoxBottom(new Vector3(0, 1.35f, L * 0.5f - 0.05f), new Vector3(W * 0.9f, 1.0f, 0.12f), Palette.Glass);
                    mb.BoxBottom(new Vector3(0, 0.95f, 0), new Vector3(W + 0.04f, 0.2f, L + 0.02f), Palette.White);
                    mb.BoxBottom(new Vector3(0, 2.8f, 0), new Vector3(W * 0.96f, 0.06f, L * 0.96f), Palette.White);
                    mb.BoxBottom(new Vector3(0, 2.86f, 1.5f), new Vector3(W * 0.6f, 0.3f, 1.6f), new Color(0.75f, 0.75f, 0.78f));
                    mb.BoxBottom(new Vector3(0, 2.86f, -2.5f), new Vector3(W * 0.6f, 0.3f, 1.6f), new Color(0.75f, 0.75f, 0.78f));
                    float r = 0.48f;
                    Wheel(mb, -W * 0.5f, L * 0.33f, r, 0.3f); Wheel(mb, W * 0.5f, L * 0.33f, r, 0.3f);
                    Wheel(mb, -W * 0.5f, -L * 0.25f, r, 0.3f); Wheel(mb, W * 0.5f, -L * 0.25f, r, 0.3f);
                    Wheel(mb, -W * 0.5f, -L * 0.36f, r, 0.3f); Wheel(mb, W * 0.5f, -L * 0.36f, r, 0.3f);
                    lightY = 0.9f;
                    brakes = new[] { new Vector3(-W * 0.38f, lightY, -L * 0.5f), new Vector3(W * 0.38f, lightY, -L * 0.5f) };
                    break;
                }
                case VehicleType.Motorbike:
                {
                    Color body = Palette.Pick(Palette.CarColors, rng);
                    Color jacket = Palette.Pick(Palette.JacketColors, rng);
                    Color helmet = Palette.Pick(Palette.CarColors, rng);
                    mb.BoxBottom(new Vector3(0, 0.3f, 0), new Vector3(0.34f, 0.42f, 1.45f), body);
                    mb.BoxBottom(new Vector3(0, 0.72f, -0.2f), new Vector3(0.36f, 0.12f, 0.7f), new Color(0.15f, 0.15f, 0.15f));
                    mb.BoxBottom(new Vector3(0, 0.72f, 0.55f), new Vector3(0.7f, 0.06f, 0.06f), Palette.Tire);
                    mb.Prism(new Vector3(0, 0.3f, 0.7f), Vector3.right, 0.3f, 0.12f, 8, Palette.Tire);
                    mb.Prism(new Vector3(0, 0.3f, -0.68f), Vector3.right, 0.3f, 0.14f, 8, Palette.Tire);
                    // rider
                    mb.BoxBottom(new Vector3(0, 0.8f, -0.15f), new Vector3(0.5f, 0.6f, 0.34f), jacket);
                    mb.Beam(new Vector3(-0.24f, 1.25f, -0.05f), new Vector3(-0.33f, 0.8f, 0.5f), 0.13f, jacket);
                    mb.Beam(new Vector3(0.24f, 1.25f, -0.05f), new Vector3(0.33f, 0.8f, 0.5f), 0.13f, jacket);
                    mb.Ball(new Vector3(0, 1.58f, -0.1f), 0.21f, helmet);
                    lightY = 0.55f;
                    brakes = new[] { new Vector3(0, lightY, -0.74f) };
                    break;
                }
                default:
                {
                    Color body = Palette.Pick(Palette.CarColors, rng);
                    mb.BoxBottom(new Vector3(0, 0.28f, 0), new Vector3(W, 0.62f, L), body);
                    mb.BoxBottom(new Vector3(0, 0.9f, -0.2f), new Vector3(W * 0.86f, 0.5f, L * 0.5f), Palette.Glass);
                    mb.BoxBottom(new Vector3(0, 1.38f, -0.2f), new Vector3(W * 0.88f, 0.1f, L * 0.44f), body);
                    mb.BoxBottom(new Vector3(0, 0.5f, L * 0.5f), new Vector3(W * 0.9f, 0.18f, 0.08f), new Color(0.3f, 0.3f, 0.32f));
                    Wheel(mb, -W * 0.5f, L * 0.31f, 0.33f, 0.24f); Wheel(mb, W * 0.5f, L * 0.31f, 0.33f, 0.24f);
                    Wheel(mb, -W * 0.5f, -L * 0.31f, 0.33f, 0.24f); Wheel(mb, W * 0.5f, -L * 0.31f, 0.33f, 0.24f);
                    lightY = 0.72f;
                    brakes = new[] { new Vector3(-W * 0.36f, lightY, -L * 0.5f), new Vector3(W * 0.36f, lightY, -L * 0.5f) };
                    break;
                }
            }

            VehicleVisual v = new VehicleVisual();
            v.root = new GameObject(t.ToString());
            v.root.transform.SetParent(parent, false);
            mb.BuildObject("Body", v.root.transform);

            // Brake lights: big and bright so danger always reads from above.
            MeshBatcher bm = new MeshBatcher();
            Vector3 bsize = t == VehicleType.Motorbike ? new Vector3(0.22f, 0.14f, 0.12f) : new Vector3(W * 0.26f, 0.2f, 0.14f);
            for (int i = 0; i < brakes.Length; i++) bm.Box(brakes[i], bsize, Quaternion.identity, Palette.BrakeOff);
            // A flat plate on top of the rear so the top-down camera sees the brake light.
            if (t != VehicleType.Motorbike) bm.Box(new Vector3(0, lightY + 0.11f, -L * 0.5f + 0.1f), new Vector3(W * 0.9f, 0.04f, 0.24f), Quaternion.identity, Palette.BrakeOff);
            v.brake = bm.BuildObject("Brake", v.root.transform, false).GetComponent<Renderer>();

            float by = lightY + 0.1f;
            float hx = t == VehicleType.Motorbike ? 0.28f : W * 0.5f;
            float hz = L * 0.5f - 0.05f;
            MeshBatcher bl = new MeshBatcher();
            bl.Box(new Vector3(-hx, by, hz), new Vector3(0.24f, 0.2f, 0.24f), Quaternion.identity, Palette.Blinker, true);
            bl.Box(new Vector3(-hx, by, -hz), new Vector3(0.24f, 0.2f, 0.24f), Quaternion.identity, Palette.Blinker, true);
            v.blinkLeft = bl.BuildObject("BlinkL", v.root.transform, false).GetComponent<Renderer>();
            MeshBatcher br = new MeshBatcher();
            br.Box(new Vector3(hx, by, hz), new Vector3(0.24f, 0.2f, 0.24f), Quaternion.identity, Palette.Blinker, true);
            br.Box(new Vector3(hx, by, -hz), new Vector3(0.24f, 0.2f, 0.24f), Quaternion.identity, Palette.Blinker, true);
            v.blinkRight = br.BuildObject("BlinkR", v.root.transform, false).GetComponent<Renderer>();
            v.blinkLeft.enabled = false;
            v.blinkRight.enabled = false;
            return v;
        }

        /// <summary>The player: bright green ojol jacket + helmet, delivery box, and a ground ring for readability.</summary>
        public static GameObject BuildPlayer(Transform parent, out Transform leanPivot, out Renderer[] blinkRenderers, out GameObject foodBox)
        {
            GameObject root = new GameObject("PlayerBike");
            root.transform.SetParent(parent, false);

            // Ground ring (does not lean).
            MeshBatcher ring = new MeshBatcher();
            int n = 16;
            for (int i = 0; i < n; i++)
            {
                float a0 = i * Mathf.PI * 2f / n, a1 = (i + 1) * Mathf.PI * 2f / n;
                Vector3 p0 = new Vector3(Mathf.Cos(a0), 0.04f, Mathf.Sin(a0)) * 1.25f;
                Vector3 p1 = new Vector3(Mathf.Cos(a1), 0.04f, Mathf.Sin(a1)) * 1.25f;
                p0.y = p1.y = 0.05f;
                ring.Beam(p0, p1, 0.16f, new Color(1f, 0.92f, 0.2f), true);
            }
            ring.BuildObject("Ring", root.transform, false);

            GameObject pivot = new GameObject("LeanPivot");
            pivot.transform.SetParent(root.transform, false);
            leanPivot = pivot.transform;

            MeshBatcher mb = new MeshBatcher();
            Color scooter = new Color(0.95f, 0.95f, 0.95f);
            Color green = Palette.OjolGreen;
            mb.BoxBottom(new Vector3(0, 0.28f, 0.05f), new Vector3(0.4f, 0.42f, 1.5f), scooter);
            mb.BoxBottom(new Vector3(0, 0.28f, 0.62f), new Vector3(0.44f, 0.75f, 0.3f), scooter);
            mb.BoxBottom(new Vector3(0, 0.7f, -0.2f), new Vector3(0.38f, 0.12f, 0.75f), new Color(0.12f, 0.12f, 0.12f));
            mb.BoxBottom(new Vector3(0, 1.0f, 0.68f), new Vector3(0.8f, 0.07f, 0.07f), Palette.Tire);
            mb.Prism(new Vector3(0, 0.3f, 0.72f), Vector3.right, 0.3f, 0.13f, 8, Palette.Tire);
            mb.Prism(new Vector3(0, 0.3f, -0.66f), Vector3.right, 0.3f, 0.15f, 8, Palette.Tire);
            // rider
            mb.BoxBottom(new Vector3(0, 0.8f, -0.1f), new Vector3(0.56f, 0.64f, 0.38f), green);
            mb.BoxBottom(new Vector3(0, 1.1f, -0.1f), new Vector3(0.58f, 0.08f, 0.4f), Palette.OjolGreenDark);
            mb.Beam(new Vector3(-0.27f, 1.3f, 0f), new Vector3(-0.38f, 1.0f, 0.62f), 0.15f, green);
            mb.Beam(new Vector3(0.27f, 1.3f, 0f), new Vector3(0.38f, 1.0f, 0.62f), 0.15f, green);
            mb.Ball(new Vector3(0, 1.66f, -0.05f), 0.25f, green);
            mb.BoxBottom(new Vector3(0, 1.62f, 0.14f), new Vector3(0.36f, 0.12f, 0.12f), Palette.Glass);
            mb.BoxBottom(new Vector3(0, 1.86f, -0.05f), new Vector3(0.08f, 0.06f, 0.46f), Palette.White);
            mb.BuildObject("Bike", pivot.transform);

            // Delivery box (the NgoJek-in thermal bag).
            MeshBatcher box = new MeshBatcher();
            box.BoxBottom(new Vector3(0, 0.85f, -0.62f), new Vector3(0.62f, 0.55f, 0.55f), Palette.OjolGreen);
            box.BoxBottom(new Vector3(0, 1.4f, -0.62f), new Vector3(0.64f, 0.04f, 0.2f), Palette.White);
            box.BoxBottom(new Vector3(0, 1.4f, -0.62f), new Vector3(0.2f, 0.045f, 0.57f), new Color(1f, 0.9f, 0.2f));
            foodBox = box.BuildObject("DeliveryBox", pivot.transform);

            MeshBatcher bl = new MeshBatcher();
            bl.Box(new Vector3(-0.25f, 0.8f, 0.8f), new Vector3(0.14f, 0.12f, 0.12f), Quaternion.identity, Palette.Blinker, true);
            MeshBatcher br = new MeshBatcher();
            br.Box(new Vector3(0.25f, 0.8f, 0.8f), new Vector3(0.14f, 0.12f, 0.12f), Quaternion.identity, Palette.Blinker, true);
            blinkRenderers = new Renderer[]
            {
                bl.BuildObject("BlinkL", pivot.transform, false).GetComponent<Renderer>(),
                br.BuildObject("BlinkR", pivot.transform, false).GetComponent<Renderer>(),
            };
            blinkRenderers[0].enabled = false;
            blinkRenderers[1].enabled = false;
            return root;
        }
    }
}
