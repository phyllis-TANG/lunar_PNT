#include "UnrealMvpSmokeExportComponent.h"

#include "Dom/JsonObject.h"
#include "HAL/PlatformFileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace
{
struct FMat3 { double V[3][3]{}; };

FMat3 NativeRotationColumns(const FQuat& Q)
{
    FMat3 R;
    const FVector Axes[3] = {Q.RotateVector(FVector::ForwardVector), Q.RotateVector(FVector::RightVector), Q.RotateVector(FVector::UpVector)};
    for (int C=0; C<3; ++C) { R.V[0][C]=Axes[C].X; R.V[1][C]=Axes[C].Y; R.V[2][C]=Axes[C].Z; }
    return R;
}

FMat3 ConvertRotation(const FMat3& R)
{
    // R_NB = C_NU R_UF C_FB. Both basis changes are improper; the result is proper.
    constexpr double CNU[3][3]={{0,1,0},{1,0,0},{0,0,1}};
    constexpr double CFB[3][3]={{1,0,0},{0,-1,0},{0,0,1}};
    FMat3 O;
    for(int I=0;I<3;++I) for(int J=0;J<3;++J) for(int K=0;K<3;++K) for(int L=0;L<3;++L)
        O.V[I][J] += CNU[I][K]*R.V[K][L]*CFB[L][J];
    return O;
}

void MatrixToWxyz(const FMat3& R, double& W,double& X,double& Y,double& Z)
{
    W=FMath::Sqrt(FMath::Max(0.,1.+R.V[0][0]+R.V[1][1]+R.V[2][2]))/2.;
    X=FMath::CopySign(FMath::Sqrt(FMath::Max(0.,1.+R.V[0][0]-R.V[1][1]-R.V[2][2]))/2.,R.V[2][1]-R.V[1][2]);
    Y=FMath::CopySign(FMath::Sqrt(FMath::Max(0.,1.-R.V[0][0]+R.V[1][1]-R.V[2][2]))/2.,R.V[0][2]-R.V[2][0]);
    Z=FMath::CopySign(FMath::Sqrt(FMath::Max(0.,1.-R.V[0][0]-R.V[1][1]+R.V[2][2]))/2.,R.V[1][0]-R.V[0][1]);
    const double N=FMath::Sqrt(W*W+X*X+Y*Y+Z*Z); W/=N; X/=N; Y/=N; Z/=N;
    if(W<0) {W=-W;X=-X;Y=-Y;Z=-Z;}
}
}

UUnrealMvpSmokeExportComponent::UUnrealMvpSmokeExportComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
}

void UUnrealMvpSmokeExportComponent::BeginPlay()
{
    Super::BeginPlay();
    StartTransform=GetOwner()->GetActorTransform();
    Root=FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir()/RunDirectory);
    IFileManager::Get().MakeDirectory(*(Root/TEXT("raw")),true);
    IFileManager::Get().MakeDirectory(*(Root/TEXT("truth")),true);
    RawCsv=Root/TEXT("raw/actor.csv"); TruthCsv=Root/TEXT("truth/trajectory.csv");
    FFileHelper::SaveStringToFile(TEXT("timestamp_ns,frame_index,action,x_u_cm,y_u_cm,z_u_cm,q_u_x,q_u_y,q_u_z,q_u_w\n"),*RawCsv);
    FFileHelper::SaveStringToFile(TEXT("timestamp_ns,frame_index,action,p_N_B_x_m,p_N_B_y_m,p_N_B_z_m,q_N_B_w,q_N_B_x,q_N_B_y,q_N_B_z\n"),*TruthCsv);
    const FString Config=FString::Printf(TEXT("{\n  \"schema_version\": \"unreal-mvp-interface-v1\",\n  \"engine_version\": \"%s\",\n  \"fixed_step_ns\": %lld,\n  \"native_frame\": \"UE Forward-Right-Up centimetres\",\n  \"converted_frame\": \"ENU/FLU metres\",\n  \"sensor_plugin\": \"not configured by exporter\"\n}\n"),*FEngineVersion::Current().ToString(),FixedStepNanoseconds);
    FFileHelper::SaveStringToFile(Config,*(Root/TEXT("engine_config.json")));
}

FString UUnrealMvpSmokeExportComponent::ActionAt(double S)
{
    if(S<0.5) return TEXT("stationary"); if(S<1.5) return TEXT("translate_native_x");
    if(S<2.0) return TEXT("plus_90_yaw_native_z"); if(S<2.5) return TEXT("plus_90_pitch_native_y");
    if(S<3.0) return TEXT("plus_90_roll_native_x"); return TEXT("complete");
}

void UUnrealMvpSmokeExportComponent::DriveMotion(double S)
{
    FVector P=StartTransform.GetLocation(); FQuat Q=StartTransform.GetRotation();
    if(S>=0.5) P += FVector(FMath::Min(S-0.5,1.),0,0)*100.;
    if(S>=1.5) Q=FQuat(FVector::UpVector,FMath::Min((S-1.5)/0.5,1.)*PI/2.)*Q;
    if(S>=2.0) Q=FQuat(FVector::RightVector,FMath::Min((S-2.0)/0.5,1.)*PI/2.)*Q;
    if(S>=2.5) Q=FQuat(FVector::ForwardVector,FMath::Min((S-2.5)/0.5,1.)*PI/2.)*Q;
    GetOwner()->SetActorLocationAndRotation(P,Q,false,nullptr,ETeleportType::TeleportPhysics);
}

void UUnrealMvpSmokeExportComponent::ExportFrame(int64 T,const FString& Action)
{
    const FVector P=GetOwner()->GetActorLocation(); const FQuat Q=GetOwner()->GetActorQuat();
    const FVector PN(P.Y/100.,P.X/100.,P.Z/100.); const FMat3 R=ConvertRotation(NativeRotationColumns(Q));
    double W,X,Y,Z; MatrixToWxyz(R,W,X,Y,Z);
    FFileHelper::SaveStringToFile(FString::Printf(TEXT("%lld,%llu,%s,%.9g,%.9g,%.9g,%.17g,%.17g,%.17g,%.17g\n"),T,FrameIndex,*Action,P.X,P.Y,P.Z,Q.X,Q.Y,Q.Z,Q.W),*RawCsv,FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,&IFileManager::Get(),FILEWRITE_Append);
    FFileHelper::SaveStringToFile(FString::Printf(TEXT("%lld,%llu,%s,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g\n"),T,FrameIndex,*Action,PN.X,PN.Y,PN.Z,W,X,Y,Z),*TruthCsv,FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,&IFileManager::Get(),FILEWRITE_Append);
}

void UUnrealMvpSmokeExportComponent::TickComponent(float Dt,ELevelTick Tick,FActorComponentTickFunction* Fn)
{
    Super::TickComponent(Dt,Tick,Fn); if(bFinished) return;
    const int64 T=static_cast<int64>(FrameIndex)*FixedStepNanoseconds; const double S=T/1e9;
    if(bDriveKnownMotion) DriveMotion(S); ExportFrame(T,ActionAt(S)); ++FrameIndex;
    if(S>=3.) {bFinished=true; SetComponentTickEnabled(false);}
}

void UUnrealMvpSmokeExportComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    Super::EndPlay(Reason);
}
