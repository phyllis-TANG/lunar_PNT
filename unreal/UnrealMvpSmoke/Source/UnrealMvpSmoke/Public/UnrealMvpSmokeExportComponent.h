#pragma once

#include "Components/ActorComponent.h"
#include "UnrealMvpSmokeExportComponent.generated.h"

/**
 * Minimal engine adapter for the documented smoke-test motion.
 *
 * It deliberately exports both the native transform and the independently
 * converted ENU/FLU transform. It does not reinterpret third-party sensor data.
 */
UCLASS(ClassGroup=(LunarPNT), meta=(BlueprintSpawnableComponent))
class UNREALMVPSMOKE_API UUnrealMvpSmokeExportComponent final : public UActorComponent
{
    GENERATED_BODY()
public:
    UUnrealMvpSmokeExportComponent();

    UPROPERTY(EditAnywhere, Category="Lunar PNT") FString RunDirectory = TEXT("LunarPNT/smoke_run");
    UPROPERTY(EditAnywhere, Category="Lunar PNT") int64 FixedStepNanoseconds = 10000000;
    UPROPERTY(EditAnywhere, Category="Lunar PNT") bool bDriveKnownMotion = true;

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

private:
    FString Root;
    FString RawCsv;
    FString TruthCsv;
    FTransform StartTransform;
    uint64 FrameIndex = 0;
    bool bFinished = false;

    void DriveMotion(double Seconds);
    void ExportFrame(int64 TimestampNs, const FString& Action);
    static FString ActionAt(double Seconds);
};
