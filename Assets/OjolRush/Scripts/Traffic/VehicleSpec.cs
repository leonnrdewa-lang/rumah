using UnityEngine;

namespace OjolRush
{
    public enum VehicleType { Car, Angkot, Bajaj, Bus, Motorbike }

    public class VehicleSpec
    {
        public float length, width, maxSpeed, accel, decel, hardDecel, laneChangeRate;

        /// <summary>Per-type handling: angkot brake hard, bajaj are slow, bikes are quick and nervy.</summary>
        public static VehicleSpec For(VehicleType t)
        {
            switch (t)
            {
                case VehicleType.Angkot: return new VehicleSpec { length = 4.6f, width = 1.85f, maxSpeed = 10.5f, accel = 3f, decel = 6f, hardDecel = 11f, laneChangeRate = 0.04f };
                case VehicleType.Bajaj: return new VehicleSpec { length = 2.6f, width = 1.35f, maxSpeed = 7f, accel = 2f, decel = 5f, hardDecel = 8f, laneChangeRate = 0f };
                case VehicleType.Bus: return new VehicleSpec { length = 11f, width = 2.5f, maxSpeed = 9f, accel = 1.4f, decel = 4f, hardDecel = 7f, laneChangeRate = 0.01f };
                case VehicleType.Motorbike: return new VehicleSpec { length = 1.9f, width = 0.75f, maxSpeed = 13.5f, accel = 4.5f, decel = 8f, hardDecel = 12f, laneChangeRate = 0.15f };
                default: return new VehicleSpec { length = 4.2f, width = 1.8f, maxSpeed = 12.5f, accel = 3f, decel = 6.5f, hardDecel = 10f, laneChangeRate = 0.07f };
            }
        }
    }

    /// <summary>Palette used across the game (chunky toy colours, golden-hour friendly).</summary>
    public static class Palette
    {
        public static readonly Color OjolGreen = new Color(0.13f, 0.78f, 0.33f);
        public static readonly Color OjolGreenDark = new Color(0.05f, 0.5f, 0.2f);
        public static readonly Color AngkotBlue = new Color(0.12f, 0.44f, 0.85f);
        public static readonly Color BajajOrange = new Color(0.95f, 0.5f, 0.1f);
        public static readonly Color Tire = new Color(0.08f, 0.08f, 0.09f);
        public static readonly Color Glass = new Color(0.16f, 0.22f, 0.3f);
        public static readonly Color White = new Color(0.95f, 0.95f, 0.92f);
        public static readonly Color BrakeOff = new Color(0.35f, 0.05f, 0.05f);
        public static readonly Color BrakeOn = new Color(1f, 0.1f, 0.08f);
        public static readonly Color Blinker = new Color(1f, 0.62f, 0.05f);
        public static readonly Color Skin = new Color(0.78f, 0.56f, 0.4f);

        public static readonly Color[] CarColors =
        {
            new Color(0.92f, 0.92f, 0.9f), new Color(0.2f, 0.2f, 0.22f), new Color(0.72f, 0.74f, 0.78f),
            new Color(0.75f, 0.12f, 0.12f), new Color(0.18f, 0.3f, 0.6f), new Color(0.95f, 0.8f, 0.2f),
            new Color(0.45f, 0.55f, 0.35f), new Color(0.55f, 0.35f, 0.25f),
        };

        public static readonly Color[] JacketColors =
        {
            new Color(0.2f, 0.25f, 0.5f), new Color(0.7f, 0.15f, 0.15f), new Color(0.25f, 0.25f, 0.25f),
            new Color(0.85f, 0.75f, 0.3f), new Color(0.5f, 0.3f, 0.6f), new Color(0.3f, 0.55f, 0.75f),
            new Color(0.1f, 0.6f, 0.3f), // rival ojol
        };

        public static readonly Color[] BusColors =
        {
            new Color(0.85f, 0.25f, 0.15f), new Color(0.15f, 0.45f, 0.75f), new Color(0.2f, 0.6f, 0.35f),
        };

        public static Color Pick(Color[] arr, System.Random rng) { return arr[rng.Next(arr.Length)]; }
        public static Color Shade(Color c, float f) { return new Color(c.r * f, c.g * f, c.b * f, c.a); }
    }

    /// <summary>Handles on a built vehicle model for lights.</summary>
    public class VehicleVisual
    {
        public GameObject root;
        public Renderer brake;
        public Renderer blinkLeft;
        public Renderer blinkRight;
    }
}
