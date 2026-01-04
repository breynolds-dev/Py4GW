# ──────────────────────────────────────────────────────────────────────────────
# Destroyer Core Farmer Bot
#
# Build: 
#   - R/A - Whirling Defense Tank
#   - Code: OgcTcXs9ZiHRn5AiAiVE354Q4AA
#   - Insignia: 5x Blessed
#   - Runes:
#     - Superior Rune of Vigor
#     - Superior Rune of Expertise
#     - 3x Rune of Attunement
#   - Weapons: 
#     - +5 Energy, 20% Enchantment (ie: Totem Axe)
#     - HP + 30, Armor +10 vs Pierce
#
# Description:
#   This bot automates the process of farming Destroyer Cores in "Glint's
#   Challenge" quest in Guild Wars.
# ──────────────────────────────────────────────────────────────────────────────
import PyImGui
from typing import Literal, Tuple

from Py4GWCoreLib.Builds import KeiranThackerayEOTN
from Py4GWCoreLib import (GLOBAL_CACHE, Routines, Range, Py4GW, ConsoleLog, ModelID, Botting,
                          Map, ImGui, ActionQueueManager)


class BotSettings:
    # Map/Outpost IDs
    EYE_OF_THE_NORTH_OUTPOST_ID = 642
    CENTRAL_TRANSFER_CHAMBER_ID = 652
    GLINTS_CHALLENGE_MAP_ID = 37

    # Gold threshold for deposit
    GOLD_THRESHOLD_DEPOSIT: int = 90000

    # Properties to enable/disable via setting tab
    WAR_SUPPLIES_ENABLED: bool = False

    # Runs counters
    TOTAL_RUNS: int = 0
    SUCCESSFUL_RUNS: int = 0
    FAILED_RUNS: int = 0
    
    # Material purchases
    ECTOS_BOUGHT: int = 0

    # Misc
    DEBUG: bool = False


bot = Botting("Auspicious Beginnings",
              custom_build=KeiranThackerayEOTN())
     
def create_bot_routine(bot: Botting) -> None:
    InitializeBot(bot)
    GoToEOTN(bot)
    QuestLoopEntry(bot)  # Start the quest loop
    
def QuestLoopEntry(bot: Botting) -> None:
    """Main quest loop entry point: checks gold, deposits if needed, then runs quest"""
    CheckAndDepositGold(bot)   # Check gold and deposit if threshold exceeded
    ExitToHOM(bot)             # Exit to HOM (skiped if already in HOM)
    bot.Map.Travel(target_map_id=BotSettings.CENTRAL_TRANSFER_CHAMBER_ID)
    EnterQuest(bot)            # Enter the quest
    RunQuest(bot)              # Run the quest (loops back to CheckAndDepositGold)

def _on_death(bot: "Botting"):
    _increment_runs_counters(bot, "fail")
    bot.Properties.ApplyNow("pause_on_danger", "active", False)
    bot.Properties.ApplyNow("halt_on_death","active", True)
    bot.Properties.ApplyNow("movement_timeout","value", 15000)
    bot.Properties.ApplyNow("auto_combat","active", False)
    yield from Routines.Yield.wait(8000)
    fsm = bot.config.FSM
    fsm.jump_to_state_by_name("[H]Prepare for Quest_5") 
    fsm.resume()                           
    yield  
    
def on_death(bot: "Botting"):
    print ("Player is dead. Run Failed, Restarting...")
    ActionQueueManager().ResetAllQueues()
    fsm = bot.config.FSM
    fsm.pause()
    fsm.AddManagedCoroutine("OnDeath", _on_death(bot))

def _EnableCombat(bot: Botting) -> None:
        bot.OverrideBuild(KeiranThackerayEOTN())
        bot.Templates.Aggressive(enable_imp=False)
 
def _DisableCombat(bot: Botting) -> None:
    bot.Templates.Pacifist()

def InitializeBot(bot: Botting) -> None:
    condition = lambda: on_death(bot)
    bot.Events.OnDeathCallback(condition)

def GoToEOTN(bot: Botting) -> None:
    bot.States.AddHeader("Go to EOTN")

    def _go_to_eotn(bot: Botting):
        current_map = Map.GetMapID()
        should_skip_travel = current_map in [BotSettings.EYE_OF_THE_NORTH_OUTPOST_ID, BotSettings.CENTRAL_TRANSFER_CHAMBER_ID]
        if should_skip_travel:
            if BotSettings.DEBUG:   
                print(f"[DEBUG] Already in EOTN or CTC, skipping travel")
            return

        Map.Travel(BotSettings.EYE_OF_THE_NORTH_OUTPOST_ID)
        yield from Routines.Yield.wait(1000)
        yield from Routines.Yield.Map.WaitforMapLoad(BotSettings.EYE_OF_THE_NORTH_OUTPOST_ID) 

    bot.States.AddCustomState(lambda: _go_to_eotn(bot), "GoToEOTN")

def CheckAndDepositGold(bot: Botting) -> None:
    """Check gold on character, deposit if needed"""
    bot.States.AddHeader("Check and Deposit Gold")

    def _check_and_deposit_gold(bot: Botting):
        current_map = Map.GetMapID()
        gold_on_char = GLOBAL_CACHE.Inventory.GetGoldOnCharacter()
        gold_in_storage = GLOBAL_CACHE.Inventory.GetGoldInStorage()

        if BotSettings.DEBUG:   
            print(f"[DEBUG] CheckAndDepositGold: current_map={current_map}, gold={gold_on_char}, storage={gold_in_storage}")
        
        # Travel to EOTN if character has 90k+ gold
        if gold_on_char > BotSettings.GOLD_THRESHOLD_DEPOSIT:
            # Ensure we're in EOTN outpost
            if current_map != BotSettings.EYE_OF_THE_NORTH_OUTPOST_ID:
                if BotSettings.DEBUG:   
                    print(f"[DEBUG] Traveling to EOTN from map {current_map}")

                Map.Travel(BotSettings.EYE_OF_THE_NORTH_OUTPOST_ID)
                yield from Routines.Yield.wait(1000)
                yield from Routines.Yield.Map.WaitforMapLoad(BotSettings.EYE_OF_THE_NORTH_OUTPOST_ID)
                current_map = BotSettings.EYE_OF_THE_NORTH_OUTPOST_ID

            # Deposit gold only if storage hasn't reached 800k
            if gold_in_storage < 800000:
                if BotSettings.DEBUG:   
                    print(f"Depositing {gold_on_char} gold in bank")
                GLOBAL_CACHE.Inventory.DepositGold(gold_on_char)
                yield from Routines.Yield.wait(1000)
            else:
                if BotSettings.DEBUG:   
                    print(f"Storage ({gold_in_storage}) has reached gold threshold, keeping gold on character for ecto purchases")
        else:
            if BotSettings.DEBUG:   
                print(f"Gold ({gold_on_char}) below threshold ({BotSettings.GOLD_THRESHOLD_DEPOSIT}), skipping travel and deposit")
        
        # After deposit check, try to buy ectos if in EOTN outpost
        current_map = Map.GetMapID()
        if current_map == BotSettings.EYE_OF_THE_NORTH_OUTPOST_ID:
            yield from BuyMaterials(bot)

        if BotSettings.DEBUG:   
            print(f"[DEBUG] After gold check: current_map={current_map}, HOM={BotSettings.CENTRAL_TRANSFER_CHAMBER_ID}")

    bot.States.AddCustomState(lambda: _check_and_deposit_gold(bot), "CheckAndDepositGold")

def ExitToHOM(bot: Botting) -> None:
    bot.States.AddHeader("Exit to HOM")

    # Ensure we're in HOM for quest preparation
    def _exit_to_hom(bot: Botting):
        current_map = Map.GetMapID()
        should_exit_to_hom = current_map != BotSettings.CENTRAL_TRANSFER_CHAMBER_ID
        should_travel_to_eye_of_the_north = current_map != BotSettings.EYE_OF_THE_NORTH_OUTPOST_ID

        if should_exit_to_hom:
            if BotSettings.DEBUG:   
                print(f"[DEBUG] Not in HOM, need to go there. Currently in map {current_map}")

            if should_travel_to_eye_of_the_north:
                if BotSettings.DEBUG:   
                    print(f"[DEBUG] Not in EOTN, traveling there first")
                Map.Travel(BotSettings.EYE_OF_THE_NORTH_OUTPOST_ID)
                yield from Routines.Yield.wait(1000)
                yield from Routines.Yield.Map.WaitforMapLoad(BotSettings.EYE_OF_THE_NORTH_OUTPOST_ID)

            if BotSettings.DEBUG:   
                print(f"[DEBUG] Moving to portal coordinates and exiting to HOM")

            # Use coroutine version to move to portal and exit
            yield from bot.Move._coro_xy_and_exit_map(-4873.00, 5284.00, target_map_id=BotSettings.CENTRAL_TRANSFER_CHAMBER_ID)
        else:
            if BotSettings.DEBUG:   
                print(f"[DEBUG] Already in HOM, skipping travel")
        yield

    bot.States.AddCustomState(lambda: _exit_to_hom(bot), "ExitToHOM")

def TravelToCentralTransferChamber(bot: Botting) -> None:
    bot.States.AddHeader("Exit to HOM")

    # Ensure we're in CTC for quest preparation
    def _exit_to_central_transfer_chamber(bot: Botting):
        current_map = Map.GetMapID()
        should_goto_to_central_transfer_chamber = current_map != BotSettings.CENTRAL_TRANSFER_CHAMBER_ID
        should_travel_to_eye_of_the_north = current_map != BotSettings.EYE_OF_THE_NORTH_OUTPOST_ID

        if should_goto_to_central_transfer_chamber:
            if BotSettings.DEBUG:   
                print(f"[DEBUG] Not in HOM, need to go there. Currently in map {current_map}")

            if should_travel_to_eye_of_the_north:
                if BotSettings.DEBUG:   
                    print(f"[DEBUG] Not in EOTN, traveling there first")
                Map.Travel(BotSettings.EYE_OF_THE_NORTH_OUTPOST_ID)
                yield from Routines.Yield.wait(1000)
                yield from Routines.Yield.Map.WaitforMapLoad(BotSettings.EYE_OF_THE_NORTH_OUTPOST_ID)

            if BotSettings.DEBUG:   
                print(f"[DEBUG] Moving to portal coordinates and exiting to HOM")

            # Use coroutine version to move to portal and exit
            yield from bot.Move._coro_xy_and_exit_map(-4873.00, 5284.00, target_map_id=BotSettings.CENTRAL_TRANSFER_CHAMBER_ID)
        else:
            if BotSettings.DEBUG:   
                print(f"[DEBUG] Already in HOM, skipping travel")
        yield

    bot.States.AddCustomState(lambda: _exit_to_central_transfer_chamber(bot), "ExitToHOM")

def deposit_gold(bot: Botting):
    gold_on_char = GLOBAL_CACHE.Inventory.GetGoldOnCharacter()

    # Deposit all gold if character has 90k or more
    if gold_on_char >= 90000:
        bot.Map.Travel(target_map_id=642)
        bot.Wait.ForMapLoad(target_map_id=642)
        yield from Routines.Yield.wait(500)
        GLOBAL_CACHE.Inventory.DepositGold(gold_on_char)
        yield from Routines.Yield.wait(500)
        bot.Move.XYAndExitMap(-4873.00, 5284.00, target_map_id=646)
        bot.Wait.ForMapLoad(target_map_id=646)
        yield

def BuyMaterials(bot: Botting):
    """Buy Glob of Ectoplasm if gold conditions are met."""
    # Check gold conditions for buying Glob of Ectoplasm
    gold_in_inventory = GLOBAL_CACHE.Inventory.GetGoldOnCharacter()
    gold_in_storage = GLOBAL_CACHE.Inventory.GetGoldInStorage()
    
    if gold_in_inventory >= 90000 and gold_in_storage >= 800000:
        # Move to and speak with rare material trader
        yield from bot.Move._coro_xy_and_dialog(-2079.00, 1046.00, dialog_id=0x00000001)
        
        # Buy Glob of Ectoplasm until inventory gold drops below 2k
        for _ in range(100):  # Max 100 Globs of Ectoplasm
            current_gold = GLOBAL_CACHE.Inventory.GetGoldOnCharacter()
            if current_gold < 2000:  # Stop buying if gold is below 2k
                if BotSettings.DEBUG:
                    print(f"[DEBUG] Stopping ecto purchases - gold ({current_gold}) below 2k")
                break
            yield from Routines.Yield.Merchant.BuyMaterial(ModelID.Glob_Of_Ectoplasm.value)
            BotSettings.ECTOS_BOUGHT += 1  # Increment ecto counter
            yield from Routines.Yield.wait(100)  # Small delay between purchases

def EnterQuest(bot: Botting) -> None:
    bot.States.AddHeader("Enter Quest")
    bot.Move.XYAndDialog(2428.16, 3534.33, 0x44) #enter quest with pool
    bot.Wait.ForMapLoad(target_map_id=BotSettings.GLINTS_CHALLENGE_MAP_ID)
    
def RunQuest(bot: Botting) -> None:    
    bot.States.AddHeader("Run Quest")
    _EnableCombat(bot)
    bot.Move.XY(-3327.01, 741.03, step_name="Moving To Pull Spot")
    bot.Wait.ForTime(2000)

    # Total Wait Time 225000 ms

    # Start Tank Routine with Shadow Form

    print(f"Start Balling Enemies")
    bot.Move.XY(-2676.40, 1735.90)
    bot.Wait.ForTime(2000)

    bot.Move.XY(-2232.54, 3384.54)
    bot.Wait.ForTime(2000)

    bot.Move.XY(-2253.28, 830.86)
    bot.Wait.ForTime(3000)

    print(f"Getting Energy Back")
    # Use Skill 'Storm Chaster'

    print(f"Jumping To Pack")
    # Use Skill 'Death's Charge'
    # Use Skill 'Whirling Defense'

    # Pick Up Destroyer Cores, Golds, etc
    _DisableCombat(bot)
    # Resign

    #bot.Wait.UntilOutOfCombat()
    bot.Properties.Disable("pause_on_danger")
    path = [(8859.57, -7388.68), (9012.46, -9027.44)]
    bot.Move.FollowAutoPath(path, step_name="To corner")
    bot.Properties.Enable("pause_on_danger")
    #bot.Wait.UntilOutOfCombat()

    bot.Wait.ForMapLoad(target_map_id=BotSettings.CENTRAL_TRANSFER_CHAMBER_ID)
    
    # Increment success counter at runtime, not setup time
    def _increment_success():
        _increment_runs_counters(bot, "success")
        yield
    
    bot.States.AddCustomState(lambda: _increment_success(), "IncrementSuccessCounter")
    
    # Loop back to check gold and run quest again
    bot.States.JumpToStepName("[H]Check and Deposit Gold_3")

def _increment_runs_counters(bot: Botting, type: Literal["success", "fail"]):
    """Increment run counters based on run result"""
    BotSettings.TOTAL_RUNS += 1
    if type == "success":
        BotSettings.SUCCESSFUL_RUNS += 1
    elif type == "fail":
        BotSettings.FAILED_RUNS += 1

def _success_rate():
    if BotSettings.TOTAL_RUNS == 0:
        return "0.00%"
    return f"{BotSettings.SUCCESSFUL_RUNS / BotSettings.TOTAL_RUNS * 100:.2f}%"

def _fail_rate():
    if BotSettings.TOTAL_RUNS == 0:
        return "0.00%"
    return f"{BotSettings.FAILED_RUNS / BotSettings.TOTAL_RUNS * 100:.2f}%"

def destroyer_cores_obtained():
    return 5 * BotSettings.SUCCESSFUL_RUNS # 5 destroyer cores per run

def gold_obtained():
    return 1000 * BotSettings.SUCCESSFUL_RUNS # 1000 gold per run

def _draw_settings(bot: Botting):
    PyImGui.text("Bot Settings")

    # Gold threshold controls
    gold_threshold = BotSettings.GOLD_THRESHOLD_DEPOSIT
    gold_threshold = PyImGui.input_int("Gold deposit threshold", gold_threshold)

    # Debug controls
    debug = BotSettings.DEBUG
    debug = PyImGui.checkbox("Debug", debug)

    BotSettings.GOLD_THRESHOLD_DEPOSIT = gold_threshold
    BotSettings.DEBUG = debug

bot.SetMainRoutine(create_bot_routine)
bot.UI.override_draw_config(lambda: _draw_settings(bot))

def main():
    try:
        projects_path = Py4GW.Console.get_projects_path()
        full_path = projects_path + "\\Bots\\War Supply\\"
        main_child_dimensions: Tuple[int, int] = (350, 275)
        
        bot.Update()
        bot.UI.draw_window(icon_path=full_path + "Keiran_art.png")

        if PyImGui.begin(bot.config.bot_name, PyImGui.WindowFlags.AlwaysAutoResize):
            if PyImGui.begin_tab_bar(bot.config.bot_name + "_tabs"):
                if PyImGui.begin_tab_item("Main"):
                    PyImGui.dummy(*main_child_dimensions)

                    PyImGui.separator()

                    ImGui.push_font("Regular", 18)
                    PyImGui.text("Statistics")
                    ImGui.pop_font()
                    
                    if PyImGui.collapsing_header("Runs"):
                        # Total Runs
                        PyImGui.LabelTextV("Total", "%s", [str(BotSettings.TOTAL_RUNS)])    	

                        # Successful Runs
                        PyImGui.push_style_color(PyImGui.ImGuiCol.Text, (0.0, 1.0, 0.0, 1.0))
                        PyImGui.LabelTextV("Successful", "%s", [f"{BotSettings.SUCCESSFUL_RUNS} ({_success_rate()})"])
                        PyImGui.pop_style_color(1)

                        # Failed Runs
                        PyImGui.push_style_color(PyImGui.ImGuiCol.Text, (1.0, 0.0, 0.0, 1.0))
                        PyImGui.LabelTextV("Failed", "%s", [f"{BotSettings.FAILED_RUNS} ({_fail_rate()})"])
                        PyImGui.pop_style_color(1)

                    if PyImGui.collapsing_header("Items/Gold obtained"):
                        PyImGui.LabelTextV("Gold", "%s", [str(gold_obtained())])    	
                        PyImGui.LabelTextV("Destroyer Cores", "%s", [str(destroyer_cores_obtained())])
                        PyImGui.LabelTextV("Glob of Ectoplasm", "%s", [str(BotSettings.ECTOS_BOUGHT)])    	
                    
                PyImGui.end_tab_item()
            PyImGui.end_tab_bar()
        PyImGui.end()

    except Exception as e:
        Py4GW.Console.Log(bot.config.bot_name, f"Error: {str(e)}", Py4GW.Console.MessageType.Error)
        raise

if __name__ == "__main__":
    main()
