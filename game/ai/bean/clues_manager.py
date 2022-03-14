#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import itertools
import copy

from ...action import Action, PlayAction, DiscardAction, ClueAction
from ...card import Card


class CluesManager(object):
    """
    CluesManager.
    """
    def __init__(self, strategy):
        self.strategy = strategy    # my strategy object
        
        # copy something from the strategy
        self.id = strategy.id
        self.num_players = strategy.num_players
        self.k = strategy.k
        self.possibilities = strategy.possibilities
        self.full_deck = strategy.full_deck
        self.board = strategy.board
        self.knowledge = strategy.knowledge
        
        self.COLORS_TO_NUMBERS = {color: i for (i, color) in enumerate(Card.COLORS)}
    
    
    def log(self, message):
        self.strategy.log(message)
    
    
    def is_duplicate(self, card):
        """
        Says if the given card is owned by some player who knows everything about it.
        """
        # check other players' hands
        for (player_id, hand) in self.strategy.hands.items():
            for card_pos in range(self.k):
                kn = self.knowledge[player_id][card_pos]
                if kn.knows_exactly() and hand[card_pos] is not None and hand[card_pos].equals(card):
                    return True
        
        # check my hand
        for card_pos in range(self.k):
            kn = self.knowledge[self.id][card_pos]
            if kn.knows_exactly() and any(card.equals(c) for c in self.strategy.possibilities[card_pos]):
                return True
        
        return False
    
    
    def is_usable(self, clue_giver_id):
        """
        Check that it is possible to pass all the information.
        """
        return True
    
    
    def receive_clue(self, player_id: int, clue_action: ClueAction):
        """
        Process clue given by player_id
        - Update Knowledge and self.possiblities based on direct clue.
        - Identify what type(s) of clues it is (play or save) based on convention.
            - For every type that it is identified to be, 
            - 	Update self.possibilities using convention based information
        """
        # Clue is for me
        if clue_action.target_id == self.id:
            # process direct clue
            for (i, p) in enumerate(self.possibilities):
                for card in self.strategy.full_deck_composition:
                    if not card.matches_clue(clue_action, i) and card in p:
                        del p[card]
        
        # update explicit knowledge
        for card_pos in clue_action.cards_pos:
            kn = self.knowledge[clue_action.target_id][card_pos]
            if clue_action.clue_type == Action.COLOR:
                kn.color = clue_action.color
            else:
                kn.number = clue_action.number
        
    
    def choose_all_cards_positions(self, target_id, clue_type):
        """
        Choose all card positions that receive clues (of the given type) from the given player in the given turn.
        """
        hand = self.strategy.my_hand if target_id == self.id else self.strategy.hands[target_id]
        possible_cards = [card_pos for (card_pos, kn) in enumerate(self.knowledge[target_id]) if hand[card_pos] is not None and not (kn.color if clue_type == Action.COLOR else kn.number)]
        
        return possible_cards
    
    
    
    def get_clue(self):
        """
        Compute clue to give.
        """
        raise NotImplementedError
    
    
