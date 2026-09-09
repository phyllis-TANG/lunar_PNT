using UnrealBuildTool;

public class UnrealMvpSmoke : ModuleRules
{
    public UnrealMvpSmoke(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine", "Projects" });
    }
}
