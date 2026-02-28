#!/usr/bin/env python3
"""Tests for Sushi Go client infrastructure and bot strategies."""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(__file__))

from base_client import GameState, SushiGoClient
from client_1 import CompletionBot
from client_2 import MakiRushBot
from client_3 import DenierBot
from client_5 import RoundAdaptiveBot
import b_v_sushi_go_client as bv


class StubClient(SushiGoClient):
    """Minimal concrete client for testing infrastructure methods."""
    def choose_card(self, hand): return 0


def make_state(**kw):
    defaults = dict(game_id="g1", player_id=0, hand=[], player_name="Bot")
    defaults.update(kw)
    return GameState(**defaults)


def make_bot(cls, **kw):
    bot = cls()
    bot.state = make_state(**kw)
    return bot


class TestGameState(unittest.TestCase):
    def test_count_played(self):
        s = make_state(played_cards=["Tempura", "Tempura", "Sashimi"])
        self.assertEqual(s.count_played("Tempura"), 2)
        self.assertEqual(s.count_played("Sashimi"), 1)
        self.assertEqual(s.count_played("Dumpling"), 0)

    def test_opponent_total(self):
        s = make_state(opponent_cards={"Alice": ["Tempura", "Tempura"], "Bob": ["Tempura"]})
        self.assertEqual(s.opponent_total("Tempura"), 3)
        self.assertEqual(s.opponent_total("Sashimi"), 0)

    def test_any_opponent_has(self):
        s = make_state(opponent_cards={"Alice": ["Maki Roll (3)"]})
        self.assertTrue(s.any_opponent_has("Maki Roll (3)"))
        self.assertFalse(s.any_opponent_has("Pudding"))


class TestParseHand(unittest.TestCase):
    def setUp(self):
        self.client = StubClient()
        self.client.state = make_state()

    def test_basic_indexed_hand(self):
        self.client.parse_hand("HAND 0:Tempura 1:Sashimi 2:Maki Roll (3)")
        self.assertEqual(self.client.state.hand, ["Tempura", "Sashimi", "Maki Roll (3)"])

    def test_multiword_cards_preserved(self):
        self.client.parse_hand("HAND 0:Squid Nigiri 1:Salmon Nigiri 2:Egg Nigiri")
        self.assertEqual(self.client.state.hand, ["Squid Nigiri", "Salmon Nigiri", "Egg Nigiri"])

    def test_has_chopsticks_updated(self):
        self.client.state.played_cards = ["Chopsticks"]
        self.client.parse_hand("HAND 0:Tempura")
        self.assertTrue(self.client.state.has_chopsticks)

    def test_has_unused_wasabi_one_wasabi_no_nigiri(self):
        self.client.state.played_cards = ["Wasabi"]
        self.client.parse_hand("HAND 0:Tempura")
        self.assertTrue(self.client.state.has_unused_wasabi)

    def test_has_unused_wasabi_consumed_by_nigiri(self):
        self.client.state.played_cards = ["Wasabi", "Squid Nigiri"]
        self.client.parse_hand("HAND 0:Tempura")
        self.assertFalse(self.client.state.has_unused_wasabi)


class TestHandleMessage(unittest.TestCase):
    def setUp(self):
        self.client = StubClient()
        self.client.state = make_state(round=1, turn=3, played_cards=["Tempura"])

    def test_round_start_resets_state(self):
        result = self.client.handle_message("ROUND_START 2")
        self.assertEqual(self.client.state.round, 2)
        self.assertEqual(self.client.state.turn, 1)
        self.assertEqual(self.client.state.played_cards, [])
        self.assertTrue(result)

    def test_played_increments_turn(self):
        self.client.handle_message("PLAYED Bot:Tempura; Alice:Sashimi")
        self.assertEqual(self.client.state.turn, 4)

    def test_round_end_clears_played_cards(self):
        self.client.handle_message("ROUND_END")
        self.assertEqual(self.client.state.played_cards, [])

    def test_game_end_returns_false(self):
        result = self.client.handle_message("GAME_END scores")
        self.assertFalse(result)


class TestParsePlayedOpponentTracking(unittest.TestCase):
    def setUp(self):
        self.client = StubClient()
        self.client.state = make_state(player_name="Bot")

    def test_adds_opponent_cards(self):
        self.client.parse_played("PLAYED Alice:Squid Nigiri; Bob:Tempura")
        self.assertIn("Alice", self.client.state.opponent_cards)
        self.assertEqual(self.client.state.opponent_cards["Alice"], ["Squid Nigiri"])
        self.assertEqual(self.client.state.opponent_cards["Bob"], ["Tempura"])

    def test_skips_own_player(self):
        self.client.parse_played("PLAYED Bot:Tempura; Alice:Sashimi")
        self.assertNotIn("Bot", self.client.state.opponent_cards)

    def test_accumulates_across_turns(self):
        self.client.parse_played("PLAYED Alice:Tempura")
        self.client.parse_played("PLAYED Alice:Sashimi")
        self.assertEqual(self.client.state.opponent_cards["Alice"], ["Tempura", "Sashimi"])


class TestCompletionBot(unittest.TestCase):
    def test_cashes_wasabi_with_best_nigiri(self):
        bot = make_bot(CompletionBot, has_unused_wasabi=True)
        hand = ["Tempura", "Salmon Nigiri", "Squid Nigiri"]
        self.assertEqual(bot.choose_card(hand), hand.index("Squid Nigiri"))

    def test_completes_odd_tempura_pair(self):
        bot = make_bot(CompletionBot, played_cards=["Tempura"])
        hand = ["Sashimi", "Tempura", "Pudding"]
        self.assertEqual(bot.choose_card(hand), hand.index("Tempura"))

    def test_builds_toward_sashimi_set(self):
        bot = make_bot(CompletionBot, played_cards=["Sashimi"])
        hand = ["Tempura", "Sashimi", "Pudding"]
        self.assertEqual(bot.choose_card(hand), hand.index("Sashimi"))

    def test_grabs_more_dumplings_when_started(self):
        bot = make_bot(CompletionBot, played_cards=["Dumpling"])
        hand = ["Maki Roll (3)", "Dumpling", "Pudding"]
        self.assertEqual(bot.choose_card(hand), hand.index("Dumpling"))

    def test_fallback_priority_wasabi_first(self):
        bot = make_bot(CompletionBot)
        hand = ["Pudding", "Wasabi", "Egg Nigiri"]
        self.assertEqual(bot.choose_card(hand), hand.index("Wasabi"))



class TestMakiRushBot(unittest.TestCase):
    def test_prefers_maki_roll_3_over_everything(self):
        bot = make_bot(MakiRushBot)
        hand = ["Squid Nigiri", "Maki Roll (3)", "Wasabi"]
        self.assertEqual(bot.choose_card(hand), hand.index("Maki Roll (3)"))

    def test_pivots_to_nigiri_when_late_and_maki_stacked(self):
        # turn=8 → turns_left=2; 2× Maki Roll (3) = 6 maki symbols
        bot = make_bot(MakiRushBot, turn=8, played_cards=["Maki Roll (3)", "Maki Roll (3)"])
        hand = ["Maki Roll (3)", "Squid Nigiri"]
        self.assertEqual(bot.choose_card(hand), hand.index("Squid Nigiri"))

    def test_cashes_wasabi_over_maki(self):
        bot = make_bot(MakiRushBot, has_unused_wasabi=True)
        hand = ["Maki Roll (3)", "Squid Nigiri"]
        self.assertEqual(bot.choose_card(hand), hand.index("Squid Nigiri"))


class TestDenierBot(unittest.TestCase):
    def test_blocks_opponents_tempura_pair(self):
        bot = make_bot(DenierBot, opponent_cards={"Alice": ["Tempura"]})
        hand = ["Pudding", "Tempura", "Sashimi"]
        self.assertEqual(bot.choose_card(hand), hand.index("Tempura"))

    def test_blocks_opponents_sashimi_set(self):
        bot = make_bot(DenierBot, opponent_cards={"Alice": ["Sashimi", "Sashimi"]})
        hand = ["Pudding", "Egg Nigiri", "Sashimi"]
        self.assertEqual(bot.choose_card(hand), hand.index("Sashimi"))

    def test_fallback_priority_with_no_opponents(self):
        bot = make_bot(DenierBot)
        hand = ["Pudding", "Squid Nigiri", "Tempura"]
        self.assertEqual(bot.choose_card(hand), hand.index("Squid Nigiri"))


class TestRoundAdaptiveBot(unittest.TestCase):
    def test_round1_prefers_sashimi(self):
        bot = make_bot(RoundAdaptiveBot, round=1)
        hand = ["Maki Roll (2)", "Sashimi", "Tempura"]
        self.assertEqual(bot.choose_card(hand), hand.index("Sashimi"))

    def test_round3_prefers_pudding(self):
        bot = make_bot(RoundAdaptiveBot, round=3)
        hand = ["Squid Nigiri", "Pudding", "Wasabi"]
        self.assertEqual(bot.choose_card(hand), hand.index("Pudding"))

    def test_late_turn_completes_near_tempura_pair(self):
        # turn=9 → turns_left=1; 1 Tempura played → needs exactly 1 more
        bot = make_bot(RoundAdaptiveBot, round=2, turn=9, played_cards=["Tempura"])
        hand = ["Sashimi", "Tempura", "Pudding"]
        self.assertEqual(bot.choose_card(hand), hand.index("Tempura"))


def make_bv_bot(**kw):
    """Create a bv SushiGoClient with a pre-set GameState."""
    client = bv.SushiGoClient("localhost", 9999)
    defaults = dict(game_id="g1", player_id=0, hand=[])
    defaults.update(kw)
    client.state = bv.GameState(**defaults)
    return client


class TestBVHandPhase(unittest.TestCase):
    def test_early_turn_1(self):
        self.assertEqual(make_bv_bot(turn=1)._hand_phase(), "early")

    def test_early_turn_3(self):
        self.assertEqual(make_bv_bot(turn=3)._hand_phase(), "early")

    def test_mid_turn_4(self):
        self.assertEqual(make_bv_bot(turn=4)._hand_phase(), "mid")

    def test_mid_turn_7(self):
        self.assertEqual(make_bv_bot(turn=7)._hand_phase(), "mid")

    def test_late_turn_8(self):
        self.assertEqual(make_bv_bot(turn=8)._hand_phase(), "late")

    def test_late_turn_10(self):
        self.assertEqual(make_bv_bot(turn=10)._hand_phase(), "late")

    def test_no_state_defaults_to_early(self):
        bot = bv.SushiGoClient("localhost", 9999)
        # state is None → falls back to turn=1 → "early"
        self.assertEqual(bot._hand_phase(), "early")


class TestBVWasabiCashIn(unittest.TestCase):
    def test_picks_squid_over_salmon(self):
        bot = make_bv_bot(has_unused_wasabi=True)
        hand = ["Salmon Nigiri", "Squid Nigiri", "Maki Roll (3)"]
        self.assertEqual(bot.choose_card(hand), hand.index("Squid Nigiri"))

    def test_picks_salmon_when_no_squid(self):
        bot = make_bv_bot(has_unused_wasabi=True)
        hand = ["Maki Roll (2)", "Salmon Nigiri"]
        self.assertEqual(bot.choose_card(hand), hand.index("Salmon Nigiri"))

    def test_picks_egg_as_last_resort(self):
        bot = make_bv_bot(has_unused_wasabi=True)
        hand = ["Dumpling", "Egg Nigiri"]
        self.assertEqual(bot.choose_card(hand), hand.index("Egg Nigiri"))

    def test_falls_through_to_priority_when_no_nigiri(self):
        # wasabi active but no nigiri in hand → use priority list
        bot = make_bv_bot(has_unused_wasabi=True, round=1, turn=1)
        hand = ["Pudding", "Sashimi", "Maki Roll (1)"]
        self.assertEqual(bot.choose_card(hand), hand.index("Sashimi"))


class TestBVRoundPhasePriority(unittest.TestCase):
    def test_round1_early_prefers_sashimi(self):
        bot = make_bv_bot(round=1, turn=1)
        hand = ["Pudding", "Sashimi", "Maki Roll (3)"]
        self.assertEqual(bot.choose_card(hand), hand.index("Sashimi"))

    def test_round1_mid_prefers_maki3(self):
        bot = make_bv_bot(round=1, turn=5)
        hand = ["Sashimi", "Maki Roll (3)", "Tempura"]
        self.assertEqual(bot.choose_card(hand), hand.index("Maki Roll (3)"))

    def test_round1_late_prefers_tempura(self):
        bot = make_bv_bot(round=1, turn=9)
        hand = ["Sashimi", "Squid Nigiri", "Tempura"]
        self.assertEqual(bot.choose_card(hand), hand.index("Tempura"))

    def test_round2_early_prefers_wasabi(self):
        bot = make_bv_bot(round=2, turn=1)
        hand = ["Sashimi", "Wasabi", "Maki Roll (3)"]
        self.assertEqual(bot.choose_card(hand), hand.index("Wasabi"))

    def test_round2_mid_prefers_squid_nigiri(self):
        bot = make_bv_bot(round=2, turn=5)
        hand = ["Wasabi", "Squid Nigiri", "Sashimi"]
        self.assertEqual(bot.choose_card(hand), hand.index("Squid Nigiri"))

    def test_round2_late_prefers_squid_nigiri(self):
        bot = make_bv_bot(round=2, turn=9)
        hand = ["Tempura", "Squid Nigiri", "Dumpling"]
        self.assertEqual(bot.choose_card(hand), hand.index("Squid Nigiri"))

    def test_round3_early_prefers_pudding(self):
        bot = make_bv_bot(round=3, turn=1)
        hand = ["Wasabi", "Pudding", "Squid Nigiri"]
        self.assertEqual(bot.choose_card(hand), hand.index("Pudding"))

    def test_round3_late_prefers_pudding(self):
        bot = make_bv_bot(round=3, turn=9)
        hand = ["Dumpling", "Pudding", "Tempura"]
        self.assertEqual(bot.choose_card(hand), hand.index("Pudding"))

    def test_unknown_round_falls_back_to_round1_early(self):
        # round=5 has no entry → fallback is (1, "early") → Sashimi wins
        bot = make_bv_bot(round=5, turn=1)
        hand = ["Pudding", "Sashimi", "Maki Roll (1)"]
        self.assertEqual(bot.choose_card(hand), hand.index("Sashimi"))


class TestBVParseHand(unittest.TestCase):
    def test_parses_card_names(self):
        bot = make_bv_bot()
        bot.parse_hand("HAND 0:Sashimi 1:Maki Roll (3) 2:Pudding")
        self.assertEqual(bot.state.hand, ["Sashimi", "Maki Roll (3)", "Pudding"])

    def test_chopsticks_in_played_sets_flag(self):
        bot = make_bv_bot(played_cards=["Chopsticks"])
        bot.parse_hand("HAND 0:Sashimi")
        self.assertTrue(bot.state.has_chopsticks)

    def test_no_chopsticks_clears_flag(self):
        bot = make_bv_bot(played_cards=["Tempura"])
        bot.parse_hand("HAND 0:Sashimi")
        self.assertFalse(bot.state.has_chopsticks)

    def test_wasabi_no_nigiri_sets_unused_wasabi(self):
        bot = make_bv_bot(played_cards=["Wasabi"])
        bot.parse_hand("HAND 0:Sashimi")
        self.assertTrue(bot.state.has_unused_wasabi)

    def test_wasabi_plus_nigiri_clears_unused_wasabi(self):
        # Wasabi was already paired with Squid Nigiri
        bot = make_bv_bot(played_cards=["Wasabi", "Squid Nigiri"])
        bot.parse_hand("HAND 0:Sashimi")
        self.assertFalse(bot.state.has_unused_wasabi)

    def test_no_wasabi_clears_flag(self):
        bot = make_bv_bot(played_cards=["Tempura", "Sashimi"])
        bot.parse_hand("HAND 0:Pudding")
        self.assertFalse(bot.state.has_unused_wasabi)


class TestBVHandleMessage(unittest.TestCase):
    def test_round_start_updates_round_and_resets_state(self):
        bot = make_bv_bot(round=1, turn=5, played_cards=["Tempura"])
        bot.handle_message("ROUND_START 2")
        self.assertEqual(bot.state.round, 2)
        self.assertEqual(bot.state.turn, 1)
        self.assertEqual(bot.state.played_cards, [])

    def test_played_increments_turn(self):
        bot = make_bv_bot(turn=3)
        bot.handle_message("PLAYED p1:Sashimi p2:Tempura")
        self.assertEqual(bot.state.turn, 4)

    def test_round_end_clears_played_cards(self):
        bot = make_bv_bot(played_cards=["Sashimi", "Tempura"])
        bot.handle_message("ROUND_END")
        self.assertEqual(bot.state.played_cards, [])

    def test_game_end_returns_false(self):
        bot = make_bv_bot()
        result = bot.handle_message("GAME_END")
        self.assertFalse(result)

    def test_other_messages_return_true(self):
        bot = make_bv_bot()
        self.assertTrue(bot.handle_message("WAITING"))


if __name__ == "__main__":
    unittest.main()

