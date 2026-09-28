using UnityEngine;
#if OJOL_INPUT_SYSTEM && ENABLE_INPUT_SYSTEM && !ENABLE_LEGACY_INPUT_MANAGER
using UnityEngine.InputSystem;
#endif

namespace OjolRush
{
    public enum ControlMode { Drag, Joystick }

    /// <summary>
    /// One-thumb steering. Drag mode: touch anywhere, the bike heads where your thumb pulls
    /// (floating origin). Joystick mode: a fixed virtual stick at the bottom of the screen.
    /// Thumb down but not moving = "hold" (ease off to thread a gap). Keyboard/mouse for desktop.
    /// The camera never rotates, so screen directions map straight onto the map.
    /// </summary>
    public class PlayerInput
    {
        public ControlMode mode = ControlMode.Drag;

        public bool Active { get; private set; }
        public bool Hold { get; private set; }
        /// <summary>Desired travel direction on the map (x, z), or zero.</summary>
        public Vector2 Direction { get; private set; }
        /// <summary>Screen-space stick base / knob (origin bottom-left) for drawing.</summary>
        public Vector2 Origin { get; private set; }
        public Vector2 Knob { get; private set; }
        public bool TouchActive { get; private set; }
        public bool PausePressed { get; private set; }

        bool wasDown;
        bool ignoreThisTouch;
        public Rect blockedScreenRect; // pause button, in screen coords (origin bottom-left)

        public float Scale { get { return Mathf.Max(Screen.width, Screen.height) / 1920f; } }
        public float Radius { get { return 90f * Scale; } }
        public float DeadZone { get { return 16f * Scale; } }
        public Vector2 JoystickCenter { get { return new Vector2(Screen.width * 0.5f, Screen.height * 0.17f); } }

        public void Update()
        {
            bool down;
            Vector2 pos;
            Vector2 keys;
            bool brakeKey;
            ReadDevices(out down, out pos, out keys, out brakeKey);

            bool began = down && !wasDown;
            wasDown = down;
            if (began) ignoreThisTouch = blockedScreenRect.Contains(pos);
            if (!down) ignoreThisTouch = false;

            Active = false;
            Hold = false;
            Direction = Vector2.zero;
            TouchActive = false;

            if (down && !ignoreThisTouch)
            {
                TouchActive = true;
                Active = true;
                if (mode == ControlMode.Joystick)
                {
                    Origin = JoystickCenter;
                }
                else if (began)
                {
                    Origin = pos;
                }
                Vector2 delta = pos - Origin;
                if (delta.magnitude > Radius)
                {
                    if (mode == ControlMode.Drag) Origin = pos - delta.normalized * Radius;
                    delta = delta.normalized * Radius;
                }
                Knob = Origin + delta;
                if (delta.magnitude < DeadZone) Hold = true;
                else Direction = delta.normalized;
            }

            if (keys.sqrMagnitude > 0.01f)
            {
                Active = true;
                Direction = keys.normalized;
                Hold = false;
            }
            if (brakeKey)
            {
                Active = true;
                Hold = true;
            }
        }

        void ReadDevices(out bool down, out Vector2 pos, out Vector2 keys, out bool brakeKey)
        {
            down = false;
            pos = Vector2.zero;
            keys = Vector2.zero;
            brakeKey = false;
            PausePressed = false;
#if OJOL_INPUT_SYSTEM && ENABLE_INPUT_SYSTEM && !ENABLE_LEGACY_INPUT_MANAGER
            Touchscreen ts = Touchscreen.current;
            if (ts != null && ts.primaryTouch.press.isPressed)
            {
                down = true;
                pos = ts.primaryTouch.position.ReadValue();
            }
            else if (Mouse.current != null && Mouse.current.leftButton.isPressed)
            {
                down = true;
                pos = Mouse.current.position.ReadValue();
            }
            Keyboard kb = Keyboard.current;
            if (kb != null)
            {
                if (kb.aKey.isPressed || kb.leftArrowKey.isPressed) keys.x -= 1f;
                if (kb.dKey.isPressed || kb.rightArrowKey.isPressed) keys.x += 1f;
                if (kb.wKey.isPressed || kb.upArrowKey.isPressed) keys.y += 1f;
                if (kb.sKey.isPressed || kb.downArrowKey.isPressed) keys.y -= 1f;
                brakeKey = kb.spaceKey.isPressed;
                PausePressed = kb.escapeKey.wasPressedThisFrame || kb.pKey.wasPressedThisFrame;
            }
#else
            if (Input.touchCount > 0)
            {
                Touch t = Input.GetTouch(0);
                down = t.phase != TouchPhase.Ended && t.phase != TouchPhase.Canceled;
                pos = t.position;
            }
            else if (Input.GetMouseButton(0))
            {
                down = true;
                pos = Input.mousePosition;
            }
            if (Input.GetKey(KeyCode.A) || Input.GetKey(KeyCode.LeftArrow)) keys.x -= 1f;
            if (Input.GetKey(KeyCode.D) || Input.GetKey(KeyCode.RightArrow)) keys.x += 1f;
            if (Input.GetKey(KeyCode.W) || Input.GetKey(KeyCode.UpArrow)) keys.y += 1f;
            if (Input.GetKey(KeyCode.S) || Input.GetKey(KeyCode.DownArrow)) keys.y -= 1f;
            brakeKey = Input.GetKey(KeyCode.Space);
            PausePressed = Input.GetKeyDown(KeyCode.Escape) || Input.GetKeyDown(KeyCode.P);
#endif
        }

        public void ResetState()
        {
            wasDown = true; // a finger still down from a menu tap must be lifted first
            ignoreThisTouch = true;
        }
    }
}
