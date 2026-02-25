"""
Options for Mario Kart Wii Archipelago World
"""
from dataclasses import dataclass
from Options import Choice, Range, OptionSet, PerGameCommonOptions, Toggle


class EnabledCCs(OptionSet):
    """Which engine classes (CCs) generate location checks. (options: 50cc, 100cc, 150cc, Mirror)"""
    display_name = "Enabled CCs"
    valid_keys = {"50cc", "100cc", "150cc", "Mirror"}
    default = {"50cc", "100cc", "150cc"}


class EnabledCupCheckTiers(OptionSet):
    """Which difficulty tiers generate cup completion checks. (options: 3rd_place, 2nd_place, 1st_place, 1_star, 2_star, 3_star)"""
    display_name = "Enabled Cup Check Tiers"
    valid_keys = {"3rd_place", "2nd_place", "1st_place", "1_star", "2_star", "3_star"}
    default = {"3rd_place", "2nd_place", "1st_place", "1_star", "2_star"}


class IncludeRaceChecks(Toggle):
    """Include individual race 1st place checks in addition to cup checks."""
    display_name = "Include Race Checks"
    default = False


class EnableMidRaceMemoryFeatures(Toggle):
    """Enable mid race memory features (powerups, traps, fillers). 
    Disable for now as they are not implemented yet."""
    display_name = "Enable Mid Race Memory Features"
    default = False


class CupsRequiredForGoal(Range):
    """Number of cups that must be completed at goal difficulty/CC to win."""
    display_name = "Cups Required for Goal"
    range_start = 1
    range_end = 8
    default = 6


class GoalDifficulty(Choice):
    """Difficulty tier required for goal cups."""
    display_name = "Goal Difficulty"
    option_3rd_place = 0
    option_2nd_place = 1
    option_1st_place = 2
    option_1_star = 3
    option_2_star = 4
    option_3_star = 5
    default = 3  # 1_star


class GoalCC(Choice):
    """Engine class required for goal cups."""
    display_name = "Goal CC"
    option_50cc = 0
    option_100cc = 1
    option_150cc = 2
    option_mirror = 3
    default = 2  # 150cc


class TrapPercentage(Range):
    """Percentage of filler items that will be traps (0-100)."""
    display_name = "Trap Percentage"
    range_start = 0
    range_end = 100
    default = 20


class TrapWeightBrake(Range):
    """Weight for Brake Trap. Set to 0 to disable."""
    display_name = "Trap Weight: Brake"
    range_start = 0
    range_end = 100
    default = 10


class TrapWeightGas(Range):
    """Weight for Gas Trap. Set to 0 to disable."""
    display_name = "Trap Weight: Gas"
    range_start = 0
    range_end = 100
    default = 10


class TrapWeightBoost(Range):
    """Weight for Boost Trap. Set to 0 to disable."""
    display_name = "Trap Weight: Boost"
    range_start = 0
    range_end = 100
    default = 5


class TrapWeightCloud(Range):
    """Weight for Cloud Trap. Set to 0 to disable."""
    display_name = "Trap Weight: Cloud"
    range_start = 0
    range_end = 100
    default = 15


class TrapWeightPOW(Range):
    """Weight for POW Trap. Set to 0 to disable."""
    display_name = "Trap Weight: POW"
    range_start = 0
    range_end = 100
    default = 12


class TrapWeightLightning(Range):
    """Weight for Lightning Trap. Set to 0 to disable."""
    display_name = "Trap Weight: Lightning"
    range_start = 0
    range_end = 100
    default = 8


class FillerItemQueueCap(Range):
    """Maximum filler items that can be queued per race. 0 = unlimited."""
    display_name = "Filler Item Queue Cap"
    range_start = 0
    range_end = 20
    default = 5


class FillerWeightRandom(Range):
    """Weight for Random Item filler."""
    display_name = "Filler Weight: Random Item"
    range_start = 0
    range_end = 100
    default = 30


class FillerWeightMushroom(Range):
    """Weight for Mushroom filler."""
    display_name = "Filler Weight: Mushroom"
    range_start = 0
    range_end = 100
    default = 20


class FillerWeightTripleMushroom(Range):
    """Weight for Triple Mushroom filler."""
    display_name = "Filler Weight: Triple Mushroom"
    range_start = 0
    range_end = 100
    default = 10


class FillerWeightGoldenMushroom(Range):
    """Weight for Golden Mushroom filler."""
    display_name = "Filler Weight: Golden Mushroom"
    range_start = 0
    range_end = 100
    default = 5


class FillerWeightStar(Range):
    """Weight for Star filler."""
    display_name = "Filler Weight: Star"
    range_start = 0
    range_end = 100
    default = 8


class FillerWeightBulletBill(Range):
    """Weight for Bullet Bill filler."""
    display_name = "Filler Weight: Bullet Bill"
    range_start = 0
    range_end = 100
    default = 5


class FillerWeightMegaMushroom(Range):
    """Weight for Mega Mushroom filler."""
    display_name = "Filler Weight: Mega Mushroom"
    range_start = 0
    range_end = 100
    default = 5


class FillerWeightBlueShell(Range):
    """Weight for Blue Shell filler."""
    display_name = "Filler Weight: Blue Shell"
    range_start = 0
    range_end = 100
    default = 3


class FillerWeightRedShell(Range):
    """Weight for Red Shell filler."""
    display_name = "Filler Weight: Red Shell"
    range_start = 0
    range_end = 100
    default = 15


class FillerWeightTripleRedShell(Range):
    """Weight for Triple Red Shell filler."""
    display_name = "Filler Weight: Triple Red Shell"
    range_start = 0
    range_end = 100
    default = 8


class FillerWeightBobOmb(Range):
    """Weight for Bob-omb filler."""
    display_name = "Filler Weight: Bob-omb"
    range_start = 0
    range_end = 100
    default = 6


class FillerWeightLightningItem(Range):
    """Weight for Lightning filler (not trap)."""
    display_name = "Filler Weight: Lightning"
    range_start = 0
    range_end = 100
    default = 4


class FillerWeightBlooper(Range):
    """Weight for Blooper filler."""
    display_name = "Filler Weight: Blooper"
    range_start = 0
    range_end = 100
    default = 6


class FillerWeightPOWBlock(Range):
    """Weight for POW Block filler."""
    display_name = "Filler Weight: POW Block"
    range_start = 0
    range_end = 100
    default = 6


@dataclass
class MKWiiOptions(PerGameCommonOptions):
    enabled_ccs: EnabledCCs
    enabled_cup_check_tiers: EnabledCupCheckTiers
    include_race_checks: IncludeRaceChecks
    enable_mid_race_memory_features: EnableMidRaceMemoryFeatures
    cups_required_for_goal: CupsRequiredForGoal
    goal_difficulty: GoalDifficulty
    goal_cc: GoalCC
    trap_percentage: TrapPercentage
    trap_weight_brake: TrapWeightBrake
    trap_weight_gas: TrapWeightGas
    trap_weight_boost: TrapWeightBoost
    trap_weight_cloud: TrapWeightCloud
    trap_weight_pow: TrapWeightPOW
    trap_weight_lightning: TrapWeightLightning
    filler_item_queue_cap: FillerItemQueueCap
    filler_weight_random: FillerWeightRandom
    filler_weight_mushroom: FillerWeightMushroom
    filler_weight_triple_mushroom: FillerWeightTripleMushroom
    filler_weight_golden_mushroom: FillerWeightGoldenMushroom
    filler_weight_star: FillerWeightStar
    filler_weight_bullet_bill: FillerWeightBulletBill
    filler_weight_mega_mushroom: FillerWeightMegaMushroom
    filler_weight_blue_shell: FillerWeightBlueShell
    filler_weight_red_shell: FillerWeightRedShell
    filler_weight_triple_red_shell: FillerWeightTripleRedShell
    filler_weight_bob_omb: FillerWeightBobOmb
    filler_weight_lightning_item: FillerWeightLightningItem
    filler_weight_blooper: FillerWeightBlooper
    filler_weight_pow_block: FillerWeightPOWBlock
