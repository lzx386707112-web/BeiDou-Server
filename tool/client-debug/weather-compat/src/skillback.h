#pragma once

// Independent skill backdrop plane (5th/6th job FX later).
//
// Split of responsibilities:
//   - Payload stays MCV (BeiDouVideo.dll). Large sequences are not stuffed into IMG.
//   - Placement is this plane: a 7x5 FIELD_EFFECT-style marker at z above the
//     injected weather band and behind HILL_Z tiles/buildings. DawnWarriorSkillCompat
//     still swallows the marker and calls BDV_Render at that draw, so the video
//     inherits this z instead of the stock Map/Effect field-effect slot.
//
// Packet 0x373F is decoded on the receive thread; layers and BDV_PlayFile run
// only from CallUpdate.

class CInPacket;

void SkillBack_HandlePacket(CInPacket* pPacket);
void SkillBack_Frame();
void SkillBack_OnLeaveField();
