using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

namespace OjolRush.EditorTools
{
    /// <summary>
    /// One-time project setup so device builds look like the Editor:
    /// portrait orientation, fog/instancing shader variants kept, and base material assets in
    /// Resources (runtime-created materials alone would let the build strip emission/instancing variants).
    /// Runs once automatically; re-run any time via the "Ojol Rush" menu.
    /// </summary>
    [InitializeOnLoad]
    static class OjolRushProjectSetup
    {
        const string DoneKey = "OjolRush_ProjectSetup_v1_";
        const string ResourcesDir = "Assets/OjolRush/Resources";

        static OjolRushProjectSetup()
        {
            EditorApplication.delayCall += () =>
            {
                string key = DoneKey + Application.dataPath;
                if (EditorPrefs.GetBool(key, false)) return;
                EditorPrefs.SetBool(key, true);
                Apply();
            };
        }

        [MenuItem("Ojol Rush/Apply Project Settings")]
        static void Apply()
        {
            PlayerSettings.defaultInterfaceOrientation = UIOrientation.Portrait;
            if (string.IsNullOrEmpty(PlayerSettings.productName) || PlayerSettings.productName == "rumah")
                PlayerSettings.productName = "Ojol Rush";

            // Keep instancing + linear fog variants (materials are created at runtime, not referenced by scenes).
            Object[] gs = AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/GraphicsSettings.asset");
            if (gs != null && gs.Length > 0)
            {
                SerializedObject so = new SerializedObject(gs[0]);
                SetInt(so, "m_InstancingStripping", 2); // Keep All
                SetInt(so, "m_FogStripping", 1);        // Custom
                SetBool(so, "m_FogKeepLinear", true);
                so.ApplyModifiedPropertiesWithoutUndo();
            }

            CreateBaseMaterials();
            AssetDatabase.SaveAssets();
            Debug.Log("[Ojol Rush] Project settings applied (portrait, shader variants, base materials).");
        }

        static void SetInt(SerializedObject so, string name, int v)
        {
            SerializedProperty p = so.FindProperty(name);
            if (p != null) p.intValue = v;
        }

        static void SetBool(SerializedObject so, string name, bool v)
        {
            SerializedProperty p = so.FindProperty(name);
            if (p != null) p.boolValue = v;
        }

        static void CreateBaseMaterials()
        {
            Material template = null;
            RenderPipelineAsset rp = GraphicsSettings.renderPipelineAsset;
            if (rp != null) template = rp.defaultMaterial;
            if (template == null) template = AssetDatabase.GetBuiltinExtraResource<Material>("Default-Material.mat");
            if (template == null) return;
            if (!AssetDatabase.IsValidFolder(ResourcesDir)) AssetDatabase.CreateFolder("Assets/OjolRush", "Resources");

            Material plain = new Material(template);
            plain.enableInstancing = true;
            plain.DisableKeyword("_EMISSION");
            Save(plain, ResourcesDir + "/OjolRushBase.mat");

            Material glow = new Material(template);
            glow.enableInstancing = true;
            glow.EnableKeyword("_EMISSION");
            if (glow.HasProperty("_EmissionColor")) glow.SetColor("_EmissionColor", Color.white);
            glow.globalIlluminationFlags = MaterialGlobalIlluminationFlags.None;
            Save(glow, ResourcesDir + "/OjolRushBaseEmissive.mat");
        }

        static void Save(Material m, string path)
        {
            if (AssetDatabase.LoadAssetAtPath<Material>(path) != null) AssetDatabase.DeleteAsset(path);
            AssetDatabase.CreateAsset(m, path);
        }
    }
}
