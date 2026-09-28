using UnityEngine;

namespace OjolRush
{
    /// <summary>
    /// Starts Ojol Rush automatically when any scene loads, so the project needs no scene setup,
    /// prefabs or assets: open the project, press Play. To embed the game in your own scene
    /// instead, add a GameManager component to an empty GameObject and it will be used.
    /// </summary>
    public static class Bootstrap
    {
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Boot()
        {
            if (Object.FindObjectOfType<GameManager>() != null) return;
            GameObject go = new GameObject("OjolRush");
            go.AddComponent<GameManager>();
            Object.DontDestroyOnLoad(go);
        }
    }
}
