#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ast import Pass
import sys
import itertools
import copy
from collections import Counter

from ...action import Action, PlayAction, DiscardAction, ClueAction
from ...card import Card, get_appearance
from ...deck import DECKS
from ...base_strategy import BaseStrategy
from .clues_manager import CluesManager




class Knowledge:
    """
    An instance of this class represents 
    - What a player knows about a card, as known by everyone in self.color and self.number
    """
    
    def __init__(self, color=False, number=False):
        self.color = color                  # know exact color
        self.number = number                # know exact number
        self.playable = False               # at some point, this card was playable
        self.non_playable = False           # at some point, this card was not playable
        self.useless = False                # this card is useless    
    
    def __repr__(self):
        return ("C" if self.color else "-") + ("N" if self.number else "-") + ("P" if self.playable else "-") + ("Q" if self.non_playable else "-") + ("L" if self.useless else "-") + ("H" if self.high else "-")
    
    
    def knows(self, clue_type):
        """
        Does the player know the color/number?
        """
        assert clue_type in Action.CLUE_TYPES
        if clue_type == Action.COLOR:
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
        
        # for each of my card, store its possibilities using both implicit and explicit information
        self.possibilities = [Counter(self.full_deck) for i in range(self.k)]
        
        # remove cards of other players from possibilities
        self.update_possibilities()
        
        # knowledge of all players
        self.knowledge = [[Knowledge(color=False, number=False) for j in range(k)] for i in range(num_players)]
        
        self.clues_manager = CluesManager(self)
    
    
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
    

    def finesse_index(self, player_id) -> int:
        """
        Returns the index of the leftmost unclued(finesse) card of the given player.
        """

        "*** BEGIN SOLUTION ***"
        for i, kn in enumerate(self.knowledge[player_id]):
            if not (kn.knows(Action.COLOR) or kn.knows(Action.NUMBER)):
                return i
        "*** END SOLUTION ***"


    def chop_index(self, player_id) -> int:
        """
        Returns the index of the rightmost unclued(chop) card of the given player.
        """

        "*** BEGIN SOLUTION ***"
        for i, kn in enumerate(self.knowledge[player_id][::-1]):
            if not (kn.knows(Action.COLOR) or kn.knows(Action.NUMBER)):
                return (self.k - 1) - i
        "*** END SOLUTION ***"


    def update_knowledge(self, player_id, card_pos, new_card_exists):
        self.knowledge[player_id].pop(card_pos)
        self.knowledge[player_id].insert(0, Knowledge(False, False))
    
    
    def print_knowledge(self):
        print("Knowledge")
        for i in range(self.num_players):
            print("Player %d:" % i, end=' ')
            for card_pos in range(self.k):
                print(self.knowledge[i][card_pos], end=' ')
            print()
        print()

    
    def feed_turn(self, player_id: int, action: Action):
        """
        Receive information about a played turn.
        """
        if action.type in [Action.PLAY, Action.DISCARD]:
            # reset knowledge of the player
            new_card = self.my_hand[0] if player_id == self.id else self.hands[player_id][0]
            self.update_knowledge(player_id, action.card_pos, new_card is not None)
            
            if player_id == self.id:
                # check for my new card
                self.possibilities.pop(action.card_pos)
                self.possibilities.insert(0, Counter(self.full_deck) if self.my_hand[0] is not None else Counter())
        
        elif action.type == Action.CLUE:
            # someone gave a clue!
            self.process_clue(player_id, action)
        
        # update possibilities with visible cards
        self.update_possibilities()
        
        # print knowledge
        if self.verbose and self.id == self.num_players-1:
            self.print_knowledge()

    
    def process_clue(self, player_id: int, action: ClueAction):
        """
        Process clue given by player_id
        - Update Knowledge and self.possiblities based on direct clue.
        - Identify what type(s) of clues it is (play or save) based on convention.
            - For every type that it is identified to be, 
            - 	Update self.possibilities using convention based information
        """
        # Clue is for me
        if action.player_id == self.id:
            # process direct clue
            for (i, p) in enumerate(self.possibilities):
                for card in self.strategy.full_deck_composition:
                    if not card.matches_clue(action, i) and card in p:
                        # self.log("removing card %r from position %d due to clue" % (card, i))
                        # p.remove(card)
                        del p[card]
        
        # update knowledge
        for card_pos in action.cards_pos:
            kn = self.knowledge[action.player_id][card_pos]
            if action.clue_type == Action.COLOR:
                kn.color = True
            else:
                kn.number = True
        
        chop_index = self.chop_index(self.id)
        if len(action.card_pos) == 1:
            # If it is a 2 or 5 clue that touches chop, it is a discard clue. Otherwise, it is a play clue.
            if chop_index == action.cards_pos[0] and action.clue_type == ClueAction.NUMBER and action.number == 5 or action.number == 2:
                # It's a discard clue
                pass
        else:
            pass
        
        

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


