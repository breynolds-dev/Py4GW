import Py4GW
import math
from typing import Tuple
from Py4GWCoreLib import Profession
from Py4GWCoreLib import GLOBAL_CACHE
from Py4GWCoreLib import Routines
from Py4GWCoreLib import ConsoleLog
from Py4GWCoreLib import BuildMgr
from Py4GWCoreLib import Map, Agent
from Py4GWCoreLib import Range
from Py4GWCoreLib import Utils
from Py4GWCoreLib import Overlay, DXOverlay
from Py4GWCoreLib import ThrottledTimer

from typing import List, Tuple
from Py4GWCoreLib.Builds.BuildHelpers import BuildDangerHelper

dx = DXOverlay()
ShowDXoverlay = False

def vector_angle(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Returns the cosine similarity (dot product / magnitudes). 1 = same direction, -1 = opposite."""
    dot = a[0]*b[0] + a[1]*b[1]
    mag_a = math.hypot(*a)
    mag_b = math.hypot(*b)
    if mag_a == 0 or mag_b == 0:
        return 1  # safest fallback
    dot = a[0]*b[0] + a[1]*b[1]
    return dot / (mag_a * mag_b)

#region SFRangerDestroyerCore
class ShadowFormRangerDestroyerCore(BuildMgr):
    def __init__(self, build_danger_helper: BuildDangerHelper = BuildDangerHelper()):
        super().__init__(
            name="SF Whirling Defense Ranger",
            required_primary=Profession.Ranger,
            required_secondary=Profession.Assassin,
            template_code="OwZSg4PTSfHQ6MTQ3lIQrg4O",
            skills=[
                GLOBAL_CACHE.Skill.GetID("Deadly_Paradox"),
                GLOBAL_CACHE.Skill.GetID("Shadow_Form"),
                GLOBAL_CACHE.Skill.GetID("Shroud_of_Distress"),
                GLOBAL_CACHE.Skill.GetID("Way_of_Perfection"),
                GLOBAL_CACHE.Skill.GetID("Great_Dwarf_Armor"),
                GLOBAL_CACHE.Skill.GetID("Deaths_Charge"),
                GLOBAL_CACHE.Skill.GetID("Storm_Chaser"),
                GLOBAL_CACHE.Skill.GetID("Whirling_Defense"),
            ],
        )
        
        # Skill IDs
        self.deadly_paradox = GLOBAL_CACHE.Skill.GetID("Deadly_Paradox")
        self.shadow_form = GLOBAL_CACHE.Skill.GetID("Shadow_Form")
        self.shroud_of_distress = GLOBAL_CACHE.Skill.GetID("Shroud_of_Distress")
        self.way_of_perfection = GLOBAL_CACHE.Skill.GetID("Way_of_Perfection")
        self.great_dwarf_armor = GLOBAL_CACHE.Skill.GetID("Great_Dwarf_Armor")
        self.deaths_charge = GLOBAL_CACHE.Skill.GetID("Deaths_Charge")
        self.storm_chaser = GLOBAL_CACHE.Skill.GetID("Storm_Chaser")
        self.whirling_defense = GLOBAL_CACHE.Skill.GetID("Whirling_Defense")

        # Internal dash cooldown
        self.timer = ThrottledTimer(12000)
        self.timer.Start()
        
        # States
        self.is_looting = False
        self.routine_finished = False

        self.build_danger_helper = build_danger_helper

    def SetRoutineFinished(self, routine_finished: bool):
        self.routine_finished = routine_finished

    def SetLootingSignal(self, is_looting: bool):
        self.is_looting = is_looting


    def _CastSkillID(self, skill_id:int, extra_condition:bool=True, log:bool=True, aftercast_delay:int=1000):
        result = yield from Routines.Yield.Skills.CastSkillID(skill_id, extra_condition=extra_condition, log=log, aftercast_delay=aftercast_delay)
        return result
    

    def _CastSkillSlot(self, slot:int, extra_condition:bool=True, log:bool=True, aftercast_delay:int=1000):
        result = yield from Routines.Yield.Skills.CastSkillSlot(slot, extra_condition=extra_condition, log=log, aftercast_delay=aftercast_delay)
        return result
                

    # Shroud of Distress watcher
    def ShroudOfDistressWatcher(self):
        # Initial vars
        player_agent_id = GLOBAL_CACHE.Player.GetAgentID()
        has_sod = Routines.Checks.Effects.HasBuff(player_agent_id, self.shroud_of_distress)
        is_sod_ready = Routines.Checks.Skills.IsSkillIDReady(self.shroud_of_distress)
        is_sod_about_to_expire = has_sod and GLOBAL_CACHE.Effects.GetEffectTimeRemaining(player_agent_id, self.shroud_of_distress) <= 2000
        is_sf_about_to_expire = Routines.Checks.Effects.HasBuff(player_agent_id, self.shadow_form) and GLOBAL_CACHE.Effects.GetEffectTimeRemaining(player_agent_id, self.shadow_form) <= 4000

        if is_sf_about_to_expire:
            return  # Shadow Form has priority

        if (is_sod_ready and (is_sod_about_to_expire or not has_sod)):
            # ** Cast Shroud of Distress **
            yield from self._CastSkillID(self.shroud_of_distress, log =False, aftercast_delay=1350)
    
    def ShadowFormWatcher(self):
        # Initial vars
        player_agent_id = GLOBAL_CACHE.Player.GetAgentID()
        has_shadow_form = Routines.Checks.Effects.HasBuff(player_agent_id, self.shadow_form)
        is_sf_about_to_expire = has_shadow_form and GLOBAL_CACHE.Effects.GetEffectTimeRemaining(player_agent_id, self.shadow_form) <= 4000
        is_sf_ready = Routines.Checks.Skills.IsSkillIDReady(self.shadow_form)

        # Cast Shadow Form if not active or about to expire
        if (not has_shadow_form or is_sf_about_to_expire) and is_sf_ready:
            yield from self._CastSkillID(self.deadly_paradox, log=False, aftercast_delay=200)
            yield from self._CastSkillID(self.shadow_form, log=False, aftercast_delay=1250)

    def StanceWatcher(self):
        # Initial vars
        player_agent_id = GLOBAL_CACHE.Player.GetAgentID()
        is_sf_about_to_expire = Routines.Checks.Effects.HasBuff(player_agent_id, self.shadow_form) and GLOBAL_CACHE.Effects.GetEffectTimeRemaining(player_agent_id, self.shadow_form) <= 4000
        has_storm_chaser = Routines.Checks.Effects.HasBuff(player_agent_id, self.storm_chaser)
        has_stance = Routines.Checks.Effects.HasBuff(player_agent_id, self.whirling_defense)

        # Dont handle stance if shadow form is about to expire -- SF has priority
        if is_sf_about_to_expire:
            yield

        # With high enough dwarven skill, this will only run at the start of the run
        if not has_storm_chaser and not has_stance:
            yield from self._CastSkillID(self.storm_chaser, log=False, aftercast_delay=1250)
            yield from self._CastSkillID(self.whirling_defense, log=False, aftercast_delay=200)

        # Continuation vars
        remaining_stability_duration = GLOBAL_CACHE.Effects.GetEffectTimeRemaining(player_agent_id, self.storm_chaser)
        remaining_stance_duration = GLOBAL_CACHE.Effects.GetEffectTimeRemaining(player_agent_id, self.whirling_defense)

        # Refresh dwarven stability if it's about to expire
        if (not has_storm_chaser or remaining_stability_duration <= 2000) and Routines.Checks.Skills.IsSkillIDReady(self.storm_chaser): 
            yield from self._CastSkillID(self.storm_chaser, log=False, aftercast_delay=200)

        # Refresh stance if it's about to expire
        if (not has_stance or remaining_stance_duration <= 2000) and self.timer.IsExpired():
            self.timer.Reset()
            yield from self._CastSkillID(self.whirling_defense, log=False, aftercast_delay=200)

    def ProcessSkillCasting(self):
        current_map_id = Map.GetMapID()
        player_agent_id = GLOBAL_CACHE.Player.GetAgentID()

        while True:
            # Check basic conditions where skill handling should be skipped
            
            # Check if map has fully loaded
            if not Routines.Checks.Map.MapValid():
                yield from Routines.Yield.wait(1000)
                continue
            
            # Player is dead
            if Agent.IsDead(GLOBAL_CACHE.Player.GetAgentID()):
                yield from Routines.Yield.wait(1000)
                continue

            # Cannot cast skills right now, throttle 100ms
            if not Routines.Checks.Skills.CanCast():
                yield from Routines.Yield.wait(100)
                continue

            # Check if routine is finished
            if self.routine_finished:
                yield from Routines.Yield.wait(1000)
                continue

            if self.is_looting:
                yield from Routines.Yield.wait(1000)
                continue

            # === Skill Watchers ===

            # Shroud of Distress watcher
            yield from self.ShroudOfDistressWatcher()

            # Shadow Form watcher
            yield from self.ShadowFormWatcher()

            # Stance watcher
            yield from self.StanceWatcher()

            # IAU Watcher === Anti Cripple/KD ===
            # yield from self.IAUWatcher()

            # Shadow Sanctuary watcher
            # yield from self.DefensiveWatcher()

            # Blocked Escape watcher
            # yield from self.BlockedEscapeWatcher()

            # === IDLE WAIT ===
            yield from Routines.Yield.wait(150)
            
            # Log current map id and name
            ConsoleLog(self.build_name, f"Current Map ID: {current_map_id}, Name: {Map.GetMapName(current_map_id)}", Py4GW.Console.MessageType.Info, log=False)



    # Taken from aC's Build_Manager for Death's Charge targeting 
    def DeathsChargeToBestEnemy(self):
        def angle_between_player_and_enemy(facing_vec, enemy_vec):
            """
            Returns absolute angle (0..180°) between player's facing vector
            and the vector from player -> enemy.
            """
            fx, fy = facing_vec
            ex, ey = enemy_vec
            dot = fx * ex + fy * ey            
            det = fx * ey - fy * ex            
            angle_rad = math.atan2(det, dot)
            angle_deg = abs(math.degrees(angle_rad))

            return angle_deg
        

        SPELLCAST_RANGE = 1248.0
        px, py = GLOBAL_CACHE.Player.GetXY()
        pz = Overlay().FindZ(px, py)
        heading = Agent.GetRotationAngle(GLOBAL_CACHE.Player.GetAgentID())
        facing_vec = (math.cos(heading), math.sin(heading))

        enemy_array = Routines.Agents.GetFilteredEnemyArray(px, py, max_distance=SPELLCAST_RANGE)

        best_15deg = None
        best_15deg_dist = -1
        best_30deg = None
        best_30deg_dist = -1

        for enemy in enemy_array:
            if Agent.IsDead(enemy):
                continue

            ex, ey = Agent.GetXY(enemy)
            enemy_vec = (ex - px, ey - py)
            dist = math.hypot(enemy_vec[0], enemy_vec[1])
            angle = angle_between_player_and_enemy(facing_vec, enemy_vec)

            if angle <= 15.0:
                if dist > best_15deg_dist:
                    best_15deg_dist = dist
                    best_15deg = enemy
            elif angle <= 60.0:
                if dist > best_30deg_dist:
                    best_30deg_dist = dist
                    best_30deg = enemy

        best_target = best_15deg if best_15deg else best_30deg

        if not best_target:
            ConsoleLog(self.build_name, "Deaths Charge Handler ::: No valid target in 15° or 30° cone → skip", Py4GW.Console.MessageType.Debug)
            return

        ex, ey = Agent.GetXY(best_target)
        ez = Overlay().FindZ(ex, ey)
        target_dist = math.hypot(ex - px, ey - py)
        ConsoleLog(
            self.build_name,
            f"Chosen enemy at ({ex:.1f}, {ey:.1f}) | Cone: {'15°' if best_target == best_15deg else '30°'} | Distance={target_dist:.1f}",
            Py4GW.Console.MessageType.Debug
        )

        if ShowDXoverlay:
            overlay = Overlay()
            overlay.BeginDraw()
            overlay.DrawLine3D(px, py, pz, ex, ey, ez, 0xFFFFFF00, 3.0)  # thick yellow/white line
            overlay.EndDraw()

        yield from Routines.Yield.Agents.ChangeTarget(best_target)
        yield from self._CastSkillID(self.deaths_charge, aftercast_delay=1000)