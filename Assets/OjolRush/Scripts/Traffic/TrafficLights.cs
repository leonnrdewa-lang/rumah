using UnityEngine;

namespace OjolRush
{
    public enum LightState { Green, Yellow, Red }

    /// <summary>Two-phase signals (east-west / north-south) per intersection with random offsets.</summary>
    public class TrafficLights
    {
        const float Yellow = 2f;
        const float AllRed = 2f;
        readonly float[] offsets;
        readonly int nx;
        public float green = 9f;

        public TrafficLights(int nx, int nz, System.Random rng)
        {
            this.nx = nx;
            offsets = new float[nx * nz];
            for (int i = 0; i < offsets.Length; i++) offsets[i] = (float)rng.NextDouble() * 30f;
        }

        public float Cycle { get { return 2f * (green + Yellow + AllRed); } }

        public LightState State(int i, int j, bool horizontal, float time)
        {
            float t = Mathf.Repeat(time + offsets[j * nx + i], Cycle);
            float half = green + Yellow + AllRed;
            if (!horizontal) t = Mathf.Repeat(t + half, Cycle);
            if (t < green) return LightState.Green;
            if (t < green + Yellow) return LightState.Yellow;
            return LightState.Red;
        }
    }
}
