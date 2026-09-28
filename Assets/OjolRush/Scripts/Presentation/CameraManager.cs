using UnityEngine;

namespace OjolRush
{
    /// <summary>
    /// Angled top-down camera (fixed north-up yaw so thumb directions map to the map).
    /// Looks ahead in the travel direction and pulls back with speed. Handles shake and FOV kicks.
    /// </summary>
    public class CameraManager : MonoBehaviour
    {
        public Camera cam;
        GameManager gm;

        public float pitch = 58f;
        [Tooltip("Half of the visible ground width at the focus point, slow / fast.")]
        public float halfWidthSlow = 12f;
        public float halfWidthFast = 16f;
        public float lookAhead = 0.75f;

        Vector3 focus;
        Vector2 lookOffset;
        float halfWidth;
        float shake;
        float kick;
        float time;
        Color skyClear = new Color(0.98f, 0.72f, 0.45f);
        Color skyRain = new Color(0.5f, 0.56f, 0.64f);
        Plane[] planes = new Plane[6];
        bool planesValid;

        public void Init(GameManager game)
        {
            gm = game;
            GameObject go = new GameObject("OjolRushCamera");
            go.transform.SetParent(transform, false);
            cam = go.AddComponent<Camera>();
            go.AddComponent<AudioListener>();
            go.tag = "MainCamera";
            cam.fieldOfView = 55f;
            cam.nearClipPlane = 1f;
            cam.farClipPlane = 260f;
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = skyClear;
            halfWidth = halfWidthSlow;
        }

        public void Snap(Vector2 target)
        {
            focus = Geo.X0Z(target);
            lookOffset = Vector2.zero;
            halfWidth = halfWidthSlow;
            Place(0f);
        }

        public void Shake(float amount) { shake = Mathf.Max(shake, amount); }
        public void Kick(float amount) { kick = Mathf.Max(kick, amount); }

        public void SetSkyTint(float rain)
        {
            if (cam != null) cam.backgroundColor = Color.Lerp(skyClear, skyRain, rain);
        }

        public void LateTick(float dt, float unscaledDt)
        {
            time += unscaledDt;
            PlayerBikeController p = gm.player;
            Vector2 target = p.Pos;
            Vector2 wantOffset = Vector2.ClampMagnitude(p.Velocity * lookAhead, 11f);
            // Portrait screens show more ground vertically, so bias the look-ahead up-screen.
            lookOffset = Vector2.Lerp(lookOffset, wantOffset, Geo.ExpLerp(2.5f, dt));
            Vector3 want = Geo.X0Z(target + lookOffset + new Vector2(0f, 2f));
            focus = Vector3.Lerp(focus, want, Geo.ExpLerp(8f, dt));
            float wantWidth = Mathf.Lerp(halfWidthSlow, halfWidthFast, p.Speed01);
            halfWidth = Mathf.Lerp(halfWidth, wantWidth, Geo.ExpLerp(1.5f, dt));
            Place(unscaledDt);
        }

        void Place(float unscaledDt)
        {
            float aspect = Mathf.Max(0.3f, cam.aspect);
            // Keep a similar amount of street visible on wide and narrow screens.
            float hfov = 2f * Mathf.Atan(Mathf.Tan(cam.fieldOfView * 0.5f * Mathf.Deg2Rad) * aspect);
            float dist = halfWidth / Mathf.Tan(hfov * 0.5f);
            dist = Mathf.Clamp(dist, 18f, 70f);
            kick = Mathf.MoveTowards(kick, 0f, unscaledDt * 3f);
            dist *= 1f - kick * 0.06f;

            Quaternion rot = Quaternion.Euler(pitch, 0f, 0f);
            Vector3 pos = focus - rot * Vector3.forward * dist;

            shake = Mathf.MoveTowards(shake, 0f, unscaledDt * 2.2f);
            if (shake > 0f)
            {
                float s = shake * shake * 0.9f;
                pos += new Vector3((Mathf.PerlinNoise(time * 25f, 0f) - 0.5f) * s, (Mathf.PerlinNoise(0f, time * 25f) - 0.5f) * s, (Mathf.PerlinNoise(time * 25f, 7f) - 0.5f) * s);
                rot *= Quaternion.Euler(0f, 0f, (Mathf.PerlinNoise(time * 20f, 3f) - 0.5f) * s * 4f);
            }
            cam.transform.SetPositionAndRotation(pos, rot);
            planesValid = false;
        }

        public bool IsVisible(Vector3 p, float margin)
        {
            if (!planesValid)
            {
                GeometryUtility.CalculateFrustumPlanes(cam, planes);
                planesValid = true;
            }
            return GeometryUtility.TestPlanesAABB(planes, new Bounds(p + Vector3.up, Vector3.one * margin * 2f));
        }

        public Vector3 WorldToScreen(Vector3 p) { return cam.WorldToScreenPoint(p); }
    }
}
