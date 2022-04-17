#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys

from .card import Card, get_appearance
from .action import Action
from typing import Dict, List

import importlib


class Player:
    """
    A Player class works as a wrapper around the Strategy class of the corresponding player.
    In particular, it has to take care of hiding information not known to the player.
    """
    
    def __init__(self, id: int, game: 'Game', hand: List[Card], ai: str, ai_params: Dict, strategy_log: bool = False):
        # my id (order of play)
        self.id: int = id
        
        # game
        self.game: 'Game' = game
        
        # initial hand of cards
        self.hand: List[Card] = hand
        
        # AI to be used, with parsameters
        self.ai: str = ai
        self.ai_params: Dict = ai_params
        
        # create strategy object
        Strategy = __import__('ai.%s.strategy' % self.ai, globals(), locals(), fromlist=['Strategy'], level=1).Strategy
        
        self.strategy = Strategy(verbose=strategy_log, params=ai_params)
    
    
    def __eq__(self, other):
        return self.id == other.id
    
    
    def next_player(self):
        return self.game.players[(self.id + 1) % self.game.num_players]
    
    def other_players(self):
        return {i: player for (i, player) in enumerate(self.game.players) if player != self}
    
    
    def initialize(self):
        # called once after all players are created, before the game starts
        self.initialize_strategy()
    
    
    def initialize_strategy(self):
        """
        To be called once before the beginning.
        """
        self.strategy.initialize(
                id = self.id,
                num_players = self.game.num_players,
                k = self.game.k,
                board = self.game.board,
                deck_type = self.game.deck_type,
                my_hand = get_appearance(self.hand, hide=True),
                hands = {i: get_appearance(player.hand) for (i, player) in self.other_players().items()},
                discard_pile = get_appearance(self.game.discard_pile),
                deck_size = len(self.game.deck),
                game = self.game
            )
        self.update_strategy()
    
    def update_strategy(self):
        """
        To be called immediately after every turn.
        """
        self.strategy.update(
                clues = self.game.clues,
                lives = self.game.lives,
                my_hand = get_appearance(self.hand, hide=True),
                hands = {i: get_appearance(player.hand) for (i, player) in self.other_players().items()},
                discard_pile = get_appearance(self.game.discard_pile),
                turn = self.game.get_current_turn(),
                last_turn = self.game.last_turn,
                deck_size = len(self.game.deck),
                game = self.game
            )
    
    
    def get_turn_action(self):
        # update strategy (in case this is the first turn)
        self.update_strategy()
        
        # choose action for this turn
        action = self.strategy.get_turn_action()
        action.apply(self.game)
        return action
    
    
    def feed_turn(self, turn):
        # update strategy
        self.update_strategy()
        
        # pass information about what happened during the turn
        self.strategy.feed_turn(turn.player.id, turn.action)


