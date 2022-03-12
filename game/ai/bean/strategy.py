#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import itertools
import copy
from collections import Counter

from ...action import Action, PlayAction, DiscardAction, HintAction
from ...card import Card, get_appearance
from ...deck import DECKS
from ...base_strategy import BaseStrategy
from .hints_manager import ValueHintsManager




class Knowledge:
    """
    An instance of this class represents what a player knows about a card, as known by everyone.
    """
    
    def __init__(self, color=False, number=False):
        self.color = color                  # know the color
        self.number = number                # know the number
        self.playable = False               # at some point, this card was playable
        self.non_playable = False           # at some point, this card was not playable
        self.useless = False                # this card is useless
        self.high = False                   # at some point, this card was high (see CardHintsManager)
    
    
    def __repr__(self):
        return ("C" if self.color else "-") + ("N" if self.number else "-") + ("P" if self.playable else "-") + ("Q" if self.non_playable else "-") + ("L" if self.useless else "-") + ("H" if self.high else "-")
    
    
    def knows(self, hint_type):
        """
        Does the player know the color/number?
        """
        assert hint_type in Action.HINT_TYPES
        if hint_type == Action.COLOR:
            return self.color
        else:
            return self.number
    
    def knows_exactly(self):
        """
        Does the player know exactly this card?
        """
        return self.color and (self.number or self.playable)


class Strategy(BaseStrategy):
    """
    An instance of this class represents a player's strategy.
    It only has the knowledge of that player, and it must make decisions.
    """
    
    DECK_SIZE_BEFORE_FULL_SEARCH = {
        4: 10,
        5: 4,
    }   # k (number of cards per hand): size of the deck when we want to consider all combinations of cards
    
    
    def __init__(self, verbose=False, params={}):
        self.COLORS_TO_NUMBERS = {color: i for (i, color) in enumerate(Card.COLORS)}
        self.verbose = verbose
        self.params = params
    
    
    def initialize(self, id, num_players, k, board, deck_type, my_hand, hands, discard_pile, deck_size):
        """
        To be called once before the beginning.
        """
        self.id = id
        self.num_players = num_players
        self.k = k  # number of cards per hand
        self.board = board
        self.deck_type = deck_type
        
        # store a copy of the full deck
        self.full_deck = get_appearance(DECKS[deck_type]())
        self.full_deck_composition = Counter(self.full_deck)
        
        # hands
        self.my_hand = my_hand  # says in which positions there is actually a card
        self.hands = hands
        
        # discard pile
        self.discard_pile = discard_pile
        
        # deck size
        self.deck_size = deck_size
        
        # for each of my card, store its possibilities
        self.possibilities = [Counter(self.full_deck) for i in range(self.k)]
        
        # remove cards of other players from possibilities
        self.update_possibilities()
        
        # knowledge of all players
        self.knowledge = [[Knowledge(color=False, number=False) for j in range(k)] for i in range(num_players)]
        
        # hints scheduler
        self.hints_manager = ValueHintsManager(self)
    
    
    def visible_cards(self):
        """
        Counter of all the cards visible by me.
        """
        res = Counter(self.discard_pile)
        for hand in self.hands.values():
            res += Counter(hand)
        
        return res
    
    
    def update_possibilities(self):
        """
        Update possibilities removing visible cards.
        """
        visible_cards = self.visible_cards()
        for p in self.possibilities:
            for card in self.full_deck_composition:
                if card in p:
                    # this card is still possible
                    # update the number of possible occurrences
                    p[card] = self.full_deck_composition[card] - visible_cards[card]
                    
                    if p[card] == 0:
                        # remove this card
                        del p[card]
        
        assert all(sum(p.values()) > 0 or self.my_hand[card_pos] is None for (card_pos, p) in enumerate(self.possibilities))    # check to have at least one possible card!
    
    
    def update_possibilities_with_combinations(self):
        """
        Update possibilities examining all combinations of my hand.
        Better to do it with only few cards remaining!
        """
        possible_cards = Counter()
        for p in self.possibilities:
            assert all(x > 0 for x in list(p.values()))
            possible_cards |= p
        
        new_possibilities = [set() for card_pos in range(self.k)]
        
        num_cards = len([x for x in self.my_hand if x is not None])
        assert num_cards <= self.k
        
        # cycle over all combinations
        for comb in itertools.permutations(list(possible_cards.elements()), num_cards):
            # construct hand
            hand = copy.copy(self.my_hand)
            i = 0
            for card_pos in range(self.k):
                if hand[card_pos] is not None:
                    hand[card_pos] = comb[i]
                    i += 1
            
            # check if this hand is possible
            if all(card is None or self.possibilities[card_pos][card] > 0 for (card_pos, card) in enumerate(hand)):
                # this hand is possible
                # self.log("possible hand %r" % hand)
                
                for (card_pos, card) in enumerate(hand):
                    if card is not None:
                        new_possibilities[card_pos].add(card)
        
        self.log("old possibilities %r" % [len(p) for p in self.possibilities])
        self.log("new possibilities %r" % [len(p) for p in new_possibilities])
        
        # update possibilities
        for (card_pos, p) in enumerate(self.possibilities):
            self.possibilities[card_pos] = p & Counter(new_possibilities[card_pos])
        
        self.update_possibilities() # set the right multiplicities
    
    
    def next_player_id(self):
        return (self.id + 1) % self.num_players
    
    def other_players_id(self):
        return [i for i in range(self.num_players) if i != self.id]
    
    
    def reset_knowledge(self, player_id, card_pos, new_card_exists):
        self.knowledge[player_id][card_pos] = Knowledge(False, False)
    
    
    def print_knowledge(self):
        print("Knowledge")
        for i in range(self.num_players):
            print("Player %d:" % i, end=' ')
            for card_pos in range(self.k):
                print(self.knowledge[i][card_pos], end=' ')
            print()
        print()

    
    def feed_turn(self, player_id, action):
        """
        Receive information about a played turn.
        """
        if action.type in [Action.PLAY, Action.DISCARD]:
            # reset knowledge of the player
            new_card = self.my_hand[action.card_pos] if player_id == self.id else self.hands[player_id][action.card_pos]
            self.reset_knowledge(player_id, action.card_pos, new_card is not None)
            
            if player_id == self.id:
                # check for my new card
                self.possibilities[action.card_pos] = Counter(self.full_deck) if self.my_hand[action.card_pos] is not None else Counter()
        
        elif action.type == Action.HINT:
            # someone gave a hint!
            # the suitable hints manager must process it
            hints_manager = self.hints_scheduler.select_hints_manager(player_id, action.turn)
            hints_manager.receive_hint(player_id, action)
        
        # update possibilities with visible cards
        self.update_possibilities()
        
        # print knowledge
        if self.verbose and self.id == self.num_players-1:
            self.print_knowledge()

    
    
    def get_best_discard(self):
        """
        Choose the best card to be discarded.
        """
        return NotImplementedError
    
    
    def get_best_play(self):
        """
        Choose the best card to play.
        """
        return NotImplementedError
    
    
    def get_best_play_last_round(self):
        """
        Choose the best card to play in the last round of the game.
        The players know almost everything, and it is reasonable to examine all the possibilities.
        """
        return NotImplementedError

    
    def get_turn_action(self):
        """
        Choose action for this turn.
        """
        return NotImplementedError

