using System.Collections.Generic;
using UnityEngine;

namespace OjolRush
{
    /// <summary>
    /// All sounds are synthesised at startup (no audio assets needed): scooter engine loop, klakson,
    /// whoosh, cha-ching, order ping, rain, crash, angkot conductor shout, meow, cluck...
    /// Swap any clip for a recorded one by assigning it in <see cref="clips"/>.
    /// </summary>
    public class AudioManager : MonoBehaviour
    {
        const int Rate = 22050;
        public readonly Dictionary<string, AudioClip> clips = new Dictionary<string, AudioClip>();
        AudioSource engine, rain;
        AudioSource[] voices;
        int nextVoice;
        GameManager gm;
        System.Random rng = new System.Random(7);
        bool rainOn;
        public float masterVolume = 0.8f;

        public void Init(GameManager game)
        {
            gm = game;
            clips["engine"] = Engine();
            clips["rain"] = Noise(2f, 0.35f, 0.15f, true);
            clips["horn_car"] = Horn(0.35f, 415f, 523f);
            clips["horn_bike"] = Horn(0.22f, 620f, 740f);
            clips["horn_bus"] = Horn(0.5f, 233f, 294f);
            clips["horn"] = clips["horn_car"];
            clips["whoosh"] = Whoosh();
            clips["chaching"] = ChaChing();
            clips["ping"] = Ping();
            clips["pickup"] = Blip(new[] { 660f, 880f }, 0.08f);
            clips["crash"] = Crash();
            clips["bump"] = Thump(0.14f, 70f);
            clips["splash"] = Noise(0.35f, 0.5f, 0.6f, false);
            clips["shout"] = Shout();
            clips["meow"] = Meow();
            clips["cluck"] = Cluck();
            clips["levelup"] = Blip(new[] { 523f, 659f, 784f, 1046f }, 0.09f);
            clips["gameover"] = Blip(new[] { 523f, 440f, 349f, 262f }, 0.16f);
            clips["siren"] = Siren();
            clips["star"] = Blip(new[] { 1318f }, 0.06f);

            engine = gameObject.AddComponent<AudioSource>();
            engine.clip = clips["engine"];
            engine.loop = true;
            engine.volume = 0f;
            engine.Play();
            rain = gameObject.AddComponent<AudioSource>();
            rain.clip = clips["rain"];
            rain.loop = true;
            rain.volume = 0f;
            rain.Play();
            voices = new AudioSource[10];
            for (int i = 0; i < voices.Length; i++)
            {
                voices[i] = gameObject.AddComponent<AudioSource>();
                voices[i].playOnAwake = false;
            }
        }

        public void Play(string name, float volume, float pitch)
        {
            AudioClip c;
            if (!clips.TryGetValue(name, out c) || c == null) return;
            AudioSource v = voices[nextVoice];
            nextVoice = (nextVoice + 1) % voices.Length;
            v.pitch = pitch;
            v.PlayOneShot(c, volume * masterVolume);
        }

        public void PlayHorn(Vector3 worldPos, VehicleType type)
        {
            float d = Vector2.Distance(Geo.XZ(worldPos), gm.player.Pos);
            float vol = Mathf.Clamp01(1f - d / 50f) * 0.55f;
            if (vol <= 0.02f) return;
            string n = type == VehicleType.Bus ? "horn_bus" : (type == VehicleType.Motorbike || type == VehicleType.Bajaj ? "horn_bike" : "horn_car");
            Play(n, vol, 0.9f + (float)rng.NextDouble() * 0.2f);
        }

        public void SetRain(bool on) { rainOn = on; }

        public void Tick(float unscaledDt, bool playing)
        {
            float targetVol = playing && gm.player.Active ? 0.16f + 0.14f * gm.player.Speed01 : 0f;
            engine.volume = Mathf.MoveTowards(engine.volume, targetVol * masterVolume, unscaledDt * 0.8f);
            engine.pitch = Mathf.Lerp(engine.pitch, 0.75f + gm.player.Speed01 * 1.1f + (gm.player.Airborne ? 0.25f : 0f), Geo.ExpLerp(6f, unscaledDt));
            rain.volume = Mathf.MoveTowards(rain.volume, (rainOn ? 0.45f : 0f) * masterVolume, unscaledDt * 0.3f);
        }

        // ------------------------------------------------------------------ synthesis

        static AudioClip Make(string name, float[] data)
        {
            AudioClip c = AudioClip.Create(name, data.Length, 1, Rate, false);
            c.SetData(data, 0);
            return c;
        }

        float Rnd() { return (float)rng.NextDouble() * 2f - 1f; }

        AudioClip Engine()
        {
            // One second loop of a small single-cylinder putter; integer cycles so it loops cleanly.
            int n = Rate;
            float[] d = new float[n];
            float f = 38f;
            float lp = 0f;
            for (int i = 0; i < n; i++)
            {
                float t = (float)i / Rate;
                float ph = Mathf.Repeat(t * f, 1f);
                float pulse = Mathf.Exp(-ph * 7f);
                float saw = ph * 2f - 1f;
                float harm = Mathf.Sin(2f * Mathf.PI * f * 2f * t) * 0.3f + Mathf.Sin(2f * Mathf.PI * f * 3f * t) * 0.15f;
                float noise = Rnd() * 0.25f * pulse;
                float s = pulse * 0.7f + saw * 0.15f + harm + noise;
                lp += (s - lp) * 0.35f;
                d[i] = lp * 0.5f;
            }
            return Make("engine", d);
        }

        AudioClip Noise(float len, float vol, float bright, bool loop)
        {
            int n = (int)(Rate * len);
            float[] d = new float[n];
            float lp = 0f;
            for (int i = 0; i < n; i++)
            {
                lp += (Rnd() - lp) * bright;
                float env = loop ? 1f : Mathf.Exp(-(float)i / n * 5f) * Mathf.Min(1f, i / (Rate * 0.01f));
                d[i] = lp * vol * env;
            }
            if (loop)
            {
                // Cross-fade the ends for a seamless loop.
                int fade = Rate / 10;
                for (int i = 0; i < fade; i++)
                {
                    float a = (float)i / fade;
                    d[i] = d[i] * a + d[n - fade + i] * (1f - a);
                }
            }
            return Make("noise", d);
        }

        AudioClip Horn(float len, float f1, float f2)
        {
            int n = (int)(Rate * len);
            float[] d = new float[n];
            for (int i = 0; i < n; i++)
            {
                float t = (float)i / Rate;
                float a = Mathf.Sign(Mathf.Sin(2f * Mathf.PI * f1 * t)) + Mathf.Sign(Mathf.Sin(2f * Mathf.PI * f2 * t));
                float env = Mathf.Min(1f, t / 0.01f) * Mathf.Min(1f, (len - t) / 0.03f);
                d[i] = a * 0.18f * env;
            }
            return Make("horn", d);
        }

        AudioClip Whoosh()
        {
            float len = 0.45f;
            int n = (int)(Rate * len);
            float[] d = new float[n];
            float lp = 0f, bp = 0f;
            for (int i = 0; i < n; i++)
            {
                float t = (float)i / n;
                float cut = Mathf.Lerp(0.05f, 0.5f, Mathf.Sin(t * Mathf.PI));
                lp += (Rnd() - lp) * cut;
                bp += (lp - bp) * 0.5f;
                float env = Mathf.Sin(t * Mathf.PI);
                d[i] = (lp - bp) * env * 1.6f;
            }
            return Make("whoosh", d);
        }

        AudioClip ChaChing()
        {
            float len = 0.8f;
            int n = (int)(Rate * len);
            float[] d = new float[n];
            for (int i = 0; i < n; i++)
            {
                float t = (float)i / Rate;
                float s = 0f;
                // "cha" click
                if (t < 0.06f) s += Rnd() * (1f - t / 0.06f) * 0.4f;
                // "ching" bells
                float t2 = t - 0.08f;
                if (t2 > 0f)
                {
                    float e = Mathf.Exp(-t2 * 5f);
                    s += (Mathf.Sin(2f * Mathf.PI * 1318f * t2) + 0.6f * Mathf.Sin(2f * Mathf.PI * 1760f * t2) + 0.3f * Mathf.Sin(2f * Mathf.PI * 2637f * t2)) * e * 0.25f;
                }
                d[i] = s;
            }
            return Make("chaching", d);
        }

        AudioClip Ping()
        {
            float len = 0.35f;
            int n = (int)(Rate * len);
            float[] d = new float[n];
            for (int i = 0; i < n; i++)
            {
                float t = (float)i / Rate;
                float f = t < 0.12f ? 1046f : 1568f;
                float tt = t < 0.12f ? t : t - 0.12f;
                d[i] = Mathf.Sin(2f * Mathf.PI * f * t) * Mathf.Exp(-tt * 12f) * 0.35f;
            }
            return Make("ping", d);
        }

        AudioClip Blip(float[] notes, float noteLen)
        {
            int per = (int)(Rate * noteLen);
            int n = per * notes.Length + Rate / 5;
            float[] d = new float[n];
            for (int k = 0; k < notes.Length; k++)
            {
                for (int i = 0; i < per + Rate / 5 && k * per + i < n; i++)
                {
                    float t = (float)i / Rate;
                    float sq = Mathf.Sin(2f * Mathf.PI * notes[k] * t) + 0.3f * Mathf.Sign(Mathf.Sin(2f * Mathf.PI * notes[k] * t));
                    d[k * per + i] += sq * Mathf.Exp(-t * 14f) * 0.22f;
                }
            }
            return Make("blip", d);
        }

        AudioClip Crash()
        {
            float len = 0.6f;
            int n = (int)(Rate * len);
            float[] d = new float[n];
            float lp = 0f;
            for (int i = 0; i < n; i++)
            {
                float t = (float)i / Rate;
                lp += (Rnd() - lp) * 0.3f;
                float thump = Mathf.Sin(2f * Mathf.PI * Mathf.Lerp(90f, 40f, t / len) * t) * Mathf.Exp(-t * 10f);
                float clang = Mathf.Sin(2f * Mathf.PI * 1250f * t) * Mathf.Sin(2f * Mathf.PI * 1893f * t) * Mathf.Exp(-t * 14f);
                d[i] = (lp * Mathf.Exp(-t * 7f) * 0.8f + thump * 0.8f + clang * 0.3f) * 0.6f;
            }
            return Make("crash", d);
        }

        AudioClip Thump(float len, float f)
        {
            int n = (int)(Rate * len);
            float[] d = new float[n];
            for (int i = 0; i < n; i++)
            {
                float t = (float)i / Rate;
                d[i] = (Mathf.Sin(2f * Mathf.PI * f * t) * 0.8f + Rnd() * 0.2f) * Mathf.Exp(-t * 25f) * 0.7f;
            }
            return Make("thump", d);
        }

        AudioClip Shout()
        {
            // A rough formant-ish "KAMPUNG MELAYUUU" yell: glides + vibrato through a resonant filter.
            float len = 0.9f;
            int n = (int)(Rate * len);
            float[] d = new float[n];
            float bp1 = 0f, bp1v = 0f, bp2 = 0f, bp2v = 0f, ph = 0f;
            for (int i = 0; i < n; i++)
            {
                float t = (float)i / len / Rate;
                float f0 = t < 0.3f ? Mathf.Lerp(210f, 260f, t / 0.3f) : Mathf.Lerp(300f, 220f, (t - 0.3f) / 0.7f);
                f0 *= 1f + Mathf.Sin(t * 60f) * 0.02f;
                ph += f0 / Rate;
                float src = Mathf.Repeat(ph, 1f) * 2f - 1f;
                float f1 = t < 0.3f ? 700f : (t < 0.6f ? 500f : 350f);
                float f2 = t < 0.3f ? 1200f : (t < 0.6f ? 1700f : 900f);
                Resonate(ref bp1, ref bp1v, src, f1, 0.08f);
                Resonate(ref bp2, ref bp2v, src, f2, 0.1f);
                float env = Mathf.Min(1f, t / 0.05f) * Mathf.Min(1f, (1f - t) / 0.15f);
                if (t > 0.27f && t < 0.31f) env *= 0.2f;
                d[i] = (bp1 * 0.6f + bp2 * 0.4f) * env * 0.25f;
            }
            return Make("shout", d);
        }

        static void Resonate(ref float y, ref float v, float x, float f, float damp)
        {
            float w = 2f * Mathf.PI * f / Rate;
            v += (x * w - y * w * w - v * damp * 2f);
            y += v;
            y = Mathf.Clamp(y, -4f, 4f);
        }

        AudioClip Meow()
        {
            float len = 0.45f;
            int n = (int)(Rate * len);
            float[] d = new float[n];
            float ph = 0f;
            for (int i = 0; i < n; i++)
            {
                float t = (float)i / n;
                float f = 600f + Mathf.Sin(t * Mathf.PI) * 450f + Mathf.Sin(t * 50f) * 20f;
                ph += f / Rate;
                float s = Mathf.Sin(2f * Mathf.PI * ph) + 0.4f * Mathf.Sin(4f * Mathf.PI * ph);
                d[i] = s * Mathf.Sin(t * Mathf.PI) * 0.25f;
            }
            return Make("meow", d);
        }

        AudioClip Cluck()
        {
            float len = 0.35f;
            int n = (int)(Rate * len);
            float[] d = new float[n];
            for (int i = 0; i < n; i++)
            {
                float t = (float)i / Rate;
                float s = 0f;
                for (int k = 0; k < 3; k++)
                {
                    float tk = t - k * 0.1f;
                    if (tk > 0f && tk < 0.07f) s += Mathf.Sign(Mathf.Sin(2f * Mathf.PI * (900f - tk * 3000f) * tk)) * Mathf.Exp(-tk * 40f);
                }
                d[i] = s * 0.2f;
            }
            return Make("cluck", d);
        }

        AudioClip Siren()
        {
            float len = 1f;
            int n = (int)(Rate * len);
            float[] d = new float[n];
            float ph = 0f;
            for (int i = 0; i < n; i++)
            {
                float t = (float)i / Rate;
                float f = Mathf.Repeat(t * 2f, 1f) < 0.5f ? 960f : 770f;
                ph += f / Rate;
                d[i] = Mathf.Sign(Mathf.Sin(2f * Mathf.PI * ph)) * 0.12f * Mathf.Min(1f, (len - t) / 0.05f);
            }
            return Make("siren", d);
        }
    }
}
