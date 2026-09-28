using System.Collections.Generic;
using UnityEngine;

namespace OjolRush
{
    /// <summary>
    /// Immediate-mode HUD (no UI package or prefabs needed): score / timer / rating on top,
    /// helmet hearts at the bottom, order card, off-screen arrow, combo, popups, banners,
    /// title screen, pause and "SHIFT SELESAI".
    /// </summary>
    public class HUD : MonoBehaviour
    {
        class PopupItem
        {
            public Vector3 world;
            public bool screenSpace;
            public Vector2 screen;
            public string text;
            public Color color;
            public float age, life, size;
        }

        GameManager gm;
        readonly List<PopupItem> popups = new List<PopupItem>();
        readonly Dictionary<int, GUIStyle> styles = new Dictionary<int, GUIStyle>();
        Texture2D white, round, circle, ring, helmet, helmetCracked, star, arrow;
        GUIStyle roundStyle;

        string bannerText;
        Color bannerColor;
        float bannerTime;
        string bigTitle, bigSub;
        float bigTime;
        string notifyTitle, notifyBody;
        float notifyTime;
        float speedLines;
        float crashFlash;
        float helmetCrack;
        float comboPulse;
        float time;
        float u = 1f;

        public void Init(GameManager game)
        {
            gm = game;
            white = Solid();
            round = RoundRect(64, 22);
            circle = Circle(128, false);
            ring = Circle(128, true);
            helmet = Helmet(128, false);
            helmetCracked = Helmet(128, true);
            star = Star(64);
            arrow = Arrow(64);
            roundStyle = new GUIStyle();
            roundStyle.normal.background = round;
            roundStyle.border = new RectOffset(24, 24, 24, 24);
        }

        // ------------------------------------------------------------------ API

        public void Popup(Vector3 world, string text, Color color, float size = 1f)
        {
            popups.Add(new PopupItem { world = world, text = text, color = color, life = 1.1f, size = size });
        }

        public void ScreenPopup(Vector2 screenFrac, string text, Color color, float size = 1f)
        {
            popups.Add(new PopupItem { screenSpace = true, screen = screenFrac, text = text, color = color, life = 1.0f, size = size });
        }

        public void Banner(string text, Color c)
        {
            bannerText = text;
            bannerColor = c;
            bannerTime = 2.6f;
        }

        public void BigBanner(string title, string sub)
        {
            bigTitle = title;
            bigSub = sub;
            bigTime = 2.4f;
        }

        public void Notify(string title, string body)
        {
            notifyTitle = title;
            notifyBody = body;
            notifyTime = 2.8f;
        }

        public void SpeedLines() { speedLines = 0.35f; }
        public void CrashFlash(bool heavy)
        {
            crashFlash = heavy ? 0.5f : 0.2f;
            if (heavy) helmetCrack = 0.9f;
        }
        public void ComboPulse() { comboPulse = 1f; }

        public void ClearAll()
        {
            popups.Clear();
            bannerTime = bigTime = notifyTime = speedLines = crashFlash = helmetCrack = 0f;
        }

        public void Tick(float unscaledDt)
        {
            time += unscaledDt;
            for (int i = popups.Count - 1; i >= 0; i--)
            {
                popups[i].age += unscaledDt;
                if (popups[i].age > popups[i].life) popups.RemoveAt(i);
            }
            bannerTime -= unscaledDt;
            bigTime -= unscaledDt;
            notifyTime -= unscaledDt;
            speedLines -= unscaledDt;
            crashFlash -= unscaledDt;
            helmetCrack -= unscaledDt;
            comboPulse = Mathf.MoveTowards(comboPulse, 0f, unscaledDt * 4f);
        }

        /// <summary>Screen rect of the pause button in bottom-left-origin coordinates (for input blocking).</summary>
        public Rect PauseButtonScreenRect
        {
            get
            {
                Rect r = PauseRect();
                return new Rect(r.x, Screen.height - r.yMax, r.width, r.height);
            }
        }

        Rect PauseRect()
        {
            float s = 110f * U();
            return new Rect(Screen.width - s - 30f * U(), Screen.height - s - 40f * U(), s, s);
        }

        float U() { return Mathf.Min(Screen.width / 1080f, Screen.height / 1200f); }

        // ------------------------------------------------------------------ drawing

        void OnGUI()
        {
            if (gm == null) return;
            u = U();
            GUI.depth = 0;
            switch (gm.State)
            {
                case GameState.Title:
                    DrawTitle();
                    break;
                case GameState.Playing:
                    DrawPlaying();
                    if (gm.Paused) DrawPause();
                    break;
                case GameState.GameOver:
                    DrawWorldPopups();
                    DrawGameOver();
                    break;
            }
        }

        void DrawPlaying()
        {
            DrawSpeedLines();
            DrawTarget();
            DrawWorldPopups();
            DrawTopBar();
            DrawOrderCard();
            DrawCombo();
            DrawHelmets();
            DrawJoystick();
            DrawBanners();
            DrawCrash();

            Rect pr = PauseRect();
            Box(pr, new Color(0f, 0f, 0f, 0.45f));
            Label(pr, "II", 50, Color.white, TextAnchor.MiddleCenter);
            if (!gm.Paused && GUI.Button(pr, GUIContent.none, GUIStyle.none)) gm.TogglePause();
        }

        void DrawTopBar()
        {
            float w = Screen.width;
            Rect bar = new Rect(0, 0, w, 170f * u);
            GUI.color = new Color(0.05f, 0.08f, 0.1f, 0.62f);
            GUI.DrawTexture(bar, white);
            GUI.color = Color.white;

            // Score
            Label(new Rect(30 * u, 18 * u, 400 * u, 40 * u), "SKOR", 30, new Color(1f, 1f, 1f, 0.7f), TextAnchor.UpperLeft);
            Label(new Rect(30 * u, 55 * u, 450 * u, 90 * u), FormatNum(gm.score.Score), 64, Color.white, TextAnchor.UpperLeft);

            // Timer
            Order o = gm.orders.Current;
            string timer = "--";
            Color tc = Color.white;
            float pulse = 1f;
            if (o != null)
            {
                int t = Mathf.CeilToInt(o.timeLeft);
                timer = (t / 60) + ":" + (t % 60).ToString("00");
                if (o.timeLeft < 10f)
                {
                    tc = Color.Lerp(new Color(1f, 0.3f, 0.2f), Color.white, Mathf.PingPong(time * 4f, 1f) * 0.4f);
                    pulse = 1f + Mathf.Abs(Mathf.Sin(time * 6f)) * 0.08f;
                }
            }
            else if (gm.orders.NextOrderIn > 0f)
            {
                timer = "...";
            }
            Label(new Rect(w * 0.5f - 200 * u, 18 * u, 400 * u, 40 * u), "WAKTU", 30, new Color(1f, 1f, 1f, 0.7f), TextAnchor.UpperCenter);
            Label(new Rect(w * 0.5f - 200 * u, 50 * u, 400 * u, 100 * u), timer, (int)(80 * pulse), tc, TextAnchor.UpperCenter);

            // Rating
            float rating = gm.rating.Average;
            Label(new Rect(w - 430 * u, 18 * u, 400 * u, 40 * u), "RATING " + rating.ToString("0.0"), 30, RatingColor(rating), TextAnchor.UpperRight);
            float sz = 58f * u;
            for (int i = 0; i < 5; i++)
            {
                Rect r = new Rect(w - 30 * u - (5 - i) * (sz + 6 * u), 62 * u, sz, sz);
                float fill = Mathf.Clamp01(rating - i);
                GUI.color = new Color(0.25f, 0.25f, 0.25f, 0.9f);
                GUI.DrawTexture(r, star);
                if (fill > 0f)
                {
                    GUI.color = new Color(1f, 0.82f, 0.15f);
                    GUI.DrawTextureWithTexCoords(new Rect(r.x, r.y, r.width * fill, r.height), star, new Rect(0, 0, fill, 1));
                }
            }
            GUI.color = Color.white;

            // Rush level chip
            RushLevelConfig l = gm.rush.Level;
            Rect chip = new Rect(20 * u, 185 * u, 470 * u, 58 * u);
            GUI.color = RushColor(gm.rush.LevelNumber);
            GUI.Box(chip, GUIContent.none, roundStyle);
            GUI.color = Color.white;
            Label(chip, "RUSH " + gm.rush.LevelNumber + " · " + l.title, 30, Color.white, TextAnchor.MiddleCenter);
        }

        void DrawOrderCard()
        {
            float w = Screen.width;
            Order o = gm.orders.Current;
            float y = 258f * u;
            float slide = notifyTime > 2.4f ? (notifyTime - 2.4f) / 0.4f : 0f;
            Rect card = new Rect(20 * u, y - slide * 200f * u, w - 40 * u, 150 * u);
            if (card.width > 1000 * u) card.width = 1000 * u;
            GUI.color = new Color(1f, 1f, 1f, 0.93f);
            GUI.Box(card, GUIContent.none, roundStyle);
            GUI.color = Palette.OjolGreen;
            GUI.Box(new Rect(card.x, card.y, 190 * u, card.height), GUIContent.none, roundStyle);
            GUI.color = Color.white;
            Label(new Rect(card.x, card.y + 10 * u, 190 * u, 50 * u), "NgoJek-in", 30, Color.white, TextAnchor.UpperCenter, false);
            Rect inner = new Rect(card.x + 210 * u, card.y + 12 * u, card.width - 230 * u, card.height - 24 * u);
            Color dark = new Color(0.12f, 0.14f, 0.16f);
            if (o == null)
            {
                Label(new Rect(card.x, card.y + 60 * u, 190 * u, 60 * u), "...", 50, Color.white, TextAnchor.UpperCenter, false);
                Label(inner, "Mencari order...", 38, dark, TextAnchor.MiddleLeft, false);
                return;
            }
            bool pickup = o.stage == OrderStage.Pickup;
            Label(new Rect(card.x, card.y + 60 * u, 190 * u, 70 * u), pickup ? "AMBIL" : "ANTAR", 40, Color.white, TextAnchor.UpperCenter, false);
            Label(new Rect(inner.x, inner.y, inner.width, 50 * u), pickup ? o.pickup.name : o.dropoff.name, 40, dark, TextAnchor.UpperLeft, false);
            string type = o.type == OrderType.Food ? "Makanan" : "Paket";
            Vector2? tp = gm.orders.TargetPosition;
            float dist = tp.HasValue ? Vector2.Distance(tp.Value, gm.player.Pos) : 0f;
            string pen = o.penalty > 0 ? "  (-" + o.penalty + " bintang)" : "";
            Label(new Rect(inner.x, inner.y + 58 * u, inner.width, 60 * u), type + ": " + o.item + "  ·  " + Mathf.RoundToInt(dist) + " m" + pen, 30,
                o.penalty > 0 ? new Color(0.8f, 0.2f, 0.15f) : new Color(0.3f, 0.33f, 0.36f), TextAnchor.UpperLeft, false);
            // time bar
            float f = Mathf.Clamp01(o.timeLeft / o.timeTotal);
            Rect bar = new Rect(inner.x, card.yMax - 20 * u, inner.width, 8 * u);
            Box(bar, new Color(0f, 0f, 0f, 0.12f));
            Box(new Rect(bar.x, bar.y, bar.width * f, bar.height), f > 0.45f ? Palette.OjolGreen : (f > 0.25f ? new Color(1f, 0.75f, 0.1f) : new Color(1f, 0.3f, 0.2f)));

            if (notifyTime > 0f && notifyTitle != null)
            {
                float a = Mathf.Clamp01(notifyTime / 0.4f);
                Rect n = new Rect(card.x, card.yMax + 12 * u, card.width, 110 * u);
                GUI.color = new Color(0.1f, 0.12f, 0.14f, 0.85f * a);
                GUI.Box(n, GUIContent.none, roundStyle);
                GUI.color = Color.white;
                Label(new Rect(n.x + 24 * u, n.y + 8 * u, n.width - 48 * u, 40 * u), notifyTitle, 30, new Color(0.5f, 1f, 0.6f, a), TextAnchor.UpperLeft, false);
                Label(new Rect(n.x + 24 * u, n.y + 44 * u, n.width - 48 * u, 70 * u), notifyBody, 26, new Color(1f, 1f, 1f, a), TextAnchor.UpperLeft, false);
            }
        }

        void DrawTarget()
        {
            Vector2? tp = gm.orders.TargetPosition;
            if (!tp.HasValue) return;
            bool pickup = gm.orders.Current.stage == OrderStage.Pickup;
            Color c = pickup ? new Color(1f, 0.6f, 0.1f) : Palette.OjolGreen;
            Vector3 world = Geo.X0Z(tp.Value, 6f);
            Vector3 sp = gm.cameraManager.WorldToScreen(world);
            float w = Screen.width, h = Screen.height;
            float top = 420f * u, bottom = 230f * u, side = 70f * u;
            Vector2 gp = new Vector2(sp.x, h - sp.y);
            bool behind = sp.z < 0f;
            bool onScreen = !behind && gp.x > side && gp.x < w - side && gp.y > top && gp.y < h - bottom;
            float dist = Vector2.Distance(tp.Value, gm.player.Pos);
            if (onScreen)
            {
                float bob = Mathf.Sin(time * 6f) * 12f * u;
                Rect r = new Rect(gp.x - 40 * u, gp.y - 110 * u + bob, 80 * u, 80 * u);
                GUIUtility.RotateAroundPivot(180f, r.center);
                GUI.color = c;
                GUI.DrawTexture(r, arrow);
                GUI.matrix = Matrix4x4.identity;
                GUI.color = Color.white;
                return;
            }
            // Off-screen: arrow on the screen edge pointing at the target.
            Vector2 center = new Vector2(w * 0.5f, (top + h - bottom) * 0.5f);
            Vector2 d = gp - center;
            if (behind) d = -d;
            if (d.sqrMagnitude < 1f) d = Vector2.down;
            float halfW = w * 0.5f - side, halfH = (h - bottom - top) * 0.5f;
            float k = Mathf.Min(halfW / Mathf.Max(0.001f, Mathf.Abs(d.x)), halfH / Mathf.Max(0.001f, Mathf.Abs(d.y)));
            Vector2 at = center + d * k;
            float ang = Mathf.Atan2(d.x, -d.y) * Mathf.Rad2Deg;
            float s = 110f * u * (1f + Mathf.Sin(time * 8f) * 0.06f);
            Rect ar = new Rect(at.x - s * 0.5f, at.y - s * 0.5f, s, s);
            GUIUtility.RotateAroundPivot(ang, ar.center);
            GUI.color = new Color(0f, 0f, 0f, 0.5f);
            GUI.DrawTexture(new Rect(ar.x + 4 * u, ar.y + 4 * u, ar.width, ar.height), arrow);
            GUI.color = c;
            GUI.DrawTexture(ar, arrow);
            GUI.matrix = Matrix4x4.identity;
            GUI.color = Color.white;
            Vector2 lp = at - d.normalized * 95f * u;
            Label(new Rect(lp.x - 120 * u, lp.y - 25 * u, 240 * u, 50 * u), Mathf.RoundToInt(dist) + " m", 34, c, TextAnchor.MiddleCenter);
        }

        void DrawCombo()
        {
            ComboSystem combo = gm.combo;
            if (combo.Count < 1) return;
            float w = Screen.width;
            float scale = 1f + comboPulse * 0.35f;
            string t = combo.Count > 1 ? "SALIP x" + combo.Multiplier + "!" : "SALIP!";
            Color c = Color.Lerp(new Color(1f, 0.9f, 0.2f), new Color(1f, 0.35f, 0.9f), Mathf.Clamp01((combo.Count - 1) / 8f));
            Rect r = new Rect(0, Screen.height * 0.3f, w, 110 * u);
            Label(r, t, (int)(76 * scale), c, TextAnchor.MiddleCenter);
            Rect bar = new Rect(w * 0.5f - 180 * u, r.yMax, 360 * u, 12 * u);
            Box(bar, new Color(0f, 0f, 0f, 0.35f));
            Box(new Rect(bar.x, bar.y, bar.width * combo.WindowLeft, bar.height), c);
        }

        void DrawHelmets()
        {
            float s = 110f * u;
            float y = Screen.height - s - 40f * u;
            int max = gm.config.helmets;
            for (int i = 0; i < max; i++)
            {
                bool alive = i < gm.player.Helmets;
                Rect r = new Rect(30 * u + i * (s + 16 * u), y, s, s);
                GUI.color = new Color(0f, 0f, 0f, 0.4f);
                GUI.DrawTexture(new Rect(r.x + 4 * u, r.y + 5 * u, r.width, r.height), alive ? helmet : helmetCracked);
                GUI.color = alive ? Palette.OjolGreen : new Color(0.45f, 0.45f, 0.45f, 0.8f);
                if (alive && i == gm.player.Helmets - 1 && gm.player.Helmets == 1) GUI.color = Color.Lerp(Palette.OjolGreen, new Color(1f, 0.3f, 0.2f), Mathf.PingPong(time * 3f, 1f));
                GUI.DrawTexture(r, alive ? helmet : helmetCracked);
            }
            GUI.color = Color.white;
        }

        void DrawJoystick()
        {
            PlayerInput input = gm.input;
            float rad = input.Radius;
            if (input.mode == ControlMode.Joystick)
            {
                Vector2 c = input.JoystickCenter;
                Vector2 k = input.TouchActive ? input.Knob : c;
                DrawStick(c, k, rad, 0.5f);
            }
            else if (input.TouchActive)
            {
                DrawStick(input.Origin, input.Knob, rad, 0.25f);
            }
        }

        void DrawStick(Vector2 c, Vector2 k, float rad, float alpha)
        {
            Vector2 gc = new Vector2(c.x, Screen.height - c.y);
            Vector2 gk = new Vector2(k.x, Screen.height - k.y);
            GUI.color = new Color(1f, 1f, 1f, alpha);
            GUI.DrawTexture(new Rect(gc.x - rad, gc.y - rad, rad * 2f, rad * 2f), ring);
            GUI.color = new Color(1f, 1f, 1f, alpha + 0.2f);
            float kr = rad * 0.45f;
            GUI.DrawTexture(new Rect(gk.x - kr, gk.y - kr, kr * 2f, kr * 2f), circle);
            GUI.color = Color.white;
        }

        void DrawWorldPopups()
        {
            for (int i = 0; i < popups.Count; i++)
            {
                PopupItem p = popups[i];
                float t = p.age / p.life;
                Vector2 gp;
                if (p.screenSpace)
                {
                    gp = new Vector2(p.screen.x * Screen.width, p.screen.y * Screen.height);
                }
                else
                {
                    Vector3 sp = gm.cameraManager.WorldToScreen(p.world);
                    if (sp.z < 0f) continue;
                    gp = new Vector2(sp.x, Screen.height - sp.y);
                }
                gp.y -= t * 90f * u;
                float pop = t < 0.15f ? Mathf.Lerp(0.5f, 1.2f, t / 0.15f) : Mathf.Lerp(1.2f, 1f, Mathf.Clamp01((t - 0.15f) / 0.2f));
                Color c = p.color;
                c.a = t > 0.7f ? 1f - (t - 0.7f) / 0.3f : 1f;
                Label(new Rect(gp.x - 400 * u, gp.y - 50 * u, 800 * u, 100 * u), p.text, (int)(48 * p.size * pop), c, TextAnchor.MiddleCenter);
            }
        }

        void DrawBanners()
        {
            float w = Screen.width;
            if (bannerTime > 0f && bannerText != null)
            {
                float a = Mathf.Clamp01(bannerTime / 0.4f) * Mathf.Clamp01((2.6f - bannerTime) / 0.2f + 0.01f);
                Rect r = new Rect(40 * u, Screen.height * 0.62f, w - 80 * u, 100 * u);
                GUI.color = new Color(0f, 0f, 0f, 0.55f * a);
                GUI.Box(r, GUIContent.none, roundStyle);
                GUI.color = Color.white;
                Color c = bannerColor;
                c.a = a;
                Label(r, bannerText, 42, c, TextAnchor.MiddleCenter);
            }
            if (bigTime > 0f && bigTitle != null)
            {
                float t = 2.4f - bigTime;
                float s = t < 0.2f ? Mathf.Lerp(2f, 1f, t / 0.2f) : 1f;
                float a = Mathf.Clamp01(bigTime / 0.4f);
                Label(new Rect(0, Screen.height * 0.4f, w, 160 * u), bigTitle, (int)(120 * s), new Color(1f, 0.85f, 0.2f, a), TextAnchor.MiddleCenter);
                Label(new Rect(0, Screen.height * 0.4f + 150 * u, w, 70 * u), bigSub, 44, new Color(1f, 1f, 1f, a), TextAnchor.MiddleCenter);
            }
        }

        void DrawSpeedLines()
        {
            if (speedLines <= 0f) return;
            float a = speedLines / 0.35f;
            float w = Screen.width, h = Screen.height;
            GUI.color = new Color(1f, 1f, 1f, 0.55f * a);
            System.Random r = new System.Random((int)(time * 30f));
            for (int i = 0; i < 18; i++)
            {
                float y = (float)r.NextDouble() * h;
                float len = (0.12f + (float)r.NextDouble() * 0.18f) * w;
                float th = (3f + (float)r.NextDouble() * 4f) * u;
                bool left = i % 2 == 0;
                GUI.DrawTexture(new Rect(left ? 0 : w - len, y, len * (1f - a * 0.3f), th), white);
            }
            GUI.color = Color.white;
        }

        void DrawCrash()
        {
            if (crashFlash > 0f)
            {
                GUI.color = new Color(1f, 0.1f, 0.05f, crashFlash * 0.5f);
                GUI.DrawTexture(new Rect(0, 0, Screen.width, Screen.height), white);
                GUI.color = Color.white;
            }
            if (helmetCrack > 0f)
            {
                float t = 0.9f - helmetCrack;
                float s = 300f * u * (t < 0.1f ? Mathf.Lerp(1.6f, 1f, t / 0.1f) : 1f);
                float a = Mathf.Clamp01(helmetCrack / 0.3f);
                Rect r = new Rect(Screen.width * 0.5f - s * 0.5f, Screen.height * 0.45f - s * 0.5f, s, s);
                GUI.color = new Color(1f, 1f, 1f, a);
                GUI.DrawTexture(r, helmetCracked);
                GUI.color = Color.white;
            }
        }

        // ------------------------------------------------------------------ screens

        void DrawTitle()
        {
            float w = Screen.width, h = Screen.height;
            GUI.color = new Color(0.05f, 0.05f, 0.08f, 0.45f);
            GUI.DrawTexture(new Rect(0, 0, w, h), white);
            GUI.color = Color.white;
            float bob = Mathf.Sin(time * 2f) * 8f * u;
            Label(new Rect(0, h * 0.14f + bob, w, 200 * u), "OJOL", 170, Palette.OjolGreen, TextAnchor.MiddleCenter);
            Label(new Rect(0, h * 0.14f + 170 * u + bob, w, 200 * u), "RUSH", 170, new Color(1f, 0.82f, 0.15f), TextAnchor.MiddleCenter);
            Label(new Rect(60 * u, h * 0.14f + 380 * u, w - 120 * u, 120 * u), "Kamu bukan yang tercepat.\nKamu jagonya nyelip.", 40, Color.white, TextAnchor.MiddleCenter);

            Rect b = new Rect(w * 0.5f - 300 * u, h * 0.6f, 600 * u, 150 * u);
            if (BigButton(b, "MULAI SHIFT", Palette.OjolGreen)) gm.StartRun();
            DrawControlToggle(new Rect(w * 0.5f - 300 * u, b.yMax + 40 * u, 600 * u, 90 * u));
            Label(new Rect(0, b.yMax + 150 * u, w, 60 * u), "Skor terbaik: " + FormatNum(gm.BestScore), 36, new Color(1f, 1f, 1f, 0.85f), TextAnchor.MiddleCenter);
            Label(new Rect(40 * u, h - 150 * u, w - 80 * u, 120 * u),
                "Seret jempol = arah motor · Tahan diam = pelan\nSalip mepet = poin · Antar sebelum waktu habis", 28, new Color(1f, 1f, 1f, 0.75f), TextAnchor.MiddleCenter);
        }

        void DrawControlToggle(Rect r)
        {
            string label = "Kontrol: " + (gm.input.mode == ControlMode.Drag ? "SERET (bebas)" : "JOYSTICK (tetap)");
            if (BigButton(r, label, new Color(0.2f, 0.25f, 0.3f), 36))
                gm.SetControlMode(gm.input.mode == ControlMode.Drag ? ControlMode.Joystick : ControlMode.Drag);
        }

        void DrawPause()
        {
            float w = Screen.width, h = Screen.height;
            GUI.color = new Color(0f, 0f, 0f, 0.6f);
            GUI.DrawTexture(new Rect(0, 0, w, h), white);
            GUI.color = Color.white;
            Label(new Rect(0, h * 0.25f, w, 150 * u), "ISTIRAHAT DULU", 90, Color.white, TextAnchor.MiddleCenter);
            Rect b = new Rect(w * 0.5f - 300 * u, h * 0.45f, 600 * u, 140 * u);
            if (BigButton(b, "LANJUT", Palette.OjolGreen)) gm.TogglePause();
            if (BigButton(new Rect(b.x, b.yMax + 30 * u, b.width, 120 * u), "ULANG SHIFT", new Color(0.85f, 0.35f, 0.2f), 44)) gm.StartRun();
            DrawControlToggle(new Rect(b.x, b.yMax + 180 * u, b.width, 90 * u));
        }

        void DrawGameOver()
        {
            float w = Screen.width, h = Screen.height;
            GUI.color = new Color(0.03f, 0.03f, 0.05f, 0.72f);
            GUI.DrawTexture(new Rect(0, 0, w, h), white);
            GUI.color = Color.white;
            float y = h * 0.1f;
            Label(new Rect(0, y, w, 150 * u), "SHIFT SELESAI", 100, new Color(1f, 0.82f, 0.15f), TextAnchor.MiddleCenter);
            Label(new Rect(40 * u, y + 140 * u, w - 80 * u, 70 * u), gm.GameOverReason, 38, new Color(1f, 0.5f, 0.4f), TextAnchor.MiddleCenter);
            Label(new Rect(0, y + 240 * u, w, 60 * u), "SKOR", 36, new Color(1f, 1f, 1f, 0.7f), TextAnchor.MiddleCenter);
            Label(new Rect(0, y + 290 * u, w, 150 * u), FormatNum(gm.score.Score), 130, Color.white, TextAnchor.MiddleCenter);
            bool newBest = gm.NewBest;
            Label(new Rect(0, y + 440 * u, w, 60 * u), newBest ? "REKOR BARU!" : "Terbaik: " + FormatNum(gm.BestScore), 42,
                newBest ? Color.Lerp(new Color(1f, 0.85f, 0.2f), Palette.OjolGreen, Mathf.PingPong(time * 2f, 1f)) : new Color(1f, 1f, 1f, 0.8f), TextAnchor.MiddleCenter);

            string stats = "Antaran: " + gm.score.Deliveries + "     Salip: " + gm.score.NearMisses +
                           "\nCombo terbaik: x" + gm.combo.Best + "     Rating: " + gm.rating.Average.ToString("0.0") +
                           "\nTip: " + FormatNum(gm.score.TotalTips) + "     Rush tertinggi: " + gm.rush.LevelNumber;
            Label(new Rect(40 * u, y + 530 * u, w - 80 * u, 200 * u), stats, 34, new Color(0.9f, 0.95f, 1f), TextAnchor.MiddleCenter);

            Rect b = new Rect(w * 0.5f - 300 * u, h * 0.72f, 600 * u, 160 * u);
            if (gm.GameOverTime > 0.6f && BigButton(b, "LAGI", Palette.OjolGreen, 80)) gm.StartRun();
            DrawControlToggle(new Rect(b.x, b.yMax + 40 * u, b.width, 90 * u));
        }

        bool BigButton(Rect r, string text, Color c, int size = 60)
        {
            bool hover = r.Contains(Event.current.mousePosition);
            GUI.color = new Color(0f, 0f, 0f, 0.35f);
            GUI.Box(new Rect(r.x, r.y + 8 * u, r.width, r.height), GUIContent.none, roundStyle);
            GUI.color = hover ? Color.Lerp(c, Color.white, 0.15f) : c;
            GUI.Box(r, GUIContent.none, roundStyle);
            GUI.color = Color.white;
            Label(r, text, size, Color.white, TextAnchor.MiddleCenter);
            return GUI.Button(r, GUIContent.none, GUIStyle.none);
        }

        // ------------------------------------------------------------------ helpers

        void Box(Rect r, Color c)
        {
            GUI.color = c;
            GUI.DrawTexture(r, white);
            GUI.color = Color.white;
        }

        GUIStyle Style(int size, TextAnchor anchor)
        {
            int px = Mathf.Max(8, Mathf.RoundToInt(size * u));
            int key = px * 16 + (int)anchor;
            GUIStyle s;
            if (!styles.TryGetValue(key, out s))
            {
                s = new GUIStyle(GUI.skin.label);
                s.fontSize = px;
                s.fontStyle = FontStyle.Bold;
                s.alignment = anchor;
                s.wordWrap = true;
                s.clipping = TextClipping.Overflow;
                s.richText = false;
                styles[key] = s;
            }
            return s;
        }

        void Label(Rect r, string text, int size, Color c, TextAnchor anchor, bool outline = true)
        {
            GUIStyle s = Style(size, anchor);
            if (outline)
            {
                float o = Mathf.Max(1f, 3f * u * size / 50f);
                s.normal.textColor = new Color(0.05f, 0.05f, 0.08f, c.a * 0.9f);
                GUI.Label(new Rect(r.x - o, r.y, r.width, r.height), text, s);
                GUI.Label(new Rect(r.x + o, r.y, r.width, r.height), text, s);
                GUI.Label(new Rect(r.x, r.y - o, r.width, r.height), text, s);
                GUI.Label(new Rect(r.x, r.y + o * 1.6f, r.width, r.height), text, s);
            }
            s.normal.textColor = c;
            GUI.Label(r, text, s);
        }

        static string FormatNum(int n) { return n.ToString("#,0").Replace(',', '.'); }

        static Color RatingColor(float r)
        {
            if (r >= 4.5f) return new Color(0.6f, 1f, 0.6f);
            if (r >= 3.8f) return new Color(1f, 0.9f, 0.4f);
            return new Color(1f, 0.45f, 0.35f);
        }

        static Color RushColor(int lvl)
        {
            switch (lvl)
            {
                case 1: return new Color(0.2f, 0.6f, 0.35f, 0.9f);
                case 2: return new Color(0.75f, 0.6f, 0.1f, 0.9f);
                case 3: return new Color(0.25f, 0.45f, 0.8f, 0.9f);
                case 4: return new Color(0.85f, 0.4f, 0.1f, 0.9f);
                default: return new Color(0.8f, 0.12f, 0.15f, 0.95f);
            }
        }

        // ------------------------------------------------------------------ procedural textures

        static Texture2D NewTex(int size)
        {
            Texture2D t = new Texture2D(size, size, TextureFormat.RGBA32, false);
            t.wrapMode = TextureWrapMode.Clamp;
            t.filterMode = FilterMode.Bilinear;
            return t;
        }

        static Texture2D Solid()
        {
            Texture2D t = new Texture2D(1, 1);
            t.SetPixel(0, 0, Color.white);
            t.Apply();
            return t;
        }

        static Texture2D RoundRect(int size, float radius)
        {
            Texture2D t = NewTex(size);
            for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    float cx = Mathf.Clamp(x + 0.5f, radius, size - radius);
                    float cy = Mathf.Clamp(y + 0.5f, radius, size - radius);
                    float d = Vector2.Distance(new Vector2(x + 0.5f, y + 0.5f), new Vector2(cx, cy));
                    t.SetPixel(x, y, new Color(1, 1, 1, Mathf.Clamp01(radius - d + 0.5f)));
                }
            t.Apply();
            return t;
        }

        static Texture2D Circle(int size, bool ringOnly)
        {
            Texture2D t = NewTex(size);
            float r = size * 0.5f - 1f;
            for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    float d = Vector2.Distance(new Vector2(x + 0.5f, y + 0.5f), new Vector2(size * 0.5f, size * 0.5f));
                    float a = Mathf.Clamp01(r - d);
                    if (ringOnly) a *= Mathf.Clamp01(d - (r - 8f));
                    t.SetPixel(x, y, new Color(1, 1, 1, a));
                }
            t.Apply();
            return t;
        }

        static Texture2D Helmet(int size, bool cracked)
        {
            Texture2D t = NewTex(size);
            Vector2 c = new Vector2(size * 0.5f, size * 0.42f);
            float r = size * 0.42f;
            for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    Vector2 p = new Vector2(x + 0.5f, y + 0.5f);
                    float a = 0f;
                    // dome (texture y goes up)
                    if (p.y >= c.y - 2f) a = Mathf.Clamp01(r - Vector2.Distance(p, c));
                    // brim / chin
                    if (p.y >= size * 0.22f && p.y < c.y && p.x > c.x - r && p.x < c.x + r * 1.08f) a = 1f;
                    Color col = new Color(1, 1, 1, a);
                    // visor (darker band)
                    if (a > 0f && p.y > c.y + r * 0.05f && p.y < c.y + r * 0.42f && p.x > c.x + r * 0.05f) col = new Color(0.35f, 0.35f, 0.4f, a);
                    // stripe
                    if (a > 0f && Mathf.Abs(p.x - (c.x - r * 0.25f)) < size * 0.035f && p.y > c.y) col = new Color(1f, 1f, 1f, a) * 1f;
                    if (cracked && a > 0f)
                    {
                        float zig = c.x + Mathf.Sin(p.y * 0.35f) * size * 0.06f + (p.y - c.y) * 0.3f;
                        if (Mathf.Abs(p.x - zig) < size * 0.03f) col = new Color(0, 0, 0, 0);
                        float zig2 = c.y + Mathf.Sin(p.x * 0.4f) * size * 0.04f;
                        if (p.x > zig && Mathf.Abs(p.y - zig2) < size * 0.02f) col = new Color(0, 0, 0, 0);
                    }
                    t.SetPixel(x, y, col);
                }
            t.Apply();
            return t;
        }

        static Texture2D Star(int size)
        {
            Texture2D t = NewTex(size);
            Vector2[] pts = new Vector2[10];
            Vector2 c = new Vector2(size * 0.5f, size * 0.48f);
            for (int i = 0; i < 10; i++)
            {
                float a = Mathf.PI / 2f + i * Mathf.PI / 5f;
                float r = (i % 2 == 0 ? 0.48f : 0.2f) * size;
                pts[i] = c + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * r;
            }
            for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    int hits = 0;
                    for (int sx = 0; sx < 2; sx++)
                        for (int sy = 0; sy < 2; sy++)
                            if (InPoly(new Vector2(x + 0.25f + sx * 0.5f, y + 0.25f + sy * 0.5f), pts)) hits++;
                    t.SetPixel(x, y, new Color(1, 1, 1, hits / 4f));
                }
            t.Apply();
            return t;
        }

        static Texture2D Arrow(int size)
        {
            // Points up on screen (GUI draws texture row 0 at the bottom of the rect).
            Texture2D t = NewTex(size);
            Vector2[] pts = { new Vector2(size * 0.5f, size * 0.95f), new Vector2(size * 0.95f, size * 0.25f), new Vector2(size * 0.5f, size * 0.42f), new Vector2(size * 0.05f, size * 0.25f) };
            for (int y = 0; y < size; y++)
                for (int x = 0; x < size; x++)
                {
                    int hits = 0;
                    for (int sx = 0; sx < 2; sx++)
                        for (int sy = 0; sy < 2; sy++)
                            if (InPoly(new Vector2(x + 0.25f + sx * 0.5f, y + 0.25f + sy * 0.5f), pts)) hits++;
                    t.SetPixel(x, y, new Color(1, 1, 1, hits / 4f));
                }
            t.Apply();
            return t;
        }

        static bool InPoly(Vector2 p, Vector2[] poly)
        {
            bool inside = false;
            for (int i = 0, j = poly.Length - 1; i < poly.Length; j = i++)
            {
                if (((poly[i].y > p.y) != (poly[j].y > p.y)) &&
                    (p.x < (poly[j].x - poly[i].x) * (p.y - poly[i].y) / (poly[j].y - poly[i].y) + poly[i].x))
                    inside = !inside;
            }
            return inside;
        }
    }
}
